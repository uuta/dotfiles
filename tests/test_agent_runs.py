import json
import unittest
from datetime import datetime, timezone

from u_agents.agent_runs import (
    AgentRunsClient,
    ClaimPayload,
    build_claim_payload,
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

    def test_update_phase_generates_expected_update_payload(self):
        conn = FakeConn([_row(phase="engineering", metadata={"stage": "pm"})])
        client = AgentRunsClient(conn, self.identity)

        run = client.update_phase(
            "o/r",
            12,
            "engineering",
            metadata={"stage": "pm"},
        )

        self.assertEqual(run.phase, "engineering")
        sql, params = conn.calls[0]
        self.assertIn("UPDATE agent_runs", sql)
        self.assertIn("SET phase = %(phase)s", sql)
        self.assertEqual(params["phase"], "engineering")
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
        self.assertEqual(params["phase"], "pm_started")
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
        self.assertEqual(params["phase"], "fixing")
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

    def test_mark_pr_open_sets_pr_open_phase_and_number(self):
        conn = FakeConn([_row(phase="pr_open", pr_number=240)])
        client = AgentRunsClient(conn, self.identity)

        run = client.mark_pr_open("o/r", 12, pr_number=240)

        self.assertEqual(run.phase, "pr_open")
        self.assertEqual(run.pr_number, 240)
        _sql, params = conn.calls[0]
        self.assertEqual(params["phase"], "pr_open")
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

    def test_list_active_and_stale_runs_use_domain_phases(self):
        active_conn = FakeConn([_row(phase="pm_started")])
        active_client = AgentRunsClient(active_conn, self.identity)
        self.assertEqual(active_client.list_active_runs()[0].phase, "pm_started")
        active_sql, active_params = active_conn.calls[0]
        self.assertIn("phase = ANY(%(phases)s)", active_sql)
        self.assertIn("pm_started", active_params["phases"])

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


if __name__ == "__main__":
    unittest.main()
