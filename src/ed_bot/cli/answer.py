"""Answer CLI command — inline drafting."""

import json
import pathlib
import typer
from rich.console import Console

app = typer.Typer(help="Draft answer for a specific thread.", rich_markup_mode="rich")
console = Console()
err_console = Console(stderr=True)

DEFAULT_BOT_DIR = "~/.ed-bot"


def _get_bot_dir(bot_dir: str) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()


@app.callback(invoke_without_command=True)
def answer(
    ctx: typer.Context,
    thread_ref: str = typer.Argument(None, help="Thread ID or course_id:number"),
    hint: str = typer.Option(None, "--hint", help="Guidance for the draft"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Generate a draft answer for a specific thread."""
    if ctx.invoked_subcommand is not None:
        return

    if thread_ref is None:
        err_console.print("[red]Error: THREAD_REF is required.[/red]")
        raise typer.Exit(1)

    from ed_api import EdClient
    from ed_bot.config import BotConfig
    from ed_bot.engine.classifier import QuestionType, ThreadClassifier
    from ed_bot.engine.drafter import DraftGenerator
    from ed_bot.engine.guardrails import GuardrailsManager
    from ed_bot.knowledge.collections import KnowledgeBase
    from ed_bot.knowledge.retrieval import ContextRetriever
    from ed_bot.queue.manager import Draft, DraftQueue
    from ed_bot.queue.priority import compute_priority

    config = BotConfig.load(_get_bot_dir(bot_dir))
    client = EdClient(region=config.region)

    # Fetch thread
    if ":" in thread_ref:
        course_id_str, number_str = thread_ref.split(":", 1)
        thread = client.threads.get_by_number(int(course_id_str), int(number_str))
    else:
        thread = client.threads.get(int(thread_ref))

    # Classify
    status = ThreadClassifier.classify_status(
        comment_count=len(thread.comments),
        has_staff_response=getattr(thread, "has_staff_response", False),
        is_endorsed=thread.is_endorsed,
        is_answered=thread.is_answered,
    )

    # Load guardrails
    guardrails_mgr = GuardrailsManager(config.guardrails_dir)
    project_slug = guardrails_mgr.detect_project(thread.title + " " + thread.category)
    guardrails = guardrails_mgr.load(project_slug) if project_slug else None
    style_guide = GuardrailsManager.load_style_guide(config.style_guide_path)

    # Retrieve context
    kb = KnowledgeBase(config)
    retriever = ContextRetriever(kb)
    try:
        from ed_api.content import ed_xml_to_markdown
        question_md = ed_xml_to_markdown(thread.content)
    except Exception:
        question_md = thread.content
    context = retriever.retrieve(thread.title + " " + question_md, project=project_slug)

    # Generate draft
    generator = DraftGenerator()
    draft_content = generator.generate(
        question=question_md,
        question_type=QuestionType.PROJECT_HELP,  # LLM classification would go here
        context=context,
        style_guide=style_guide,
        guardrails=guardrails,
        hint=hint,
    )

    # Store in queue
    queue = DraftQueue(config.drafts_dir)
    draft = Draft(
        thread_id=thread.id,
        thread_number=thread.number,
        thread_title=thread.title,
        thread_status=status.value,
        question_type="project_help",
        project=project_slug,
        priority=compute_priority(status),
        content=draft_content,
        context_used=context.source_files,
        guardrails_applied=project_slug,
    )
    draft_id = queue.add(draft)

    if json_output:
        typer.echo(json.dumps({
            "draft_id": draft_id,
            "thread_id": thread.id,
            "thread_number": thread.number,
            "title": thread.title,
            "status": status.value,
            "project": project_slug,
            "content": draft_content,
        }))
    else:
        console.print(f"\n[bold]Thread #{thread.number}:[/bold] {thread.title}")
        console.print(f"Status: {status.value} | Project: {project_slug or 'none'}")
        console.print(f"\n[dim]--- Draft Answer ---[/dim]\n")
        console.print(draft_content)
        console.print(f"\n[green]Draft saved: {draft_id}[/green]")
        console.print(f"[dim]ed approve {draft_id} | ed reject {draft_id}[/dim]")
