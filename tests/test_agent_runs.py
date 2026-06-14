import json
import unittest
from datetime import datetime, timezone

from u_agents.agent_runs import (
    AgentRunsClient,
    ClaimPayload,
    ReviewCommentRecord,
    build_claim_payload,
    validate_comment_key,
    validate_verification_refs,
)
from u_agents.contract import REVIEW_RESULT_RELATIVE_PATH, RepoConfig
from u_agents.control_plane import RunnerIdentity


def _row(**overrides):
    base = {
        "repository_full_name": "o/r",
        "github_issue_number": 12,
        "parent_branch": "main",
        "branch_name": "feat/12",
        "phase": "claimed",
        "runner_id": "runner-1",
        "machine_id": "machine-1",
        "locked_by": "runner-1@machine-1",
        "lease_until": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "worktree_basename": "12",
        "tmux_window": "r-12",
        "pm_pane": None,
        "pr_number": None,
        "pr_review_fix_rounds": 0,
        "block_reason": None,
        "metadata": {},
    }
    base.update(overrides)
    return base


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params):
        self.conn.calls.append((sql, params))

    def fetchone(self):
        if not self.conn.rows:
            return None
        return self.conn.rows.pop(0)

    def fetchall(self):
        rows = self.conn.rows
        self.conn.rows = []
        return rows


class FakeConn:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


class TestReviewCommentValidators(unittest.TestCase):
    def test_comment_key_requires_colon_and_non_empty_parts(self):
        for bad in ("", "   ", "nocolon", ":abc", "1:", "  :  "):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    validate_comment_key(bad)

    def test_comment_key_accepts_signed_id_and_hash(self):
        # Synthetic review signals use deterministic signed ids; keep them valid.
        for good in ("3409641728:1cf66a90f911", "-123:deadbeef", "1:abc"):
            with self.subTest(good=good):
                self.assertEqual(validate_comment_key(good), good)

    def test_verification_refs_non_serializable_raises_value_error(self):
        with self.assertRaises(ValueError):
            validate_verification_refs([object()])


