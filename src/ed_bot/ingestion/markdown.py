"""Convert EdStem threads and comments to structured markdown."""

import re
from dataclasses import dataclass, field


@dataclass
class CommentData:
    type: str  # "answer" or "comment"
    author_role: str  # "student", "staff", "admin"
    content: str  # markdown
    is_endorsed: bool


@dataclass
class ThreadData:
    thread_id: int
    thread_number: int
    course_id: int
    semester: str
    category: str
    subcategory: str | None
    type: str
    title: str
    content: str  # markdown body
    author_role: str
    is_endorsed: bool
    is_private: bool
    is_answered: bool
    has_staff_response: bool
    has_accepted_answer: bool
    created: str
    updated: str
    comments: list[CommentData] = field(default_factory=list)


def thread_to_markdown(thread: ThreadData) -> str:
    """Convert a ThreadData to structured markdown with YAML frontmatter."""
    frontmatter = f"""---
thread_id: {thread.thread_id}
thread_number: {thread.thread_number}
course_id: {thread.course_id}
semester: {thread.semester}
category: "{thread.category}"
subcategory: {f'"{thread.subcategory}"' if thread.subcategory else 'null'}
type: {thread.type}
title: "{thread.title}"
author_role: {thread.author_role}
status: {'resolved' if thread.is_answered else 'open'}
is_endorsed: {str(thread.is_endorsed).lower()}
is_private: {str(thread.is_private).lower()}
created: {thread.created}
updated: {thread.updated}
comment_count: {len(thread.comments)}
has_staff_response: {str(thread.has_staff_response).lower()}
has_accepted_answer: {str(thread.has_accepted_answer).lower()}
---"""

    body = f"\n\n# {thread.title}\n\n{thread.content}"

    for comment in thread.comments:
        label = comment.type.capitalize()
        endorsed_str = " (endorsed)" if comment.is_endorsed else ""
        body += f"\n\n## {label} by {comment.author_role}{endorsed_str}\n\n{comment.content}"

    return frontmatter + body + "\n"


def thread_filename(thread_number: int, title: str) -> str:
    """Generate a filename from thread number and title."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"{thread_number:04d}-{slug}.md"
