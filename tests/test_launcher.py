import argparse
import os
import unittest
from pathlib import Path
from unittest import mock

from u_agents.contract import (
    LABEL_IN_PROGRESS,
    LABEL_READY,
    REVIEW_RESULT_STATUSES,
    RepoConfig,
)
from u_agents.agent_runs import AgentRun
from u_agents.control_plane import RunnerIdentity
from u_agents import launcher
from u_agents.launcher import (
    DEFAULT_CONFIG_PATHS,
    DEFAULT_PROMPT_TEMPLATE,
    PACKAGE_DIR,
    Issue,
    classify_direct_issue,
    dispatch_claim,
    main as launcher_main,
    pick_issue,
    render_pm_prompt,
    select_resume_targets,
)


def _mk_issue(repo: RepoConfig, n: int, title: str = "x",
              labels=(LABEL_READY,)) -> Issue:
    return Issue(repo=repo, number=n, title=title,
                 url=f"https://github.com/{repo.full_name}/issues/{n}",
                 labels=list(labels))


class FakeAgentRunsClient:
    def __init__(self, events=None):
        self.identity = RunnerIdentity("runner-1", "machine-1")
        self.events = [] if events is None else events
        self.cancelled = []

    def acquire_claim(self, payload):
        self.events.append("db_claim")
        return AgentRun(
            repository_full_name=payload.repository_full_name,
            github_issue_number=payload.github_issue_number,
            parent_branch=payload.parent_branch,
            branch_name=payload.branch_name,
            phase=payload.phase,
            runner_id=payload.runner_id,
            machine_id=payload.machine_id,
            locked_by=payload.locked_by,
            lease_until=payload.lease_until,
            worktree_basename=payload.worktree_basename,
            tmux_window=payload.tmux_window,
        )

    def mark_pm_started(self, run):
        self.events.append("pm_started")
        return AgentRun(
            repository_full_name=run.repository_full_name,
            github_issue_number=run.github_issue_number,
            parent_branch=run.parent_branch,
            branch_name=run.branch_name,
            phase="pm_started",
            runner_id=run.runner_id,
            machine_id=run.machine_id,
            locked_by=run.locked_by,
            lease_until=run.lease_until,
            worktree_basename=run.worktree_basename,
            tmux_window=run.tmux_window,
            pm_pane=f"agents:{run.tmux_window}.0",
        )

    def cancel_run(self, repo_full, issue_number, *, metadata=None):
        self.events.append("cancel")
        self.cancelled.append((repo_full, issue_number, metadata or {}))


