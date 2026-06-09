import io
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from unittest import mock

from u_agents.agent_runs import AgentRun
from u_agents.mark_pr_open import main, record_pr_open
from u_agents.slack_notify import SLACK_PR_OPEN_NOTIFIED_KEY

WEBHOOK = "https://hooks.slack.example/T000/B000/secret"


def _run(**overrides):
    base = AgentRun(
        repository_full_name="o/r",
        github_issue_number=12,
        parent_branch="main",
        branch_name="feat/12",
        phase="pr_open",
        runner_id="runner-1",
        machine_id="machine-1",
        locked_by="runner-1@machine-1",
        lease_until="future",
        worktree_basename="12",
        tmux_window="r-12",
        pm_pane="agents:r-12.0",
        pr_number=240,
        metadata={},
    )
    return replace(base, **overrides)


class FakeDbClient:
    def __init__(self, run=None):
        self.run = run or _run()
        self.calls = []
        self.update_calls = []
        self.closed = False

    def mark_pr_open(self, repo_full, issue_number, *, pr_number, metadata=None):
        self.calls.append(("mark_pr_open", repo_full, issue_number, pr_number, metadata))
        return replace(self.run, phase="pr_open", pr_number=pr_number)

    def update_pr_fields(self, repo_full, issue_number, **kwargs):
        self.update_calls.append((repo_full, issue_number, kwargs))
        return replace(self.run, phase="pr_open")

    def merge_metadata(self, repo_full, issue_number, metadata):
        self.update_calls.append((repo_full, issue_number, {"metadata": metadata}))
        return replace(self.run, phase="pr_open")

    def close(self):
        self.closed = True


class TestRecordPrOpen(unittest.TestCase):
    def test_delegates_to_client_mark_pr_open(self):
        db = FakeDbClient()

        run = record_pr_open(db, "o/r", 12, 240)

        self.assertEqual(run.phase, "pr_open")
        self.assertEqual(run.pr_number, 240)
        self.assertEqual(db.calls, [("mark_pr_open", "o/r", 12, 240, None)])


class TestMain(unittest.TestCase):
    # Default: Slack webhook unset so existing behaviour is unchanged.
    def setUp(self):
        patcher = mock.patch.dict(
            "os.environ", {"U_AGENTS_SLACK_WEBHOOK_URL": ""}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_main_records_pr_open_and_closes_client(self):
        db = FakeDbClient()
        with mock.patch(
            "u_agents.mark_pr_open.AgentRunsClient.from_env", return_value=db,
        ):
            rc = main(["--repo", "o/r", "--issue", "12", "--pr", "240"])

        self.assertEqual(rc, 0)
        self.assertEqual(db.calls, [("mark_pr_open", "o/r", 12, 240, None)])
        # No webhook configured -> no Slack send, no marker persisted.
        self.assertEqual(db.update_calls, [])
        self.assertTrue(db.closed)

    def test_main_closes_client_even_on_error(self):
        db = FakeDbClient()

        def boom(*_a, **_kw):
            raise RuntimeError("db down")

        db.mark_pr_open = boom
        with mock.patch(
            "u_agents.mark_pr_open.AgentRunsClient.from_env", return_value=db,
        ):
            with self.assertRaises(RuntimeError):
                main(["--repo", "o/r", "--issue", "12", "--pr", "240"])
        self.assertTrue(db.closed)

    def test_main_requires_repo_issue_and_pr(self):
        for argv in (
            ["--issue", "12", "--pr", "240"],
            ["--repo", "o/r", "--pr", "240"],
            ["--repo", "o/r", "--issue", "12"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit):
                    main(argv)

    def test_main_sends_slack_when_webhook_set(self):
        db = FakeDbClient()
        posts = []
        with mock.patch.dict(
            "os.environ", {"U_AGENTS_SLACK_WEBHOOK_URL": WEBHOOK}, clear=False
        ), mock.patch(
            "u_agents.mark_pr_open.AgentRunsClient.from_env", return_value=db,
        ), mock.patch(
            "u_agents.slack_notify.post_to_webhook",
            side_effect=lambda url, text: posts.append((url, text)),
        ):
            rc = main(["--repo", "o/r", "--issue", "12", "--pr", "240"])

        self.assertEqual(rc, 0)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][0], WEBHOOK)
        self.assertIn("o/r#12 -> PR #240", posts[0][1])
        # Dedup marker persisted before the send (marker-first ordering).
        self.assertEqual(len(db.update_calls), 1)
        self.assertEqual(
            db.update_calls[0][2]["metadata"],
            {SLACK_PR_OPEN_NOTIFIED_KEY: {"pr_number": 240}},
        )
        self.assertTrue(db.closed)

    def test_main_succeeds_when_slack_delivery_fails(self):
        db = FakeDbClient()
        buf = io.StringIO()
        with mock.patch.dict(
            "os.environ", {"U_AGENTS_SLACK_WEBHOOK_URL": WEBHOOK}, clear=False
        ), mock.patch(
            "u_agents.mark_pr_open.AgentRunsClient.from_env", return_value=db,
        ), mock.patch(
            "u_agents.slack_notify.post_to_webhook",
            side_effect=RuntimeError("slack down"),
        ), redirect_stderr(buf):
            rc = main(["--repo", "o/r", "--issue", "12", "--pr", "240"])

        # DB persistence succeeded, so the CLI still exits 0 despite Slack error.
        self.assertEqual(rc, 0)
        self.assertEqual(db.calls, [("mark_pr_open", "o/r", 12, 240, None)])
        # Dedup marker is persisted before the (failed) send, so a re-arm stays
        # suppressed and the ambiguous delivery is not retried.
        self.assertEqual(len(db.update_calls), 1)
        self.assertEqual(
            db.update_calls[0][2]["metadata"],
            {SLACK_PR_OPEN_NOTIFIED_KEY: {"pr_number": 240}},
        )
        self.assertIn("WARN: Slack PR-open notification failed", buf.getvalue())
        self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()
