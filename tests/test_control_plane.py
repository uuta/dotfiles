import unittest

from u_agents.contract import ConfigError
from u_agents.control_plane import (
    AGENT_RUN_PHASES,
    PR_REVIEW_FIX_MAX_ROUNDS,
    database_url_from_env,
    decide_pr_watch_phase,
    load_runner_identity,
    validate_worktree_basename,
)


class TestControlPlaneConstants(unittest.TestCase):
    def test_phase_values_are_exact(self):
        self.assertEqual(
            AGENT_RUN_PHASES,
            (
                "claimed",
                "pm_started",
                "engineering",
                "reviewing",
                "fixing",
                "pr_open",
                "pr_watching",
                "ready_to_merge",
                "blocked",
                "done",
                "cancelled",
            ),
        )
        self.assertEqual(PR_REVIEW_FIX_MAX_ROUNDS, 1)


class TestRunnerEnvironment(unittest.TestCase):
    def test_loads_runner_identity_from_env_mapping(self):
        ident = load_runner_identity({
            "U_AGENTS_RUNNER_ID": "runner-1",
            "U_AGENTS_MACHINE_ID": "machine-1",
        })
        self.assertEqual(ident.runner_id, "runner-1")
        self.assertEqual(ident.machine_id, "machine-1")
        self.assertEqual(ident.lock_owner, "runner-1@machine-1")

    def test_runner_id_is_required(self):
        with self.assertRaisesRegex(ConfigError, "U_AGENTS_RUNNER_ID"):
            load_runner_identity({"U_AGENTS_MACHINE_ID": "machine-1"})

    def test_runner_id_none_is_required(self):
        with self.assertRaisesRegex(ConfigError, "U_AGENTS_RUNNER_ID"):
            load_runner_identity({
                "U_AGENTS_RUNNER_ID": None,
                "U_AGENTS_MACHINE_ID": "machine-1",
            })

    def test_machine_id_is_required(self):
        with self.assertRaisesRegex(ConfigError, "U_AGENTS_MACHINE_ID"):
            load_runner_identity({"U_AGENTS_RUNNER_ID": "runner-1", "U_AGENTS_MACHINE_ID": " "})

    def test_database_url_is_required(self):
        with self.assertRaisesRegex(ConfigError, "U_AGENTS_DATABASE_URL"):
            database_url_from_env({"U_AGENTS_DATABASE_URL": ""})

    def test_database_url_uses_env_mapping(self):
        self.assertEqual(
            database_url_from_env({"U_AGENTS_DATABASE_URL": "postgresql://example/db"}),
            "postgresql://example/db",
        )

    def test_database_url_accepts_postgres_alias(self):
        self.assertEqual(
            database_url_from_env({"U_AGENTS_DATABASE_URL": "postgres://example/db"}),
            "postgres://example/db",
        )

    def test_database_url_rejects_invalid_scheme(self):
        with self.assertRaisesRegex(ConfigError, "postgresql:// or postgres://"):
            database_url_from_env({"U_AGENTS_DATABASE_URL": "mysql://example/db"})


class TestWorktreeBasename(unittest.TestCase):
    def test_accepts_basename(self):
        self.assertEqual(validate_worktree_basename("233"), "233")

    def test_rejects_paths(self):
        for value in ("", " ", ".", "..", "a/b", r"a\b"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_worktree_basename(value)

    def test_rejects_whitespace(self):
        for value in (" 233", "233 ", "issue 233", "issue\t233", "issue\n233"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "whitespace"):
                    validate_worktree_basename(value)


class TestPrWatchDecision(unittest.TestCase):
    def test_merged_wins(self):
        decision = decide_pr_watch_phase(
            pr_merged=True,
            ci_green=False,
            must_fix_review_comments=True,
            pr_review_fix_rounds=1,
        )
        self.assertEqual(decision.phase, "done")
        self.assertFalse(decision.increment_fix_rounds)

    def test_first_must_fix_round_goes_to_fixing_and_increments(self):
        decision = decide_pr_watch_phase(
            pr_merged=False,
            ci_green=True,
            must_fix_review_comments=True,
            pr_review_fix_rounds=0,
        )
        self.assertEqual(decision.phase, "fixing")
        self.assertTrue(decision.increment_fix_rounds)

    def test_second_must_fix_round_blocks(self):
        decision = decide_pr_watch_phase(
            pr_merged=False,
            ci_green=True,
            must_fix_review_comments=True,
            pr_review_fix_rounds=1,
        )
        self.assertEqual(decision.phase, "blocked")
        self.assertIn("must-fix", decision.block_reason)

    def test_green_without_must_fix_is_ready_to_merge(self):
        decision = decide_pr_watch_phase(
            pr_merged=False,
            ci_green=True,
            must_fix_review_comments=False,
            pr_review_fix_rounds=0,
        )
        self.assertEqual(decision.phase, "ready_to_merge")

    def test_pending_ci_without_must_fix_keeps_watching(self):
        decision = decide_pr_watch_phase(
            pr_merged=False,
            ci_green=False,
            must_fix_review_comments=False,
            pr_review_fix_rounds=0,
        )
        self.assertEqual(decision.phase, "pr_watching")

    def test_negative_round_count_is_invalid(self):
        with self.assertRaises(ValueError):
            decide_pr_watch_phase(
                pr_merged=False,
                ci_green=False,
                must_fix_review_comments=False,
                pr_review_fix_rounds=-1,
            )


if __name__ == "__main__":
    unittest.main()