def _args(**overrides):
    """Build a minimal argparse.Namespace matching launcher main() args."""
    defaults = dict(
        config=None,
        dry_run=False,
        repo=None,
        issue=None,
        prompt_template=DEFAULT_PROMPT_TEMPLATE,
        agent_runs_client=FakeAgentRunsClient(),
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestDefaultConfigPaths(unittest.TestCase):
    def test_repo_local_paths_are_package_anchored(self):
        # The first two defaults must point at the checked-out package's
        # config directory, anchored to launcher.py rather than the CWD.
        self.assertEqual(PACKAGE_DIR, Path(launcher.__file__).resolve().parent)
        self.assertEqual(
            DEFAULT_CONFIG_PATHS[:2],
            [
                PACKAGE_DIR / "config" / "repositories.yml",
                PACKAGE_DIR / "config" / "repositories.yaml",
            ],
        )

    def test_repo_local_paths_are_absolute(self):
        for p in DEFAULT_CONFIG_PATHS[:2]:
            self.assertTrue(p.is_absolute(), f"{p} should be absolute")

    def test_compatibility_fallbacks_unchanged(self):
        self.assertEqual(
            DEFAULT_CONFIG_PATHS[2:],
            [
                Path.home() / ".config" / "u-agents" / "repositories.yml",
                Path.home() / ".config" / "u-agents" / "repositories.yaml",
            ],
        )

    def test_repo_local_paths_do_not_depend_on_cwd(self):
        # Resolving the defaults from an unrelated working directory must
        # not change them: they are anchored to the package, not the CWD.
        orig = os.getcwd()
        try:
            os.chdir(os.path.dirname(orig) or "/")
            self.assertEqual(
                DEFAULT_CONFIG_PATHS[:2],
                [
                    PACKAGE_DIR / "config" / "repositories.yml",
                    PACKAGE_DIR / "config" / "repositories.yaml",
                ],
            )
        finally:
            os.chdir(orig)


class TestPickIssue(unittest.TestCase):
    def setUp(self):
        self.a = RepoConfig("o/a", "/w/a", "main", enabled=True)
        self.b = RepoConfig("o/b", "/w/b", "main", enabled=True)
        self.c = RepoConfig("o/c", "/w/c", "main", enabled=False)

    def test_picks_first_enabled_with_ready(self):
        def fake_list(r):
            if r is self.a:
                return []
            if r is self.b:
                return [_mk_issue(self.b, 7), _mk_issue(self.b, 8)]
            return []
        issue = pick_issue([self.a, self.b, self.c], None, None, list_fn=fake_list)
        self.assertEqual(issue.number, 7)
        self.assertIs(issue.repo, self.b)

    def test_skips_disabled_even_with_ready(self):
        def fake_list(r):
            return [_mk_issue(r, 1)] if r is self.c else []
        self.assertIsNone(pick_issue([self.c], None, None, list_fn=fake_list))

    def test_repo_filter_short_name(self):
        def fake_list(r):
            return [_mk_issue(r, 1)]
        issue = pick_issue([self.a, self.b], "b", None, list_fn=fake_list)
        self.assertIs(issue.repo, self.b)

    def test_repo_filter_full_name(self):
        def fake_list(r):
            return [_mk_issue(r, 1)]
        issue = pick_issue([self.a, self.b], "o/a", None, list_fn=fake_list)
        self.assertIs(issue.repo, self.a)

    def test_issue_filter(self):
        def fake_list(r):
            return [_mk_issue(r, 1), _mk_issue(r, 42)]
        issue = pick_issue([self.a], None, 42, list_fn=fake_list)
        self.assertEqual(issue.number, 42)

    def test_no_matches_returns_none(self):
        def fake_list(r):
            return []
        self.assertIsNone(pick_issue([self.a], None, None, list_fn=fake_list))


class TestRenderPmPrompt(unittest.TestCase):
    def test_renders_default_template_fields(self):
        repo = RepoConfig("uuta/trander-flutter", "/Users/y/trander-flutter", "master")
        issue = _mk_issue(repo, 233, title="add login")
        out = render_pm_prompt(DEFAULT_PROMPT_TEMPLATE, issue, "trander-flutter-233")
        self.assertIn("uuta/trander-flutter#233", out)
        self.assertIn('"add login"', out)
        self.assertIn("agents:trander-flutter-233.0", out)
        self.assertIn("/Users/y/trander-flutter/master", out)
        self.assertIn("/Users/y/trander-flutter/.worktrees/233", out)
        self.assertIn(
            "/Users/y/trander-flutter/.worktrees/233/tmp/review-result.json",
            out,
        )
        self.assertIn("feat/233", out)
        # Watchdog ping line is mentioned in the contract.
        self.assertIn("stalled", out)
        for status in REVIEW_RESULT_STATUSES:
            self.assertIn(status, out)
        for field in ("status", "must_fix", "optional", "verification", "summary"):
            self.assertIn(f'"{field}"', out)
        self.assertIn("Do not infer reviewer completion from tmux idle state", out)
        self.assertIn("5 minutes after reviewer", out)
        self.assertIn("Do not open a PR from pane output alone", out)

    def test_brace_in_title_does_not_break_format(self):
        repo = RepoConfig("o/r", "/w/r", "main")
        issue = _mk_issue(repo, 1, title="weird {brace} title")
        out = render_pm_prompt(DEFAULT_PROMPT_TEMPLATE, issue, "r-1")
        self.assertIn("weird {brace} title", out)


class TestClaudeTmuxGuard(unittest.TestCase):
    def setUp(self):
        self.repo = RepoConfig("o/r", "/w/r", "main")
        self.issue = _mk_issue(self.repo, 5, labels=[LABEL_READY])

    def test_default_claude_command_uses_bypass_permission_mode(self):
        self.assertEqual(
            launcher.CLAUDE_COMMAND,
            "claude --permission-mode bypassPermissions",
        )

    def test_new_window_starts_claude_command(self):
        with mock.patch("u_agents.launcher.ensure_session"), \
             mock.patch("u_agents.launcher.window_exists", return_value=False), \
             mock.patch("u_agents.launcher.wait_for_claude_ready") as m_wait, \
             mock.patch("u_agents.launcher._tmux") as m_tmux:
            window = launcher.ensure_window(self.repo, self.issue, dry_run=False)

        self.assertEqual(window, "r-5")
        m_tmux.assert_any_call([
            "new-window", "-t", launcher.TMUX_SESSION, "-n", "r-5",
            "-c", str(Path.home()), launcher.CLAUDE_COMMAND,
        ])
        m_wait.assert_called_once_with("r-5")

    def test_existing_window_must_be_claude_before_prompt(self):
        with mock.patch("u_agents.launcher.wait_for_claude_ready",
                        side_effect=RuntimeError("not claude")), \
             mock.patch("u_agents.launcher._tmux_in") as m_tmux_in:
            with self.assertRaises(RuntimeError):
                launcher.send_prompt("r-5", "hello", dry_run=False)
        m_tmux_in.assert_not_called()

    def test_expected_claude_start_accepts_quoted_command_with_args(self):
        with mock.patch("u_agents.launcher.CLAUDE_COMMAND",
                        "claude --dangerously-skip-permissions"):
            self.assertTrue(
                launcher._is_expected_claude_start(
                    '"claude --dangerously-skip-permissions"'
                )
            )

    def test_send_prompt_submits_with_control_m(self):
        with mock.patch("u_agents.launcher.wait_for_claude_ready"), \
             mock.patch("u_agents.launcher._tmux_in"), \
             mock.patch("u_agents.launcher._tmux") as m_tmux, \
             mock.patch("u_agents.launcher.os.getpid", return_value=123):
            launcher.send_prompt("r-5", "hello", dry_run=False)

        m_tmux.assert_any_call(["paste-buffer", "-b", "u-agent-prompt-123",
                                "-t", "agents:r-5.0"])
        m_tmux.assert_any_call(["send-keys", "-t", "agents:r-5.0", "C-m"])
        m_tmux.assert_any_call(["delete-buffer", "-b", "u-agent-prompt-123"],
                               check=False)

    def test_wait_for_claude_ready_accepts_idle_prompt(self):
        with mock.patch("u_agents.launcher._pane_start_command",
                        return_value=launcher.CLAUDE_COMMAND), \
             mock.patch("u_agents.launcher._pane_is_dead", return_value=False), \
             mock.patch("u_agents.launcher._capture_pane",
                        return_value="Claude Code\n\n│ >\n"):
            launcher.wait_for_claude_ready("r-5")

    def test_wait_for_claude_ready_accepts_placeholder_prompt(self):
        with mock.patch("u_agents.launcher._pane_start_command",
                        return_value=launcher.CLAUDE_COMMAND), \
             mock.patch("u_agents.launcher._pane_is_dead", return_value=False), \
             mock.patch("u_agents.launcher._capture_pane",
                        return_value='Claude Code\n\n│ > Try "fix the tests"\n'):
            launcher.wait_for_claude_ready("r-5")

    def test_wait_for_claude_ready_accepts_current_prompt_marker(self):
        with mock.patch("u_agents.launcher._pane_start_command",
                        return_value=launcher.CLAUDE_COMMAND), \
             mock.patch("u_agents.launcher._pane_is_dead", return_value=False), \
             mock.patch("u_agents.launcher._capture_pane",
                        return_value="Claude Code\n\n│ ❯\n"):
            launcher.wait_for_claude_ready("r-5")

    def test_wait_for_claude_ready_accepts_prompt_above_blank_status_tail(self):
        capture = "\n".join([
            "Claude Code",
            "────────────────────────────────────────────────────────────────────────────────",
            "❯ ",
            "────────────────────────────────────────────────────────────────────────────────",
            "  ? for shortcuts · ← for agents                3 MCP servers need auth · /mcp",
            *[""] * 18,
        ])
        with mock.patch("u_agents.launcher._pane_start_command",
                        return_value=launcher.CLAUDE_COMMAND), \
             mock.patch("u_agents.launcher._pane_is_dead", return_value=False), \
             mock.patch("u_agents.launcher._capture_pane",
                        return_value=capture):
            launcher.wait_for_claude_ready("r-5")

    def test_wait_for_claude_ready_times_out_without_idle_prompt(self):
        with mock.patch("u_agents.launcher._pane_start_command",
                        return_value=launcher.CLAUDE_COMMAND), \
             mock.patch("u_agents.launcher._pane_is_dead", return_value=False), \
             mock.patch("u_agents.launcher._capture_pane",
                        return_value="Claude Code update available\nPress Enter"), \
             mock.patch("u_agents.launcher.CLAUDE_READY_TIMEOUT_SECONDS", 0.01), \
             mock.patch("u_agents.launcher.CLAUDE_READY_POLL_SECONDS", 0), \
             mock.patch("u_agents.launcher.time.monotonic",
                        side_effect=[0.0, 0.0, 0.02]), \
             mock.patch("u_agents.launcher.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "idle input prompt"):
                launcher.wait_for_claude_ready("r-5")

    def test_send_prompt_does_not_paste_before_idle_prompt(self):
        with mock.patch("u_agents.launcher._pane_start_command",
                        return_value=launcher.CLAUDE_COMMAND), \
             mock.patch("u_agents.launcher._pane_is_dead", return_value=False), \
             mock.patch("u_agents.launcher._capture_pane",
                        return_value="Do you trust the files in this folder?"), \
             mock.patch("u_agents.launcher.CLAUDE_READY_TIMEOUT_SECONDS", 0.01), \
             mock.patch("u_agents.launcher.CLAUDE_READY_POLL_SECONDS", 0), \
             mock.patch("u_agents.launcher.time.monotonic",
                        side_effect=[0.0, 0.0, 0.02]), \
             mock.patch("u_agents.launcher.time.sleep"), \
             mock.patch("u_agents.launcher._tmux_in") as m_tmux_in:
            with self.assertRaisesRegex(RuntimeError, "idle input prompt"):
                launcher.send_prompt("r-5", "hello", dry_run=False)
        m_tmux_in.assert_not_called()


class TestClaimIssue(unittest.TestCase):
    def setUp(self):
        self.repo = RepoConfig("o/r", "/w/r", "main")
        self.issue = _mk_issue(self.repo, 5, labels=[LABEL_READY])

    def test_unexpected_gh_edit_failure_raises(self):
        res = mock.Mock(returncode=1, stderr="rate limit while editing labels")
        with mock.patch("u_agents.launcher._run", return_value=res):
            with self.assertRaisesRegex(RuntimeError, "gh issue edit failed"):
                launcher.claim_issue(self.issue, dry_run=False)

    def test_missing_label_failure_raises_with_bootstrap_hint(self):
        res = mock.Mock(returncode=1, stderr="label not found: status:ready")
        with mock.patch("u_agents.launcher._run", return_value=res):
            with self.assertRaisesRegex(RuntimeError, "Create the labels"):
                launcher.claim_issue(self.issue, dry_run=False)


class TestListByLabel(unittest.TestCase):
    def test_malformed_json_returns_empty_and_warns(self):
        repo = RepoConfig("o/r", "/w/r", "main")
        res = mock.Mock(returncode=0, stdout="{not json", stderr="")
        with mock.patch("u_agents.launcher._run", return_value=res), \
             mock.patch("sys.stderr") as stderr:
            self.assertEqual(launcher._list_by_label(repo, LABEL_READY), [])

        warning = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertIn("WARN: gh issue list returned malformed JSON", warning)
        self.assertIn("o/r", warning)


class TestClassifyDirectIssue(unittest.TestCase):
    def setUp(self):
        self.repo = RepoConfig("o/r", "/w/r", "main")

    def test_status_ready_means_claim(self):
        issue = _mk_issue(self.repo, 1, labels=[LABEL_READY])
        self.assertEqual(classify_direct_issue(issue), "claim")

    def test_status_in_progress_means_resume(self):
        issue = _mk_issue(self.repo, 1, labels=[LABEL_IN_PROGRESS])
        self.assertEqual(classify_direct_issue(issue), "resume")

    def test_ready_wins_when_both_present(self):
        # Defensive: if a repo somehow has both labels, prefer claim semantics.
        issue = _mk_issue(self.repo, 1, labels=[LABEL_READY, LABEL_IN_PROGRESS])
        self.assertEqual(classify_direct_issue(issue), "claim")

    def test_neither_label_means_skip(self):
        issue = _mk_issue(self.repo, 1, labels=["bug", "size:s"])
        self.assertEqual(classify_direct_issue(issue), "skip")

    def test_no_labels_means_skip(self):
        issue = _mk_issue(self.repo, 1, labels=[])
        self.assertEqual(classify_direct_issue(issue), "skip")


class TestSelectResumeTargets(unittest.TestCase):
    def setUp(self):
        self.a = RepoConfig("o/a", "/w/a", "main", enabled=True)
        self.b = RepoConfig("o/b", "/w/b", "main", enabled=True)
        self.c = RepoConfig("o/c", "/w/c", "main", enabled=False)

    def test_returns_only_in_progress_with_missing_window(self):
        in_progress = {
            self.a: [_mk_issue(self.a, 1, labels=[LABEL_IN_PROGRESS]),
                     _mk_issue(self.a, 2, labels=[LABEL_IN_PROGRESS])],
            self.b: [_mk_issue(self.b, 9, labels=[LABEL_IN_PROGRESS])],
        }
        # Only a-2 has a live window.
        existing = {"a-2"}
        targets = select_resume_targets(
            [self.a, self.b],
            list_in_progress_fn=lambda r: in_progress.get(r, []),
            window_exists_fn=lambda w: w in existing,
        )
        self.assertEqual([(i.repo.full_name, i.number) for i in targets],
                         [("o/a", 1), ("o/b", 9)])

    def test_skips_disabled_repo(self):
        in_progress = {self.c: [_mk_issue(self.c, 1, labels=[LABEL_IN_PROGRESS])]}
        targets = select_resume_targets(
            [self.c],
            list_in_progress_fn=lambda r: in_progress.get(r, []),
            window_exists_fn=lambda w: False,
        )
        self.assertEqual(targets, [])

    def test_no_in_progress_returns_empty(self):
        targets = select_resume_targets(
            [self.a, self.b],
            list_in_progress_fn=lambda r: [],
            window_exists_fn=lambda w: False,
        )
        self.assertEqual(targets, [])

    def test_all_windows_present_returns_empty(self):
        in_progress = {self.a: [_mk_issue(self.a, 1, labels=[LABEL_IN_PROGRESS])]}
        targets = select_resume_targets(
            [self.a],
            list_in_progress_fn=lambda r: in_progress.get(r, []),
            window_exists_fn=lambda w: True,
        )
        self.assertEqual(targets, [])

    def test_target_repo_filter_short_name(self):
        in_progress = {
            self.a: [_mk_issue(self.a, 1, labels=[LABEL_IN_PROGRESS])],
            self.b: [_mk_issue(self.b, 2, labels=[LABEL_IN_PROGRESS])],
        }
        targets = select_resume_targets(
            [self.a, self.b], target_repo="b",
            list_in_progress_fn=lambda r: in_progress.get(r, []),
            window_exists_fn=lambda w: False,
        )
        self.assertEqual([(i.repo.full_name, i.number) for i in targets],
                         [("o/b", 2)])

    def test_target_repo_filter_full_name(self):
        in_progress = {
            self.a: [_mk_issue(self.a, 1, labels=[LABEL_IN_PROGRESS])],
            self.b: [_mk_issue(self.b, 2, labels=[LABEL_IN_PROGRESS])],
        }
        targets = select_resume_targets(
            [self.a, self.b], target_repo="o/a",
            list_in_progress_fn=lambda r: in_progress.get(r, []),
            window_exists_fn=lambda w: False,
        )
        self.assertEqual([(i.repo.full_name, i.number) for i in targets],
                         [("o/a", 1)])

    def test_target_issue_filter_across_repos(self):
        # Only issue #5 should be returned, even though repo b has #10 in
        # progress with a missing window.
        in_progress = {
            self.a: [_mk_issue(self.a, 5, labels=[LABEL_IN_PROGRESS])],
            self.b: [_mk_issue(self.b, 10, labels=[LABEL_IN_PROGRESS])],
        }
        targets = select_resume_targets(
            [self.a, self.b], target_issue=5,
            list_in_progress_fn=lambda r: in_progress.get(r, []),
            window_exists_fn=lambda w: False,
        )
        self.assertEqual([(i.repo.full_name, i.number) for i in targets],
                         [("o/a", 5)])

    def test_target_repo_and_issue_filter(self):
        in_progress = {
            self.a: [_mk_issue(self.a, 5, labels=[LABEL_IN_PROGRESS]),
                     _mk_issue(self.a, 6, labels=[LABEL_IN_PROGRESS])],
            self.b: [_mk_issue(self.b, 5, labels=[LABEL_IN_PROGRESS])],
        }
        targets = select_resume_targets(
            [self.a, self.b], target_repo="b", target_issue=5,
            list_in_progress_fn=lambda r: in_progress.get(r, []),
            window_exists_fn=lambda w: False,
        )
        self.assertEqual([(i.repo.full_name, i.number) for i in targets],
                         [("o/b", 5)])

    def test_unmatched_repo_filter_returns_empty(self):
        in_progress = {self.a: [_mk_issue(self.a, 1, labels=[LABEL_IN_PROGRESS])]}
        targets = select_resume_targets(
            [self.a, self.b], target_repo="nonexistent",
            list_in_progress_fn=lambda r: in_progress.get(r, []),
            window_exists_fn=lambda w: False,
        )
        self.assertEqual(targets, [])


class TestMainGeneralRunHonorsFilters(unittest.TestCase):
    """End-to-end check that `python3 -m u_agents.launcher --repo X` (without
    --issue, so direct-lookup is NOT entered) restricts the resume sweep
    AND the claim pick to repo X only.
    """

    def setUp(self):
        self.a = RepoConfig("o/a", "/w/a", "main", enabled=True)
        self.b = RepoConfig("o/b", "/w/b", "main", enabled=True)

    def _patched_main(self, argv, in_progress_map, ready_map):
        """Run launcher.main with all side-effects stubbed."""
        resumed: list[tuple[str, int]] = []
        claimed: list[tuple[str, int]] = []

        def fake_resume(issue, _args):
            resumed.append((issue.repo.full_name, issue.number))
            return 0

        def fake_claim(issue, _args):
            claimed.append((issue.repo.full_name, issue.number))
            return 0

        patches = [
            mock.patch.object(launcher, "find_config", return_value=Path("/dev/null")),
            mock.patch.object(launcher, "load_config", return_value=[self.a, self.b]),
            mock.patch.object(launcher, "list_in_progress_issues",
                              side_effect=lambda r: in_progress_map.get(r, [])),
            mock.patch.object(launcher, "list_ready_issues",
                              side_effect=lambda r: ready_map.get(r, [])),
            mock.patch.object(launcher, "window_exists", return_value=False),
            mock.patch.object(launcher, "dispatch_resume", side_effect=fake_resume),
            mock.patch.object(launcher, "dispatch_claim", side_effect=fake_claim),
        ]
        for p in patches:
            p.start()
        try:
            launcher_main(argv)
        finally:
            for p in patches:
                p.stop()
        return resumed, claimed

    def test_repo_filter_scopes_resume_sweep(self):
        in_progress = {
            self.a: [_mk_issue(self.a, 1, labels=[LABEL_IN_PROGRESS])],
            self.b: [_mk_issue(self.b, 2, labels=[LABEL_IN_PROGRESS])],
        }
        ready = {
            self.a: [_mk_issue(self.a, 99, labels=[LABEL_READY])],
            self.b: [_mk_issue(self.b, 100, labels=[LABEL_READY])],
        }
        resumed, claimed = self._patched_main(
            ["--repo", "a"], in_progress, ready,
        )
        # Resume sweep saw only repo a's in-progress; claim picked only a's ready.
        self.assertEqual(resumed, [("o/a", 1)])
        self.assertEqual(claimed, [("o/a", 99)])

    def test_issue_filter_scopes_resume_sweep(self):
        in_progress = {
            self.a: [_mk_issue(self.a, 5, labels=[LABEL_IN_PROGRESS]),
                     _mk_issue(self.a, 10, labels=[LABEL_IN_PROGRESS])],
            self.b: [_mk_issue(self.b, 10, labels=[LABEL_IN_PROGRESS])],
        }
        ready = {
            self.a: [_mk_issue(self.a, 5, labels=[LABEL_READY])],
        }
        resumed, claimed = self._patched_main(
            ["--issue", "5"], in_progress, ready,
        )
        # Without --repo, --issue alone still scopes both phases by number 5.
        self.assertEqual(resumed, [("o/a", 5)])
        self.assertEqual(claimed, [("o/a", 5)])


class TestDbBackedClaimFlow(unittest.TestCase):
    def setUp(self):
        self.repo = RepoConfig("o/r", "/w/r", "main")
        self.issue = _mk_issue(self.repo, 5, labels=[LABEL_READY])

    def test_db_claim_happens_before_label_swap(self):
        events = []
        db = FakeAgentRunsClient(events)

        def claim(_issue, _dry):
            events.append("label_swap")
            return True

        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists", return_value=False), \
             mock.patch("u_agents.launcher.claim_issue", side_effect=claim), \
             mock.patch("u_agents.launcher.ensure_window",
                        side_effect=lambda *_args: events.append("tmux") or "r-5"), \
             mock.patch("u_agents.launcher.post_claim_comment"), \
             mock.patch("u_agents.launcher.send_prompt",
                        side_effect=lambda *_args: events.append("prompt")):
            rc = dispatch_claim(self.issue, _args(agent_runs_client=db))

        self.assertEqual(rc, 0)
        self.assertLess(events.index("db_claim"), events.index("label_swap"))
        self.assertLess(events.index("label_swap"), events.index("tmux"))

    def test_no_tmux_if_post_claim_github_reverification_fails(self):
        db = FakeAgentRunsClient()

        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=None), \
             mock.patch("u_agents.launcher.claim_issue") as m_claim, \
             mock.patch("u_agents.launcher.ensure_window") as m_window, \
             mock.patch("u_agents.launcher.send_prompt") as m_prompt:
            rc = dispatch_claim(self.issue, _args(agent_runs_client=db))

        self.assertEqual(rc, 0)
        m_claim.assert_not_called()
        m_window.assert_not_called()
        m_prompt.assert_not_called()
        self.assertEqual(db.cancelled[0][2]["cancel_reason"],
                         "github_reverification_failed")

    def test_pm_started_is_written_after_prompt_send(self):
        events = []
        db = FakeAgentRunsClient(events)

        def claim(_issue, _dry):
            events.append("label_swap")
            return True

        def send(_window, _prompt, _dry):
            events.append("prompt_sent")

        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists", return_value=False), \
             mock.patch("u_agents.launcher.claim_issue", side_effect=claim), \
             mock.patch("u_agents.launcher.ensure_window", return_value="r-5"), \
             mock.patch("u_agents.launcher.post_claim_comment"), \
             mock.patch("u_agents.launcher.send_prompt", side_effect=send):
            rc = dispatch_claim(self.issue, _args(agent_runs_client=db))

        self.assertEqual(rc, 0)
        self.assertLess(events.index("prompt_sent"), events.index("pm_started"))


