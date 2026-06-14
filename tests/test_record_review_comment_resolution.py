import io
import unittest
from contextlib import redirect_stderr
from unittest import mock

from u_agents.agent_runs import ReviewCommentRecord
from u_agents.record_review_comment_resolution import main, record_resolution


def _record(**overrides):
    base = dict(
        agent_run_id="run-uuid",
        github_comment_id=3409641728,
        body_hash="1cf66a90f911",
        comment_key="3409641728:1cf66a90f911",
        pr_number=41,
        source="inline_review",
        watcher_verdict="needs_user_judgment",
        resolution_status="addressed",
        pm_decision="valid_must_fix",
        addressed_by_commit_sha="b6cd1ad",
        verification_summary="guarded; tests green",
        verification_refs=[],
    )
    base.update(overrides)
    return ReviewCommentRecord(**base)


class FakeDbClient:
    def __init__(self, record=None):
        self.record = record or _record()
        self.calls = []
        self.closed = False

    def record_review_comment_resolution(self, repo, issue, comment_key, **kwargs):
        self.calls.append((repo, issue, comment_key, kwargs))
        return self.record

    def close(self):
        self.closed = True


class TestRecordResolution(unittest.TestCase):
    def test_delegates_to_client(self):
        db = FakeDbClient()
        rec = record_resolution(
            db, "o/r", 41, "3409641728:1cf66a90f911",
            resolution_status="addressed", pm_decision="valid_must_fix",
            addressed_by_commit_sha="b6cd1ad",
            verification_summary="guarded; tests green",
            verification_refs=["https://ci/run/1"],
        )
        self.assertEqual(rec.resolution_status, "addressed")
        self.assertEqual(len(db.calls), 1)
        repo, issue, key, kwargs = db.calls[0]
        self.assertEqual((repo, issue, key), ("o/r", 41, "3409641728:1cf66a90f911"))
        self.assertEqual(kwargs["resolution_status"], "addressed")
        self.assertEqual(kwargs["addressed_by_commit_sha"], "b6cd1ad")
        self.assertEqual(kwargs["verification_refs"], ["https://ci/run/1"])


class TestMain(unittest.TestCase):
    def _run_main(self, argv, db=None):
        db = db or FakeDbClient()
        with mock.patch(
            "u_agents.record_review_comment_resolution.AgentRunsClient.from_env",
            return_value=db,
        ), redirect_stderr(io.StringIO()):
            rc = main(argv)
        return rc, db

    def test_addressed_records_and_closes_client(self):
        rc, db = self._run_main([
            "--repo", "o/r", "--issue", "41",
            "--comment-key", "3409641728:1cf66a90f911",
            "--resolution-status", "addressed",
            "--pm-decision", "valid_must_fix",
            "--commit-sha", "b6cd1ad",
            "--verification-summary", "guarded; tests green",
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(len(db.calls), 1)
        _repo, _issue, key, kwargs = db.calls[0]
        self.assertEqual(key, "3409641728:1cf66a90f911")
        self.assertEqual(kwargs["resolution_status"], "addressed")
        self.assertEqual(kwargs["addressed_by_commit_sha"], "b6cd1ad")
        self.assertTrue(db.closed)

    def test_verification_ref_is_repeatable(self):
        rc, db = self._run_main([
            "--repo", "o/r", "--issue", "41", "--comment-key", "1:abc",
            "--resolution-status", "rejected",
            "--verification-summary", "contradicts spec",
            "--verification-ref", "https://a", "--verification-ref", "https://b",
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(db.calls[0][3]["verification_refs"], ["https://a", "https://b"])

    def test_addressed_requires_commit_sha(self):
        with self.assertRaises(SystemExit):
            self._run_main([
                "--repo", "o/r", "--issue", "41", "--comment-key", "1:abc",
                "--resolution-status", "addressed",
                "--verification-summary", "done",
            ])

    def test_addressed_requires_verification_summary(self):
        with self.assertRaises(SystemExit):
            self._run_main([
                "--repo", "o/r", "--issue", "41", "--comment-key", "1:abc",
                "--resolution-status", "addressed", "--commit-sha", "sha",
            ])

    def test_rejected_requires_reason(self):
        with self.assertRaises(SystemExit):
            self._run_main([
                "--repo", "o/r", "--issue", "41", "--comment-key", "1:abc",
                "--resolution-status", "rejected",
            ])

    def test_needs_user_judgment_requires_reason(self):
        with self.assertRaises(SystemExit):
            self._run_main([
                "--repo", "o/r", "--issue", "41", "--comment-key", "1:abc",
                "--resolution-status", "needs_user_judgment",
            ])

    def test_invalid_request_does_not_open_db_connection(self):
        # p.error exits before AgentRunsClient.from_env is called.
        with mock.patch(
            "u_agents.record_review_comment_resolution.AgentRunsClient.from_env",
            side_effect=AssertionError("must not connect on invalid args"),
        ), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main([
                    "--repo", "o/r", "--issue", "41", "--comment-key", "1:abc",
                    "--resolution-status", "addressed",
                ])

    def test_requires_repo_issue_key_and_status(self):
        for argv in (
            ["--issue", "41", "--comment-key", "1:abc", "--resolution-status", "rejected",
             "--verification-summary", "r"],
            ["--repo", "o/r", "--comment-key", "1:abc", "--resolution-status", "rejected",
             "--verification-summary", "r"],
            ["--repo", "o/r", "--issue", "41", "--resolution-status", "rejected",
             "--verification-summary", "r"],
            ["--repo", "o/r", "--issue", "41", "--comment-key", "1:abc",
             "--verification-summary", "r"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit):
                    main(argv)

    def test_invalid_comment_key_format_rejected_before_db_connection(self):
        # A comment key missing the 'github_comment_id:body_hash' colon shape is
        # rejected by the pre-DB validation block (exit 2) before from_env runs.
        with mock.patch(
            "u_agents.record_review_comment_resolution.AgentRunsClient.from_env",
            side_effect=AssertionError("must not connect on invalid comment key"),
        ), redirect_stderr(io.StringIO()):
            for bad_key in ("nocolon", ":abc", "1:", "  :  "):
                with self.subTest(bad_key=bad_key):
                    with self.assertRaises(SystemExit):
                        main([
                            "--repo", "o/r", "--issue", "41",
                            "--comment-key", bad_key,
                            "--resolution-status", "rejected",
                            "--verification-summary", "reason",
                        ])

    def test_unknown_resolution_status_is_rejected_by_argparse(self):
        with self.assertRaises(SystemExit):
            main([
                "--repo", "o/r", "--issue", "41", "--comment-key", "1:abc",
                "--resolution-status", "bogus",
            ])


if __name__ == "__main__":
    unittest.main()
