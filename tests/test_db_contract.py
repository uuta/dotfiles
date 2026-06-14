import re
import unittest
from pathlib import Path

from u_agents.control_plane import AGENT_RUN_STATUSES, RUN_PHASE_STATUSES


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "u_agents" / "db" / "001_agent_runs.sql"
DB_README = ROOT / "u_agents" / "db" / "README.md"
COMPOSE = ROOT / "u_agents" / "compose.yml"


class TestAgentRunsSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SCHEMA.read_text(encoding="utf-8")

    def test_table_and_unique_issue_key_exist(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS agent_runs", self.sql)
        self.assertIn("PRIMARY KEY DEFAULT gen_random_uuid()", self.sql)
        self.assertIn("agent_runs_repository_issue_key", self.sql)
        self.assertIn("(repository_full_name, github_issue_number)", self.sql)

    def test_required_columns_exist(self):
        for column in (
            "run_id",
            "repository_full_name",
            "github_issue_number",
            "parent_branch",
            "branch_name",
            "status",
            "runner_id",
            "machine_id",
            "locked_by",
            "lease_until",
            "worktree_basename",
            "tmux_window",
            "pm_pane",
            "review_result_relative_path",
            "pr_number",
            "pr_review_fix_rounds",
            "block_reason",
            "metadata",
            "created_at",
            "updated_at",
        ):
            with self.subTest(column=column):
                self.assertRegex(self.sql, rf"\b{column}\b")

    def test_status_check_matches_python_contract(self):
        for status in AGENT_RUN_STATUSES:
            with self.subTest(status=status):
                self.assertIn(f"'{status}'", self.sql)

    def test_removed_unused_worker_pane_columns(self):
        self.assertNotRegex(self.sql, r"\bengineer_pane\b")
        self.assertNotRegex(self.sql, r"\breviewer_pane\b")

    def test_run_phases_table_and_contract_exist(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS run_phases", self.sql)
        for column in (
            "run_phase_id",
            "agent_run_id",
            "phase_index",
            "phase_key",
            "title",
            "status",
            "metadata",
            "block_reason",
            "created_at",
            "updated_at",
        ):
            with self.subTest(column=column):
                self.assertRegex(self.sql, rf"\b{column}\b")
        for status in RUN_PHASE_STATUSES:
            with self.subTest(status=status):
                self.assertIn(f"'{status}'", self.sql)
        self.assertIn("UNIQUE (agent_run_id, phase_index)", self.sql)
        self.assertIn("UNIQUE (agent_run_id, phase_key)", self.sql)
        self.assertIn("run_phases_one_active_idx", self.sql)

    def test_constraints_cover_positive_numbers_and_non_empty_identity(self):
        self.assertIn("github_issue_number > 0", self.sql)
        self.assertIn("pr_number IS NULL OR pr_number > 0", self.sql)
        self.assertIn("pr_review_fix_rounds >= 0", self.sql)
        self.assertIn("btrim(runner_id) <> ''", self.sql)
        self.assertIn("btrim(machine_id) <> ''", self.sql)
        self.assertIn("parent_branch !~ '[[:space:]]'", self.sql)
        self.assertIn("branch_name !~ '[[:space:]]'", self.sql)
        self.assertIn("worktree_basename !~ '[[:space:]]'", self.sql)
        self.assertIn("worktree_basename !~ '[/\\\\]'", self.sql)
        self.assertIn("jsonb_typeof(metadata) = 'object'", self.sql)
        self.assertIn(
            "review_result_relative_path = 'tmp/review-result.json'",
            self.sql,
        )

    def test_constraints_cover_lease_pair_and_pr_status_integrity(self):
        self.assertIn("(locked_by IS NULL) = (lease_until IS NULL)", self.sql)
        self.assertIn(
            "status NOT IN ('pr_open', 'pr_watching', 'ready_to_merge')",
            self.sql,
        )
        self.assertIn("OR pr_number IS NOT NULL", self.sql)

    def test_updated_at_trigger_exists(self):
        self.assertIn("set_agent_runs_updated_at", self.sql)
        self.assertIn("CREATE TRIGGER agent_runs_set_updated_at", self.sql)


class TestDbDocsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = DB_README.read_text(encoding="utf-8")

    def test_docs_include_required_env(self):
        for name in ("U_AGENTS_DATABASE_URL", "U_AGENTS_RUNNER_ID", "U_AGENTS_MACHINE_ID"):
            with self.subTest(name=name):
                self.assertIn(name, self.readme)
        self.assertRegex(self.readme, r"must\s+not invent")

    def test_docs_include_all_status_values_and_transition_rules(self):
        for status in AGENT_RUN_STATUSES:
            with self.subTest(status=status):
                self.assertIn(f"`{status}`", self.readme)
        for status in RUN_PHASE_STATUSES:
            with self.subTest(run_phase_status=status):
                self.assertIn(f"`{status}`", self.readme)
        for text in (
            "GitHub Issues with `status:ready` remain the queue source of truth",
            "Only the Launcher creates or upserts the initial `agent_runs` row",
            "DB claim/lease first, then GitHub label swap",
            "review_result_relative_path",
            "Must be non-empty and contain no whitespace",
            "Must be set and cleared together with `lease_until`",
            "required for `pr_open`, `pr_watching`, and `ready_to_merge`",
            "5 minutes",
            "Automated PR review comment fixes are allowed at most once",
            "pr_review_fix_rounds = 0",
            "pr_review_fix_rounds >= 1",
            "status = 'ready_to_merge'",
            "PM creates all rows in",
            "`run_phases` once",
        ):
            with self.subTest(text=text):
                self.assertIn(text, self.readme)


class TestComposeContract(unittest.TestCase):
    def test_postgres_17_localhost_non_default_port(self):
        compose = COMPOSE.read_text(encoding="utf-8")
        self.assertIn("postgres:17", compose)
        self.assertIn('"127.0.0.1:54329:5432"', compose)
        self.assertRegex(compose, re.compile(r"POSTGRES_DB:\s*u_agents"))

    def test_db_up_task_waits_for_health(self):
        mise = (ROOT / "u_agents" / "mise.toml").read_text(encoding="utf-8")
        self.assertIn("docker compose -f compose.yml up -d --wait postgres", mise)


if __name__ == "__main__":
    unittest.main()
