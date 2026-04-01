from typer.testing import CliRunner


class TestCLIHelp:
    def test_main_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ingest" in result.stdout

    def test_main_help_shows_commands(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # At least some subcommands appear
        assert "ingest" in result.stdout or "review" in result.stdout or "status" in result.stdout

    def test_ingest_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "threads" in result.stdout

    def test_ingest_threads_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["ingest", "threads", "--help"])
        assert result.exit_code == 0

    def test_ingest_projects_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["ingest", "projects", "--help"])
        assert result.exit_code == 0

    def test_review_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["review", "--help"])
        assert result.exit_code == 0

    def test_guardrails_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["guardrails", "--help"])
        assert result.exit_code == 0

    def test_guardrails_list_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["guardrails", "list", "--help"])
        assert result.exit_code == 0

    def test_status_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0

    def test_answer_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["answer", "--help"])
        assert result.exit_code == 0
