import unittest
from dataclasses import replace

from u_agents.agent_runs import AgentRun
from u_agents.pr_watcher import (
    PrReality,
    check_once,
    extract_must_fix_review_comment_keys,
    reconcile_pr_run,
)


def _run(**overrides):
    base = AgentRun(
        repository_full_name="o/r",
        github_issue_number=12,
        parent_branch="main",
        branch_name="feat/12",
        phase="pr_watching",
        runner_id="runner-1",
        machine_id="machine-1",
        locked_by="runner-1@machine-1",
        lease_until="future",
        worktree_basename="12",
        tmux_window="r-12",
        pm_pane="agents:r-12.0",
        pr_number=45,
        pr_review_fix_rounds=0,
        metadata={},
    )
    return replace(base, **overrides)


def _reality(**overrides):
    base = PrReality(
        exists=True,
        pr_number=45,
        head_branch="feat/12",
        merged=False,
        ci_green=False,
        must_fix_review_comments=False,
    )
    return replace(base, **overrides)


class FakeDbClient:
    def __init__(self, runs=None):
        self.runs = list(runs or [])
        self.calls = []

    def list_pr_watch_runs(self):
        return list(self.runs)

    def mark_blocked(self, repo_full, issue_number, reason, *, metadata=None):
        self.calls.append(("blocked", repo_full, issue_number, reason, metadata or {}))
        return replace(
            self.runs[0] if self.runs else _run(),
            phase="blocked",
            block_reason=reason,
            metadata=metadata or {},
        )

    def mark_done(self, repo_full, issue_number, *, metadata=None):
        self.calls.append(("done", repo_full, issue_number, metadata or {}))
        return replace(
            self.runs[0] if self.runs else _run(),
            phase="done",
            metadata=metadata or {},
        )

    def update_pr_fields(
        self,
        repo_full,
        issue_number,
        *,
        pr_number=None,
        phase=None,
        increment_fix_rounds=False,
        block_reason=None,
        metadata=None,
    ):
        self.calls.append((
            "update_pr_fields",
            repo_full,
            issue_number,
            pr_number,
            phase,
            increment_fix_rounds,
            block_reason,
            metadata or {},
        ))
        run = self.runs[0] if self.runs else _run()
        return replace(
            run,
            pr_number=pr_number or run.pr_number,
            phase=phase or run.phase,
            pr_review_fix_rounds=(
                run.pr_review_fix_rounds + 1
                if increment_fix_rounds
                else run.pr_review_fix_rounds
            ),
            block_reason=block_reason,
            metadata=metadata or {},
        )


class TestCommentClassification(unittest.TestCase):
    def test_extracts_explicit_must_fix_comments(self):
        keys = extract_must_fix_review_comment_keys({
            "comments": [
                {"id": "c1", "body": "optional cleanup"},
                {"id": "c2", "body": "must-fix: handle missing state"},
            ],
            "latestReviews": [
                {"id": "r1", "state": "COMMENTED", "body": "already addressed"},
                {"id": "r2", "state": "CHANGES_REQUESTED", "body": "fix this"},
            ],
        })

        self.assertEqual(keys, ("comment:c2", "latest_review:r2"))


class TestPrWatcherTransitions(unittest.TestCase):
    def test_missing_pr_number_blocks(self):
        db = FakeDbClient([_run(pr_number=None)])
        updated = reconcile_pr_run(
            db.runs[0],
            _reality(exists=False, pr_number=0),
            db,
        )

        self.assertEqual(updated.phase, "blocked")
        self.assertIn("without pr_number", db.calls[0][3])

    def test_missing_pr_blocks(self):
        db = FakeDbClient([_run()])
        updated = reconcile_pr_run(db.runs[0], _reality(exists=False), db)

        self.assertEqual(updated.phase, "blocked")
        self.assertIn("does not exist", db.calls[0][3])

    def test_head_branch_mismatch_blocks(self):
        db = FakeDbClient([_run()])
        updated = reconcile_pr_run(
            db.runs[0],
            _reality(head_branch="feat/other"),
            db,
        )

        self.assertEqual(updated.phase, "blocked")
        self.assertIn("does not match", db.calls[0][3])

    def test_closed_unmerged_pr_blocks(self):
        db = FakeDbClient([_run()])
        updated = reconcile_pr_run(db.runs[0], _reality(closed=True), db)

        self.assertEqual(updated.phase, "blocked")
        self.assertIn("closed without being merged", db.calls[0][3])

    def test_merged_pr_marks_done(self):
        db = FakeDbClient([_run()])
        updated = reconcile_pr_run(
            db.runs[0],
            _reality(merged=True, closed=True),
            db,
        )

        self.assertEqual(updated.phase, "done")
        self.assertEqual(db.calls[0][0], "done")

    def test_first_must_fix_round_updates_then_assigns_fix(self):
        db = FakeDbClient([_run(pr_review_fix_rounds=0)])
        assignments = []

        updated = reconcile_pr_run(
            db.runs[0],
            _reality(
                must_fix_review_comments=True,
                must_fix_comment_keys=("comment:c1",),
            ),
            db,
            assign_fix=lambda run, reality: assignments.append(
                (run.pr_review_fix_rounds, reality.must_fix_comment_keys)
            ),
        )

        self.assertEqual(updated.phase, "fixing")
        self.assertEqual(updated.pr_review_fix_rounds, 1)
        self.assertEqual(db.calls[0][0], "update_pr_fields")
        self.assertTrue(db.calls[0][5])
        self.assertEqual(assignments, [(1, ("comment:c1",))])

    def test_second_must_fix_round_blocks_without_assignment(self):
        db = FakeDbClient([_run(pr_review_fix_rounds=1)])
        assignments = []

        updated = reconcile_pr_run(
            db.runs[0],
            _reality(must_fix_review_comments=True),
            db,
            assign_fix=lambda *_args: assignments.append("assigned"),
        )

        self.assertEqual(updated.phase, "blocked")
        self.assertEqual(assignments, [])
        self.assertEqual(db.calls[0][0], "blocked")

    def test_green_without_must_fix_is_ready_to_merge(self):
        db = FakeDbClient([_run()])
        updated = reconcile_pr_run(db.runs[0], _reality(ci_green=True), db)

        self.assertEqual(updated.phase, "ready_to_merge")
        self.assertEqual(db.calls[0][4], "ready_to_merge")

    def test_pending_ci_keeps_watching(self):
        db = FakeDbClient([_run(phase="pr_open")])
        updated = reconcile_pr_run(db.runs[0], _reality(ci_green=False), db)

        self.assertEqual(updated.phase, "pr_watching")
        self.assertEqual(db.calls[0][4], "pr_watching")

    def test_check_once_fetches_pr_reality_for_listed_runs(self):
        db = FakeDbClient([_run(phase="pr_open")])
        fetched = []

        updated = check_once(
            db,
            fetch_reality=lambda repo, pr: fetched.append((repo, pr)) or _reality(),
        )

        self.assertEqual(fetched, [("o/r", 45)])
        self.assertEqual(updated[0].phase, "pr_watching")


if __name__ == "__main__":
    unittest.main()
