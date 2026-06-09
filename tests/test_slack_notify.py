import io
import unittest
from contextlib import redirect_stderr
from dataclasses import replace

from u_agents.agent_runs import AgentRun
from u_agents.slack_notify import (
    SLACK_PR_OPEN_NOTIFIED_KEY,
    already_notified,
    build_pr_open_message,
    notify_pr_open,
    webhook_url_from_env,
)

WEBHOOK = "https://hooks.slack.example/T000/B000/secret"
WEBHOOK_ENV = {"U_AGENTS_SLACK_WEBHOOK_URL": WEBHOOK}


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
    def __init__(self):
        self.update_calls = []

    def merge_metadata(self, repo_full, issue_number, metadata):
        self.update_calls.append((repo_full, issue_number, {"metadata": metadata}))
        return _run()


class RecordingPoster:
    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    def __call__(self, url, text):
        self.calls.append((url, text))
        if self.exc is not None:
            raise self.exc


class TestWebhookUrlFromEnv(unittest.TestCase):
    def test_unset_returns_none(self):
        self.assertIsNone(webhook_url_from_env({}))

    def test_blank_returns_none(self):
        self.assertIsNone(webhook_url_from_env({"U_AGENTS_SLACK_WEBHOOK_URL": "   "}))

    def test_set_returns_stripped_value(self):
        self.assertEqual(
            webhook_url_from_env({"U_AGENTS_SLACK_WEBHOOK_URL": f"  {WEBHOOK} "}),
            WEBHOOK,
        )


class TestAlreadyNotified(unittest.TestCase):
    def test_false_without_marker(self):
        self.assertFalse(already_notified(_run(), 240))

    def test_true_when_marker_matches_pr(self):
        run = _run(metadata={SLACK_PR_OPEN_NOTIFIED_KEY: {"pr_number": 240}})
        self.assertTrue(already_notified(run, 240))

    def test_false_when_marker_is_for_other_pr(self):
        run = _run(metadata={SLACK_PR_OPEN_NOTIFIED_KEY: {"pr_number": 99}})
        self.assertFalse(already_notified(run, 240))


class TestBuildMessage(unittest.TestCase):
    def test_message_contains_required_lines(self):
        msg = build_pr_open_message(_run())
        self.assertIn("u_agents opened PR", msg)
        self.assertIn("o/r#12 -> PR #240", msg)
        self.assertIn("https://github.com/o/r/pull/240", msg)
        self.assertIn("branch: feat/12", msg)
        self.assertIn("runner: runner-1 / machine-1", msg)


class TestNotifyPrOpen(unittest.TestCase):
    def test_unset_env_is_noop(self):
        db = FakeDbClient()
        poster = RecordingPoster()

        sent = notify_pr_open(db, _run(), env={}, post=poster)

        self.assertFalse(sent)
        self.assertEqual(poster.calls, [])
        self.assertEqual(db.update_calls, [])

    def test_successful_send_posts_once_and_persists_marker(self):
        db = FakeDbClient()
        poster = RecordingPoster()

        sent = notify_pr_open(db, _run(), env=WEBHOOK_ENV, post=poster)

        self.assertTrue(sent)
        self.assertEqual(len(poster.calls), 1)
        url, text = poster.calls[0]
        self.assertEqual(url, WEBHOOK)
        self.assertIn("o/r#12 -> PR #240", text)
        self.assertEqual(len(db.update_calls), 1)
        repo_full, issue_number, kwargs = db.update_calls[0]
        self.assertEqual((repo_full, issue_number), ("o/r", 12))
        self.assertEqual(
            kwargs["metadata"], {SLACK_PR_OPEN_NOTIFIED_KEY: {"pr_number": 240}}
        )

    def test_delivery_failure_warns_and_does_not_raise(self):
        db = FakeDbClient()
        poster = RecordingPoster(exc=RuntimeError("slack down"))

        buf = io.StringIO()
        with redirect_stderr(buf):
            sent = notify_pr_open(db, _run(), env=WEBHOOK_ENV, post=poster)

        self.assertFalse(sent)
        self.assertEqual(len(poster.calls), 1)
        # Marker persisted BEFORE the (failed) send, so a later re-arm stays
        # suppressed: at-most-once is preferred over retrying an ambiguous send.
        self.assertEqual(len(db.update_calls), 1)
        self.assertEqual(
            db.update_calls[0][2]["metadata"],
            {SLACK_PR_OPEN_NOTIFIED_KEY: {"pr_number": 240}},
        )
        self.assertIn("WARN: Slack PR-open notification failed", buf.getvalue())

    def test_duplicate_suppressed_when_marker_present(self):
        db = FakeDbClient()
        poster = RecordingPoster()
        run = _run(metadata={SLACK_PR_OPEN_NOTIFIED_KEY: {"pr_number": 240}})

        sent = notify_pr_open(db, run, env=WEBHOOK_ENV, post=poster)

        self.assertFalse(sent)
        self.assertEqual(poster.calls, [])
        self.assertEqual(db.update_calls, [])

    def test_marker_persist_failure_skips_send_and_does_not_raise(self):
        class BoomDb(FakeDbClient):
            def merge_metadata(self, *_a, **_kw):
                raise RuntimeError("db down")

        poster = RecordingPoster()
        buf = io.StringIO()
        with redirect_stderr(buf):
            sent = notify_pr_open(BoomDb(), _run(), env=WEBHOOK_ENV, post=poster)

        self.assertFalse(sent)
        # Marker could not be persisted -> never call Slack (no un-suppressable
        # duplicate).
        self.assertEqual(poster.calls, [])
        self.assertIn("WARN: Slack PR-open notify marker persist failed", buf.getvalue())

    def test_marker_is_persisted_before_send(self):
        events = []

        class OrderedDb(FakeDbClient):
            def merge_metadata(self, repo_full, issue_number, metadata):
                events.append("marker")
                return super().merge_metadata(repo_full, issue_number, metadata)

        def poster(url, text):
            events.append("send")

        sent = notify_pr_open(OrderedDb(), _run(), env=WEBHOOK_ENV, post=poster)

        self.assertTrue(sent)
        self.assertEqual(events, ["marker", "send"])


if __name__ == "__main__":
    unittest.main()