class TestDispatchClaimRollback(unittest.TestCase):
    """Fix #3: rollback labels when dispatch fails after successful claim."""

    def setUp(self):
        self.repo = RepoConfig("o/r", "/w/r", "main")
        self.issue = _mk_issue(self.repo, 5, labels=[LABEL_READY])

    def test_rollback_called_when_send_prompt_fails_after_claim(self):
        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists", return_value=False), \
             mock.patch("u_agents.launcher.claim_issue", return_value=True) as m_claim, \
             mock.patch("u_agents.launcher.ensure_window", return_value="r-5"), \
             mock.patch("u_agents.launcher.post_claim_comment"), \
             mock.patch("u_agents.launcher.send_prompt",
                        side_effect=RuntimeError("tmux blew up")), \
             mock.patch("u_agents.launcher.rollback_claim") as m_rollback:
            with self.assertRaises(RuntimeError):
                dispatch_claim(self.issue, _args())
            m_claim.assert_called_once_with(self.issue, False)
            m_rollback.assert_called_once_with(self.issue, False)

    def test_cleans_new_window_when_send_prompt_fails_after_claim(self):
        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists",
                        side_effect=[False, True]) as m_exists, \
             mock.patch("u_agents.launcher.claim_issue", return_value=True), \
             mock.patch("u_agents.launcher.ensure_window", return_value="r-5"), \
             mock.patch("u_agents.launcher.post_claim_comment"), \
             mock.patch("u_agents.launcher.send_prompt",
                        side_effect=RuntimeError("tmux blew up")), \
             mock.patch("u_agents.launcher.rollback_claim"), \
             mock.patch("u_agents.launcher.kill_window") as m_kill:
            with self.assertRaises(RuntimeError):
                dispatch_claim(self.issue, _args())
            self.assertEqual(m_exists.call_count, 2)
            m_kill.assert_called_once_with("r-5", False)

    def test_does_not_cleanup_when_no_window_was_created(self):
        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists",
                        side_effect=[False, False]), \
             mock.patch("u_agents.launcher.claim_issue", return_value=True), \
             mock.patch("u_agents.launcher.ensure_window",
                        side_effect=RuntimeError("tmux failed before create")), \
             mock.patch("u_agents.launcher.rollback_claim"), \
             mock.patch("u_agents.launcher.kill_window") as m_kill:
            with self.assertRaises(RuntimeError):
                dispatch_claim(self.issue, _args())
            m_kill.assert_not_called()

    def test_aborts_before_tmux_when_claim_swap_failed(self):
        # If labels never swapped (claim returned False), don't dispatch.
        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists", return_value=False), \
             mock.patch("u_agents.launcher.claim_issue", return_value=False), \
             mock.patch("u_agents.launcher.ensure_window") as m_window, \
             mock.patch("u_agents.launcher.rollback_claim") as m_rollback:
            rc = dispatch_claim(self.issue, _args())
            self.assertEqual(rc, 2)
            m_window.assert_not_called()
            m_rollback.assert_not_called()

    def test_claim_exception_aborts_before_tmux(self):
        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists", return_value=False), \
             mock.patch("u_agents.launcher.claim_issue",
                        side_effect=RuntimeError("claim failed")), \
             mock.patch("u_agents.launcher.ensure_window") as m_window:
            rc = dispatch_claim(self.issue, _args())
            self.assertEqual(rc, 2)
            m_window.assert_not_called()

    def test_no_rollback_on_clean_success(self):
        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists", return_value=False), \
             mock.patch("u_agents.launcher.claim_issue", return_value=True), \
             mock.patch("u_agents.launcher.ensure_window", return_value="r-5"), \
             mock.patch("u_agents.launcher.post_claim_comment"), \
             mock.patch("u_agents.launcher.send_prompt"), \
             mock.patch("u_agents.launcher.rollback_claim") as m_rollback:
            rc = dispatch_claim(self.issue, _args())
            self.assertEqual(rc, 0)
            m_rollback.assert_not_called()

    def test_existing_window_skips_dispatch_and_does_not_claim(self):
        # If a deterministic window already exists, refuse duplicate dispatch
        # and DO NOT swap labels.
        with mock.patch("u_agents.launcher.reverify_issue_ready",
                        return_value=self.issue), \
             mock.patch("u_agents.launcher.window_exists", return_value=True), \
             mock.patch("u_agents.launcher.claim_issue") as m_claim, \
             mock.patch("u_agents.launcher.send_prompt") as m_send:
            rc = dispatch_claim(self.issue, _args())
            self.assertEqual(rc, 0)
            m_claim.assert_not_called()
            m_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
