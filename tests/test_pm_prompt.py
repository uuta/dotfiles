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
LEGACY_REVIEW_DIFF_PROMPT = (
    Path(__file__).resolve().parent.parent / "prompts" / "review-diff.md"
)
REVIEW_DIFFS_SKILL = (
    Path(__file__).resolve().parent.parent / "skills" / "review-diffs" / "SKILL.md"
)


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

    def test_records_review_comment_resolution_before_rearm(self):
        # Issue #20: the PM must persist a durable resolution in the DB before
        # re-arming the watcher; a GitHub comment is not durable state.
        self.assertIn("# PR review comment resolution", self.text)
        self.assertIn(
            "PYTHONPATH={u_agents_root} {u_agents_python} "
            "-m u_agents.record_review_comment_resolution",
            self.text,
        )
        self.assertIn("BEFORE you re-arm the watcher", self.text)
        self.assertRegex(self.text, r"addressed.*requires.*--commit-sha")
        # mark_pr_open does not own review comment resolution.
        self.assertIn("mark_pr_open` only\nre-arms the watcher", self.text)

    def test_engineer_handoff_requires_implementation_preflight(self):
        self.assertIn(
            "{u_agents_root}/skills/implementation-preflight/SKILL.md",
            self.text,
        )
        self.assertIn("compact preflight note", self.text)
        self.assertIn("current web sources", self.text)
        self.assertIn("ask before high-impact adoption", self.text)

    def test_local_review_requires_plural_review_diffs(self):
        self.assertIn("manager-led `review-diffs` skill", self.text)
        self.assertIn("mandatory local\n     review entry point", self.text)
        self.assertIn("before PR creation", self.text)
        self.assertIn("{worktree}", self.text)
        self.assertIn("{branch}", self.text)
        self.assertNotIn("`review-diff`", self.text)
        self.assertNotIn("or the project's equivalent", self.text)

    def test_web_ui_review_requires_rendered_visual_evidence(self):
        self.assertIn("the reviewer must include the `ui-visual` lens", self.text)
        self.assertIn("not production", self.text)
        self.assertIn("before the PR is created", self.text)
        for width in ["900", "1180", "1440", "1920"]:
            self.assertIn(width, self.text)
        self.assertIn("screenshot paths", self.text)
        self.assertIn("verification/tooling gap", self.text)
        self.assertIn("{review_result}` under `verification`", self.text)
        self.assertIn("must not be marked `clean` solely", self.text)
        self.assertIn("source inspection,\n     builds, or unit tests", self.text)

    def test_u_agents_review_requires_run_scoped_tmux_targets(self):
        self.assertIn("run-scoped tmux naming contract", self.text)
        self.assertIn("derive a target prefix from this\n     issue/worktree", self.text)
        self.assertIn("exact tmux window-id targets", self.text)
        self.assertIn("docs/review/tmux-targets.env", self.text)
        self.assertIn("prompt\n     delivery, polling, and cleanup", self.text)
        self.assertIn("Static reviewer window names are not\n     allowed", self.text)
        self.assertIn("multiple issue reviews can run concurrently", self.text)


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
        self.assertIn(
            f"{expected_root}/skills/implementation-preflight/SKILL.md",
            rendered,
        )


class TestLegacyReviewDiffCommand(unittest.TestCase):
    def setUp(self):
        self.text = LEGACY_REVIEW_DIFF_PROMPT.read_text(encoding="utf-8")

    def test_delegates_to_plural_review_diffs(self):
        self.assertIn("Legacy alias for review-diffs", self.text)
        self.assertIn("delegates to the plural manager-led\n`review-diffs`", self.text)
        self.assertIn("/Users/yutaaoki/dotfiles/skills/review-diffs/SKILL.md", self.text)
        self.assertIn("Do not perform the old source-only review", self.text)
        self.assertIn("docs/review/", self.text)
        self.assertIn("UI screenshot paths", self.text)
        self.assertNotIn("Score (up to 100)", self.text)
        self.assertNotIn("Create/update docs/review.md", self.text)


class TestReviewDiffsSkillTmuxTargets(unittest.TestCase):
    def setUp(self):
        self.text = REVIEW_DIFFS_SKILL.read_text(encoding="utf-8")

    def test_uses_run_scoped_exact_tmux_targets(self):
        self.assertIn("tmux allows duplicate window names", self.text)
        self.assertIn("record the exact window id", self.text)
        self.assertIn("-P -F '#{window_id}'", self.text)
        self.assertIn("docs/review/tmux-targets.env", self.text)
        self.assertIn('"${review_tag}-req"', self.text)
        self.assertIn('tmux capture-pane -p -t "$REQ_WIN"', self.text)
        self.assertIn('tmux kill-window -t "$REQ_WIN"', self.text)
        self.assertIn("Never poll by a window name", self.text)

    def test_no_static_tmux_targets_in_examples(self):
        forbidden = [
            "tmux new-window -n review-req",
            "tmux new-window -n review-correctness",
            "tmux new-window -n review-security",
            "tmux new-window -n review-ui-visual",
            "tmux capture-pane -p -t <window>",
            "tmux kill-window -t review-req",
            "tmux kill-window -t review-correctness",
            "tmux kill-window -t review-security",
            "tmux kill-window -t review-ui-visual",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, self.text)


if __name__ == "__main__":
    unittest.main()
