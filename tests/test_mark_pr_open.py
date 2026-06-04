import unittest
from dataclasses import replace
from unittest import mock

from u_agents.agent_runs import AgentRun
from u_agents.mark_pr_open import main, record_pr_open


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
        self.closed = False

    def mark_pr_open(self, repo_full, issue_number, *, pr_number, metadata=None):
        self.calls.append(("mark_pr_open", repo_full, issue_number, pr_number, metadata))
        return replace(self.run, phase="pr_open", pr_number=pr_number)

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
    def test_main_records_pr_open_and_closes_client(self):
        db = FakeDbClient()
        with mock.patch(
            "u_agents.mark_pr_open.AgentRunsClient.from_env", return_value=db,
        ):
            rc = main(["--repo", "o/r", "--issue", "12", "--pr", "240"])

        self.assertEqual(rc, 0)
        self.assertEqual(db.calls, [("mark_pr_open", "o/r", 12, 240, None)])
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


if __name__ == "__main__":
    unittest.main()
