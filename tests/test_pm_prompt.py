import shlex
import sys
import unittest
from pathlib import Path

from u_agents.contract import RepoConfig
from u_agents.launcher import (
    DEFAULT_PROMPT_TEMPLATE,
    PACKAGE_DIR,
    Issue,
    render_pm_prompt,
)

PM_PROMPT = Path(__file__).resolve().parent.parent / "u_agents" / "prompts" / "pm.md"


class TestPmPromptContent(unittest.TestCase):
    def setUp(self):
        self.text = PM_PROMPT.read_text(encoding="utf-8")

    def test_mise_trust_is_conditional(self):
        # Fix #4: trust must be performed for repos that use mise, but the
        # prompt must not assume every repo does.
        self.assertIn("mise trust", self.text)
        self.assertIn("mise.toml", self.text)
        self.assertRegex(self.text, r"do not assume every repo uses mise")

    def test_records_pr_open_bookkeeping_via_cli(self):
        # Fix #2: opening a PR must durably advance agent_runs, not rely on
        # prompt memory.
        self.assertIn("u_agents.mark_pr_open", self.text)
        self.assertIn("status=pr_open", self.text)

    def test_pr_open_command_uses_explicit_package_root_and_python(self):
        # The PM runs from the target repo worktree, which has no u_agents on
        # the path and may have a psycopg-less Python on PATH. The command must
        # carry both an explicit PYTHONPATH and the explicit runtime
        # interpreter placeholder (not a bare `python3`).
        self.assertIn(
            "PYTHONPATH={u_agents_root} {u_agents_python} -m u_agents.mark_pr_open",
            self.text,
        )


class TestPmPromptRenders(unittest.TestCase):
    """The whole template must still render: every {placeholder} added for the
    new steps must exist in the launcher's mapping (no KeyError)."""

    def _issue(self):
        repo = RepoConfig("o/r", "/workspace/r", "main")
        return Issue(repo=repo, number=233, title="t", url="http://x/233", labels=[])

    def test_renders_without_unknown_placeholders(self):
        rendered = render_pm_prompt(DEFAULT_PROMPT_TEMPLATE, self._issue(), "r-233")
        # The rendered command must carry the substituted (shell-quoted) package
        # root AND the explicit runtime interpreter, so it is runnable from the
        # target worktree with a psycopg-enabled Python.
        expected_root = shlex.quote(str(PACKAGE_DIR.parent))
        expected_python = shlex.quote(sys.executable)
        self.assertIn(
            f"PYTHONPATH={expected_root} {expected_python} "
            f"-m u_agents.mark_pr_open --repo o/r --issue 233 --pr",
            rendered,
        )
        # The interpreter must be the launcher's own sys.executable, not a bare
        # `python3`.
        self.assertIn(sys.executable, rendered)
        # Placeholders must be fully substituted (no leftover braces).
        self.assertNotIn("{u_agents_root}", rendered)
        self.assertNotIn("{u_agents_python}", rendered)
        # Literal placeholder for the PR number is left for the PM to fill.
        self.assertIn("<pr-number>", rendered)


if __name__ == "__main__":
    unittest.main()