class TestClaimPayload(unittest.TestCase):
    def test_build_claim_payload_uses_portable_worktree_basename(self):
        repo = RepoConfig("o/r", "/workspace/r", "main")
        identity = RunnerIdentity("runner-1", "machine-1")
        payload = build_claim_payload(
            repo,
            12,
            "feat/12",
            identity,
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(payload.repository_full_name, "o/r")
        self.assertEqual(payload.github_issue_number, 12)
        self.assertEqual(payload.parent_branch, "main")
        self.assertEqual(payload.branch_name, "feat/12")
        self.assertEqual(payload.worktree_basename, "12")
        self.assertNotIn("/workspace", payload.worktree_basename)
        self.assertEqual(
            payload.review_result_relative_path,
            REVIEW_RESULT_RELATIVE_PATH,
        )

    def test_rejects_invalid_claim_payload_before_db_write(self):
        conn = FakeConn([_row()])
        client = AgentRunsClient(conn, RunnerIdentity("runner-1", "machine-1"))
        payload = ClaimPayload(
            repository_full_name="not-a-full-name",
            github_issue_number=0,
            parent_branch="main branch",
            branch_name="feat/12",
            runner_id="runner",
            machine_id="machine-1",
            locked_by="runner@machine-1",
            lease_until=datetime(2026, 1, 1, tzinfo=timezone.utc),
            worktree_basename="../12",
            tmux_window="r-12",
            review_result_relative_path="tmp/wrong.json",
        )

        with self.assertRaises(Exception):
            client.acquire_claim(payload)
        self.assertEqual(conn.calls, [])

    def test_rejects_non_contract_review_result_path_before_db_write(self):
        conn = FakeConn([_row()])
        client = AgentRunsClient(conn, RunnerIdentity("runner-1", "machine-1"))
        payload = ClaimPayload(
            repository_full_name="o/r",
            github_issue_number=12,
            parent_branch="main",
            branch_name="feat/12",
            runner_id="runner-1",
            machine_id="machine-1",
            locked_by="runner-1@machine-1",
            lease_until=datetime(2026, 1, 1, tzinfo=timezone.utc),
            worktree_basename="12",
            tmux_window="r-12",
            review_result_relative_path="tmp/other.json",
        )

        with self.assertRaisesRegex(ValueError, "tmp/review-result.json"):
            client.acquire_claim(payload)
        self.assertEqual(conn.calls, [])


class TestAgentRunsClientWrites(unittest.TestCase):
    def setUp(self):
        self.identity = RunnerIdentity("runner-1", "machine-1")

    def test_acquire_claim_generates_expected_upsert_payload(self):
        conn = FakeConn([_row()])
        client = AgentRunsClient(conn, self.identity)
        repo = RepoConfig("o/r", "/workspace/r", "main")
        payload = build_claim_payload(
            repo,
            12,
            "feat/12",
            self.identity,
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        run = client.acquire_claim(payload)

        self.assertEqual(run.repository_full_name, "o/r")
        self.assertEqual(run.github_issue_number, 12)
        self.assertEqual(conn.commits, 1)
        sql, params = conn.calls[0]
        self.assertIn("INSERT INTO agent_runs", sql)
        self.assertIn("ON CONFLICT (repository_full_name, github_issue_number)", sql)
        self.assertIn("review_result_relative_path", sql)
        self.assertEqual(params["repository_full_name"], "o/r")
        self.assertEqual(params["github_issue_number"], 12)
        self.assertEqual(params["worktree_basename"], "12")
        self.assertEqual(
            params["review_result_relative_path"],
            REVIEW_RESULT_RELATIVE_PATH,
        )

    def test_update_phase_compat_generates_status_update_payload(self):
        conn = FakeConn([_row(phase="engineering", metadata={"stage": "pm"})])
        client = AgentRunsClient(conn, self.identity)

        run = client.update_phase(
            "o/r",
            12,
            "engineering",
            metadata={"stage": "pm"},
        )

        self.assertEqual(run.phase, "engineering")
        self.assertEqual(run.status, "engineering")
        sql, params = conn.calls[0]
        self.assertIn("UPDATE agent_runs", sql)
        self.assertIn("SET status = %(status)s", sql)
        self.assertEqual(params["status"], "engineering")
        self.assertEqual(json.loads(params["metadata"]), {"stage": "pm"})
        self.assertFalse(params["clear_lease"])

    def test_update_tmux_coordinates_writes_pm_started_payload(self):
        conn = FakeConn([_row(phase="pm_started", pm_pane="agents:r-12.0")])
        client = AgentRunsClient(conn, self.identity)

        run = client.update_tmux_coordinates(
            "o/r",
            12,
            tmux_window="r-12",
            pm_pane="agents:r-12.0",
        )

        self.assertEqual(run.phase, "pm_started")
        self.assertEqual(run.pm_pane, "agents:r-12.0")
        _sql, params = conn.calls[0]
        self.assertEqual(params["status"], "pm_started")
        self.assertEqual(params["tmux_window"], "r-12")
        self.assertEqual(params["pm_pane"], "agents:r-12.0")

    def test_update_pr_fields_can_increment_once(self):
        conn = FakeConn([_row(phase="fixing", pr_number=45, pr_review_fix_rounds=1)])
        client = AgentRunsClient(conn, self.identity)

        run = client.update_pr_fields(
            "o/r",
            12,
            pr_number=45,
            phase="fixing",
            increment_fix_rounds=True,
            metadata={"pr_watcher": {"verified": True}},
        )

        self.assertEqual(run.phase, "fixing")
        self.assertEqual(run.pr_review_fix_rounds, 1)
        _sql, params = conn.calls[0]
        self.assertEqual(params["pr_number"], 45)
        self.assertEqual(params["status"], "fixing")
        self.assertTrue(params["increment_fix_rounds"])

    def test_merge_metadata_only_updates_metadata(self):
        conn = FakeConn([_row(metadata={"slack_pr_open_notified": {"pr_number": 240}})])
        client = AgentRunsClient(conn, self.identity)

        run = client.merge_metadata(
            "o/r",
            12,
            {"slack_pr_open_notified": {"pr_number": 240}},
        )

        self.assertEqual(run.metadata, {"slack_pr_open_notified": {"pr_number": 240}})
        sql, params = conn.calls[0]
        self.assertIn("SET metadata = metadata || %(metadata)s::jsonb", sql)
        self.assertNotIn("block_reason =", sql)
        self.assertEqual(
            json.loads(params["metadata"]),
            {"slack_pr_open_notified": {"pr_number": 240}},
        )

    def test_mark_pr_open_sets_pr_open_status_and_number(self):
        conn = FakeConn([_row(phase="pr_open", pr_number=240)])
        client = AgentRunsClient(conn, self.identity)

        run = client.mark_pr_open("o/r", 12, pr_number=240)

        self.assertEqual(run.phase, "pr_open")
        self.assertEqual(run.pr_number, 240)
        _sql, params = conn.calls[0]
        self.assertEqual(params["status"], "pr_open")
        self.assertEqual(params["pr_number"], 240)
        # PR-open bookkeeping must not consume a review fix round.
        self.assertFalse(params["increment_fix_rounds"])
        self.assertEqual(
            json.loads(params["metadata"]), {"pr_open": {"pr_number": 240}},
        )

    def test_mark_pr_open_internal_metadata_wins_collision(self):
        conn = FakeConn([_row(phase="pr_open", pr_number=240)])
        client = AgentRunsClient(conn, self.identity)

        client.mark_pr_open(
            "o/r",
            12,
            pr_number=240,
            metadata={"pr_open": {"pr_number": 999}, "source": "test"},
        )

        _sql, params = conn.calls[0]
        self.assertEqual(
            json.loads(params["metadata"]),
            {"source": "test", "pr_open": {"pr_number": 240}},
        )

    def test_list_active_and_stale_runs_use_domain_statuses(self):
        active_conn = FakeConn([_row(phase="pm_started")])
        active_client = AgentRunsClient(active_conn, self.identity)
        self.assertEqual(active_client.list_active_runs()[0].phase, "pm_started")
        active_sql, active_params = active_conn.calls[0]
        self.assertIn("status = ANY(%(statuses)s)", active_sql)
        self.assertIn("pm_started", active_params["statuses"])

        stale_conn = FakeConn([_row(phase="engineering")])
        stale_client = AgentRunsClient(stale_conn, self.identity)
        self.assertEqual(stale_client.list_stale_runs()[0].phase, "engineering")
        stale_sql, _stale_params = stale_conn.calls[0]
        self.assertIn("lease_until < now()", stale_sql)

    def test_list_methods_commit_after_select(self):
        # Comment 4: a bare SELECT opens a transaction in PostgreSQL; the list
        # (_fetch_all) methods must commit so the connection is left clean.
        for method in ("list_active_runs", "list_stale_runs", "list_pr_watch_runs"):
            conn = FakeConn([_row(phase="pr_watching", pr_number=45)])
            client = AgentRunsClient(conn, self.identity)
            getattr(client, method)()
            self.assertEqual(conn.commits, 1, f"{method} should commit once")


def _rc_row(**overrides):
    base = {
        "agent_run_id": "run-uuid",
        "github_comment_id": 3409641728,
        "body_hash": "1cf66a90f911",
        "comment_key": "3409641728:1cf66a90f911",
        "pr_number": 41,
        "source": "inline_review",
        "watcher_verdict": "needs_user_judgment",
        "pm_decision": None,
        "resolution_status": "unresolved",
        "original_body": "guard context.mounted",
        "original_path": "a.dart",
        "original_line": 144,
        "original_commit_sha": None,
        "handed_off_at": None,
        "resolved_at": None,
        "addressed_by_commit_sha": None,
        "verification_summary": None,
        "verification_refs": [],
    }
    base.update(overrides)
    return base


class TestReviewCommentsClient(unittest.TestCase):
    def setUp(self):
        self.identity = RunnerIdentity("runner-1", "machine-1")

    def _client(self, rows):
        return AgentRunsClient(FakeConn(rows), self.identity)

    # ----- upsert ----------------------------------------------------------

    def test_upsert_review_comment_generates_insert_select_on_conflict(self):
        conn = FakeConn([_rc_row()])
        client = AgentRunsClient(conn, self.identity)

        record = client.upsert_review_comment(
            "o/r", 41,
            github_comment_id=3409641728,
            body_hash="1cf66a90f911",
            pr_number=41,
            source="inline_review",
            watcher_verdict="needs_user_judgment",
            original_body="guard context.mounted",
            original_path="a.dart",
            original_line=144,
        )

        self.assertIsInstance(record, ReviewCommentRecord)
        self.assertEqual(record.comment_key, "3409641728:1cf66a90f911")
        self.assertEqual(record.resolution_status, "unresolved")
        self.assertEqual(conn.commits, 1)
        sql, params = conn.calls[0]
        self.assertIn("INSERT INTO review_comments", sql)
        self.assertIn("SELECT run_id", sql)
        self.assertIn("ON CONFLICT ON CONSTRAINT review_comments_pkey DO UPDATE", sql)
        self.assertIn("RETURNING", sql)
        self.assertEqual(params["github_comment_id"], 3409641728)
        self.assertEqual(params["body_hash"], "1cf66a90f911")
        self.assertEqual(params["watcher_verdict"], "needs_user_judgment")

    def test_upsert_preserves_pm_resolution_columns_on_conflict(self):
        # The duplicate comment_key must update the same row WITHOUT clobbering
        # the PM-owned resolution columns; the upsert SET clause must not touch
        # them at all.
        conn = FakeConn([_rc_row()])
        client = AgentRunsClient(conn, self.identity)
        client.upsert_review_comment(
            "o/r", 41,
            github_comment_id=1, body_hash="abc", pr_number=41,
            source="inline_review", watcher_verdict="valid_optional",
        )
        sql, _params = conn.calls[0]
        # Only the ON CONFLICT ... SET clause (before RETURNING) decides what is
        # overwritten; RETURNING legitimately lists every column.
        update_clause = sql.split("DO UPDATE", 1)[1].split("RETURNING", 1)[0]
        for owned in (
            "resolution_status",
            "pm_decision",
            "handed_off_at",
            "resolved_at",
            "addressed_by_commit_sha",
            "verification_summary",
            "verification_refs",
        ):
            with self.subTest(column=owned):
                self.assertNotIn(owned, update_clause)
        # It does refresh the watcher-observed fields and last_seen_at.
        self.assertIn("watcher_verdict = EXCLUDED.watcher_verdict", update_clause)
        self.assertIn("last_seen_at = now()", update_clause)

    def test_upsert_validates_inputs_before_db(self):
        for kwargs in (
            {"source": "bogus"},
            {"watcher_verdict": "bogus"},
            {"pr_number": 0},
            {"body_hash": "  "},
        ):
            with self.subTest(kwargs=kwargs):
                conn = FakeConn([_rc_row()])
                client = AgentRunsClient(conn, self.identity)
                base = {
                    "github_comment_id": 1,
                    "body_hash": "abc",
                    "pr_number": 41,
                    "source": "inline_review",
                    "watcher_verdict": "needs_user_judgment",
                }
                base.update(kwargs)
                with self.assertRaises(ValueError):
                    client.upsert_review_comment("o/r", 41, **base)
                self.assertEqual(conn.calls, [])

    def test_upsert_raises_when_agent_run_missing(self):
        conn = FakeConn([])  # INSERT...SELECT matched no agent_runs row
        client = AgentRunsClient(conn, self.identity)
        with self.assertRaises(RuntimeError):
            client.upsert_review_comment(
                "o/r", 41, github_comment_id=1, body_hash="abc", pr_number=41,
                source="inline_review", watcher_verdict="needs_user_judgment",
            )

    # ----- hand-off --------------------------------------------------------

    def test_mark_review_comment_handed_off_is_idempotent_coalesce(self):
        conn = FakeConn([_rc_row(handed_off_at="2026-06-14T00:00:00Z")])
        client = AgentRunsClient(conn, self.identity)
        record = client.mark_review_comment_handed_off(
            "o/r", 41, "3409641728:1cf66a90f911",
        )
        self.assertIsNotNone(record.handed_off_at)
        sql, params = conn.calls[0]
        self.assertIn("UPDATE review_comments", sql)
        self.assertIn("handed_off_at = COALESCE(rc.handed_off_at, now())", sql)
        self.assertEqual(params["comment_key"], "3409641728:1cf66a90f911")

    def test_mark_review_comment_handed_off_raises_when_missing(self):
        conn = FakeConn([])
        client = AgentRunsClient(conn, self.identity)
        with self.assertRaises(RuntimeError):
            client.mark_review_comment_handed_off("o/r", 41, "9:deadbeef")

    # ----- record resolution ----------------------------------------------

    def test_record_resolution_addressed_writes_commit_and_verification(self):
        conn = FakeConn([_rc_row(
            resolution_status="addressed", pm_decision="valid_must_fix",
            addressed_by_commit_sha="b6cd1ad",
            verification_summary="guarded; tests green", resolved_at="2026-06-14",
        )])
        client = AgentRunsClient(conn, self.identity)
        record = client.record_review_comment_resolution(
            "o/r", 41, "3409641728:1cf66a90f911",
            resolution_status="addressed", pm_decision="valid_must_fix",
            addressed_by_commit_sha="b6cd1ad",
            verification_summary="guarded; tests green",
            verification_refs=["https://ci/run/1"],
        )
        self.assertEqual(record.resolution_status, "addressed")
        sql, params = conn.calls[0]
        self.assertIn("UPDATE review_comments", sql)
        self.assertIn("resolution_status = %(resolution_status)s", sql)
        self.assertIn("WHEN %(resolution_status)s = 'unresolved' THEN NULL", sql)
        self.assertEqual(params["addressed_by_commit_sha"], "b6cd1ad")
        self.assertEqual(json.loads(params["verification_refs"]), ["https://ci/run/1"])

    def test_record_resolution_addressed_requires_commit_and_verification(self):
        for kwargs in (
            {"addressed_by_commit_sha": None, "verification_summary": "v"},
            {"addressed_by_commit_sha": "sha", "verification_summary": None},
            {"addressed_by_commit_sha": "  ", "verification_summary": "v"},
            {"addressed_by_commit_sha": "sha", "verification_summary": "   "},
        ):
            with self.subTest(kwargs=kwargs):
                conn = FakeConn([_rc_row()])
                client = AgentRunsClient(conn, self.identity)
                with self.assertRaises(ValueError):
                    client.record_review_comment_resolution(
                        "o/r", 41, "1:abc", resolution_status="addressed", **kwargs,
                    )
                self.assertEqual(conn.calls, [])

    def test_record_resolution_rejected_and_judgment_require_reason(self):
        for status in ("rejected", "needs_user_judgment"):
            with self.subTest(status=status):
                conn = FakeConn([_rc_row()])
                client = AgentRunsClient(conn, self.identity)
                with self.assertRaises(ValueError):
                    client.record_review_comment_resolution(
                        "o/r", 41, "1:abc", resolution_status=status,
                        verification_summary=None,
                    )
                self.assertEqual(conn.calls, [])

    def test_record_resolution_rejects_non_list_verification_refs(self):
        conn = FakeConn([_rc_row()])
        client = AgentRunsClient(conn, self.identity)
        with self.assertRaises(ValueError):
            client.record_review_comment_resolution(
                "o/r", 41, "1:abc", resolution_status="rejected",
                verification_summary="reason", verification_refs="not-a-list",
            )
        self.assertEqual(conn.calls, [])

    def test_record_resolution_rejects_unknown_status_and_decision(self):
        conn = FakeConn([_rc_row()])
        client = AgentRunsClient(conn, self.identity)
        with self.assertRaises(ValueError):
            client.record_review_comment_resolution(
                "o/r", 41, "1:abc", resolution_status="bogus",
            )
        with self.assertRaises(ValueError):
            client.record_review_comment_resolution(
                "o/r", 41, "1:abc", resolution_status="rejected",
                pm_decision="bogus", verification_summary="reason",
            )

    def test_record_resolution_raises_when_missing(self):
        conn = FakeConn([])
        client = AgentRunsClient(conn, self.identity)
        with self.assertRaises(RuntimeError):
            client.record_review_comment_resolution(
                "o/r", 41, "9:deadbeef", resolution_status="rejected",
                verification_summary="reason",
            )

    def test_list_review_comments_joins_and_commits(self):
        conn = FakeConn([_rc_row(), _rc_row(comment_key="2:def", github_comment_id=2)])
        client = AgentRunsClient(conn, self.identity)
        records = client.list_review_comments("o/r", 41)
        self.assertEqual(len(records), 2)
        self.assertEqual(conn.commits, 1)
        sql, _params = conn.calls[0]
        self.assertIn("FROM review_comments", sql)
        self.assertIn("JOIN agent_runs", sql)


if __name__ == "__main__":
    unittest.main()
