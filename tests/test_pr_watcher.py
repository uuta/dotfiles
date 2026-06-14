import json
import subprocess
import sys
import unittest
from dataclasses import replace
from unittest import mock

from u_agents.agent_runs import AgentRun
from u_agents.pr_watcher import (
    PR_VIEW_JSON_FIELDS,
    REVIEW_VERDICTS,
    PrReality,
    ReviewComment,
    _status_checks_green,
    build_fix_prompt,
    build_validation_handoff_prompt,
    check_once,
    default_validate_comment,
    extract_must_fix_review_comment_keys,
    fetch_pr_reality,
    fetch_review_comments,
    live_dispatch_handoff,
    mark_pr_open_command,
    reconcile_pr_run,
    triage_review_comments,
)


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr,
    )


def _inline_proc(items=None):
    """A successful `gh api .../comments` response (a JSON array)."""
    return _completed(returncode=0, stdout=json.dumps(items or []))


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
        status=None,
        phase=None,
        increment_fix_rounds=False,
        block_reason=None,
        metadata=None,
    ):
        phase = phase or status
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


class TestStatusChecksGreen(unittest.TestCase):
    """Comment 1: support both CheckRun and StatusContext rollup entries."""

    def test_checkrun_completed_success_is_green(self):
        self.assertTrue(_status_checks_green([
            {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
        ]))

    def test_checkrun_in_progress_is_not_green(self):
        self.assertFalse(_status_checks_green([
            {"__typename": "CheckRun", "status": "IN_PROGRESS", "conclusion": None},
        ]))

    def test_classic_status_context_success_is_green(self):
        self.assertTrue(_status_checks_green([
            {"__typename": "StatusContext", "context": "ci/circleci", "state": "SUCCESS"},
        ]))

    def test_classic_status_context_pending_is_not_green(self):
        self.assertFalse(_status_checks_green([
            {"__typename": "StatusContext", "context": "ci/circleci", "state": "PENDING"},
        ]))

    def test_classic_status_context_failure_is_not_green(self):
        self.assertFalse(_status_checks_green([
            {"__typename": "StatusContext", "context": "ci/circleci", "state": "FAILURE"},
        ]))

    def test_classic_status_context_error_is_not_green(self):
        self.assertFalse(_status_checks_green([
            {"__typename": "StatusContext", "context": "ci/circleci", "state": "ERROR"},
        ]))

    def test_mixed_checkrun_and_status_context_all_green(self):
        self.assertTrue(_status_checks_green([
            {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SKIPPED"},
            {"__typename": "StatusContext", "context": "ci/x", "state": "SUCCESS"},
        ]))

    def test_mixed_with_failing_classic_status_is_not_green(self):
        self.assertFalse(_status_checks_green([
            {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "StatusContext", "context": "ci/x", "state": "FAILURE"},
        ]))

    def test_empty_or_non_list_is_not_green(self):
        self.assertFalse(_status_checks_green([]))
        self.assertFalse(_status_checks_green(None))


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

    def test_superseded_historical_review_is_ignored(self):
        # Comment 2: an old CHANGES_REQUESTED review that was later superseded by
        # an APPROVED latest review must not keep the PR classified as must-fix.
        keys = extract_must_fix_review_comment_keys({
            "comments": [],
            "reviews": [
                {"id": "r1", "state": "CHANGES_REQUESTED", "body": "fix this"},
                {"id": "r1b", "state": "APPROVED", "body": "lgtm now"},
            ],
            "latestReviews": [
                {"id": "r1b", "state": "APPROVED", "body": "lgtm now"},
            ],
        })

        self.assertEqual(keys, ())

    def test_latest_changes_requested_still_classified(self):
        keys = extract_must_fix_review_comment_keys({
            "comments": [],
            "reviews": [
                {"id": "r1", "state": "APPROVED", "body": "lgtm"},
            ],
            "latestReviews": [
                {"id": "r2", "state": "CHANGES_REQUESTED", "body": "needs work"},
            ],
        })

        self.assertEqual(keys, ("latest_review:r2",))


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
        # A validated must-fix comment (validator returns valid_must_fix) drives
        # the first fix round. The legacy must_fix_review_comments flag alone
        # must NOT trigger fixing (it is routed through validation instead).
        db = FakeDbClient([_run(pr_review_fix_rounds=0)])
        c = ReviewComment(comment_id="c1", body="please fix", source="inline")
        assignments = []

        updated = reconcile_pr_run(
            db.runs[0],
            _reality(review_comments=(c,)),
            db,
            assign_fix=lambda run, reality: assignments.append(
                run.pr_review_fix_rounds
            ),
            validate_comment=lambda _c: "valid_must_fix",
        )

        self.assertEqual(updated.phase, "fixing")
        self.assertEqual(updated.pr_review_fix_rounds, 1)
        self.assertEqual(db.calls[0][0], "update_pr_fields")
        self.assertTrue(db.calls[0][5])
        self.assertEqual(assignments, [1])

    def test_second_must_fix_round_blocks_without_assignment(self):
        # Round cap: a fresh validated must-fix with the budget exhausted blocks.
        db = FakeDbClient([_run(pr_review_fix_rounds=1)])
        c = ReviewComment(comment_id="c1", body="please fix", source="inline")
        assignments = []

        updated = reconcile_pr_run(
            db.runs[0],
            _reality(review_comments=(c,)),
            db,
            assign_fix=lambda *_args: assignments.append("assigned"),
            validate_comment=lambda _c: "valid_must_fix",
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

    def test_check_once_defers_run_on_transient_fetch_error(self):
        # Comment 3: a transient fetch failure must not block the run; it is
        # skipped this pass and retried later, never marked blocked.
        db = FakeDbClient([_run(phase="pr_open")])

        def boom(_repo, _pr):
            raise RuntimeError("transient github outage")

        updated = check_once(db, fetch_reality=boom)

        self.assertEqual(updated, [])
        self.assertEqual(db.calls, [])


class TestFetchPrReality(unittest.TestCase):
    """Comment 3: definitive not-found vs transient/parse failures."""

    def test_definitive_not_found_returns_exists_false(self):
        proc = _completed(
            returncode=1,
            stderr="GraphQL: Could not resolve to a PullRequest with the number of 999.",
        )
        with mock.patch("u_agents.pr_watcher._run", return_value=proc):
            reality = fetch_pr_reality("o/r", 999)

        self.assertFalse(reality.exists)
        self.assertEqual(reality.pr_number, 999)

    def test_transient_failure_raises_runtime_error(self):
        proc = _completed(
            returncode=1,
            stderr="error connecting to api.github.com: dial tcp: i/o timeout",
        )
        with mock.patch("u_agents.pr_watcher._run", return_value=proc):
            with self.assertRaises(RuntimeError):
                fetch_pr_reality("o/r", 45)

    def test_dns_resolution_failure_is_transient_not_absence(self):
        # "Could not resolve host" is a DNS/network error, not a missing PR.
        proc = _completed(
            returncode=1, stderr="Could not resolve host: api.github.com",
        )
        with mock.patch("u_agents.pr_watcher._run", return_value=proc):
            with self.assertRaises(RuntimeError):
                fetch_pr_reality("o/r", 45)

    def test_malformed_json_raises_runtime_error(self):
        proc = _completed(returncode=0, stdout="<html>500</html>")
        with mock.patch("u_agents.pr_watcher._run", return_value=proc):
            with self.assertRaises(RuntimeError):
                fetch_pr_reality("o/r", 45)

    def test_valid_payload_parses_into_reality(self):
        payload = json.dumps({
            "number": 45,
            "headRefName": "feat/12",
            "state": "OPEN",
            "merged": False,
            "statusCheckRollup": [
                {"__typename": "StatusContext", "context": "ci", "state": "SUCCESS"},
            ],
            "reviewDecision": None,
            "comments": [],
            "latestReviews": [],
        })
        with mock.patch(
            "u_agents.pr_watcher._run",
            side_effect=[_completed(returncode=0, stdout=payload), _inline_proc()],
        ):
            reality = fetch_pr_reality("o/r", 45)

        self.assertTrue(reality.exists)
        self.assertEqual(reality.pr_number, 45)
        self.assertEqual(reality.head_branch, "feat/12")
        self.assertTrue(reality.ci_green)
        self.assertFalse(reality.must_fix_review_comments)


class TestGhFieldCompatibility(unittest.TestCase):
    """The current gh CLI has no `merged` JSON field; requesting it errors with
    `Unknown JSON field: "merged"`. The watcher must only ask for supported
    fields and infer merged/closed/open from `state`/`mergedAt`.
    """

    @staticmethod
    def _payload(**overrides):
        base = {
            "number": 45,
            "headRefName": "feat/12",
            "state": "OPEN",
            "mergedAt": None,
            "statusCheckRollup": [],
            "reviewDecision": None,
            "comments": [],
            "latestReviews": [],
        }
        base.update(overrides)
        return json.dumps(base)

    def _captured_json_fields(self):
        """Run fetch_pr_reality and return the parsed `--json` field set.

        fetch_pr_reality issues more than one gh call (pr view + inline review
        comments), so scan all calls for the one carrying `--json`.
        """
        captured = {"cmds": []}

        def fake_run(cmd):
            captured["cmds"].append(cmd)
            if "api" in cmd:
                return _inline_proc()
            return _completed(returncode=0, stdout=self._payload())

        with mock.patch("u_agents.pr_watcher._run", side_effect=fake_run):
            fetch_pr_reality("o/r", 45)
        pr_view_cmds = [c for c in captured["cmds"] if "--json" in c]
        cmd = pr_view_cmds[0]
        idx = cmd.index("--json")
        return set(cmd[idx + 1].split(","))

    def test_does_not_request_unsupported_merged_field(self):
        fields = self._captured_json_fields()
        # `merged` is a substring of `mergedAt`, so compare the exact field set.
        self.assertNotIn("merged", fields)

    def test_requests_supported_merge_state_fields(self):
        fields = self._captured_json_fields()
        self.assertIn("mergedAt", fields)
        self.assertIn("state", fields)
        # The module constant and the actual request must stay in sync.
        self.assertEqual(fields, set(PR_VIEW_JSON_FIELDS))

    def test_module_field_list_excludes_merged(self):
        self.assertNotIn("merged", PR_VIEW_JSON_FIELDS)
        self.assertIn("mergedAt", PR_VIEW_JSON_FIELDS)

    def test_merged_state_infers_merged_true(self):
        proc = _completed(returncode=0, stdout=self._payload(state="MERGED"))
        with mock.patch(
            "u_agents.pr_watcher._run", side_effect=[proc, _inline_proc()],
        ):
            reality = fetch_pr_reality("o/r", 45)
        self.assertTrue(reality.merged)
        self.assertFalse(reality.closed)

    def test_merged_at_timestamp_infers_merged_true(self):
        proc = _completed(
            returncode=0,
            stdout=self._payload(state="MERGED", mergedAt="2026-01-01T00:00:00Z"),
        )
        with mock.patch(
            "u_agents.pr_watcher._run", side_effect=[proc, _inline_proc()],
        ):
            reality = fetch_pr_reality("o/r", 45)
        self.assertTrue(reality.merged)

    def test_closed_unmerged_state_infers_closed(self):
        proc = _completed(returncode=0, stdout=self._payload(state="CLOSED"))
        with mock.patch(
            "u_agents.pr_watcher._run", side_effect=[proc, _inline_proc()],
        ):
            reality = fetch_pr_reality("o/r", 45)
        self.assertFalse(reality.merged)
        self.assertTrue(reality.closed)

    def test_open_state_is_neither_merged_nor_closed(self):
        proc = _completed(returncode=0, stdout=self._payload(state="OPEN"))
        with mock.patch(
            "u_agents.pr_watcher._run", side_effect=[proc, _inline_proc()],
        ):
            reality = fetch_pr_reality("o/r", 45)
        self.assertFalse(reality.merged)
        self.assertFalse(reality.closed)


class TestInlineReviewCommentCollection(unittest.TestCase):
    """Inline PR review comments (per-file/line) come from a separate gh API
    call, not `gh pr view`. They must be represented in PrReality."""

    @staticmethod
    def _pr_view(**overrides):
        base = {
            "number": 45, "headRefName": "feat/12", "state": "OPEN",
            "mergedAt": None, "statusCheckRollup": [], "reviewDecision": None,
            "comments": [], "latestReviews": [],
        }
        base.update(overrides)
        return _completed(returncode=0, stdout=json.dumps(base))

    def test_inline_review_comments_collected_into_reality(self):
        inline = [{
            "id": 3348968705,
            "body": "`ref.read` after `await purchaseNotifier.purchaseProduct()` "
                    "should be guarded with `context.mounted`.",
            "path": "lib/views/organisms/purchases/purchase_offer_view.dart",
            "line": 144,
            "user": {"login": "gemini-code-assist[bot]", "type": "Bot"},
        }]
        with mock.patch(
            "u_agents.pr_watcher._run",
            side_effect=[self._pr_view(), _completed(0, json.dumps(inline))],
        ):
            reality = fetch_pr_reality("o/r", 45)

        inline_cs = [c for c in reality.review_comments if c.source == "inline"]
        self.assertEqual(len(inline_cs), 1)
        c = inline_cs[0]
        self.assertEqual(c.comment_id, "3348968705")
        self.assertEqual(
            c.path, "lib/views/organisms/purchases/purchase_offer_view.dart",
        )
        self.assertEqual(c.line, 144)
        self.assertEqual(c.author_type, "Bot")

    def test_inline_fetch_api_failure_raises_transient(self):
        # An inline-comment API failure is ambiguous (the PR exists), so it must
        # raise so check_once defers instead of proceeding as if there were no
        # inline comments to validate.
        with mock.patch(
            "u_agents.pr_watcher._run",
            side_effect=[self._pr_view(), _completed(returncode=1, stderr="boom")],
        ):
            with self.assertRaises(RuntimeError):
                fetch_pr_reality("o/r", 45)

    def test_inline_fetch_malformed_json_raises(self):
        with mock.patch(
            "u_agents.pr_watcher._run",
            side_effect=[self._pr_view(), _completed(0, "<html>500</html>")],
        ):
            with self.assertRaises(RuntimeError):
                fetch_pr_reality("o/r", 45)

    def test_fetch_review_comments_raises_on_non_list(self):
        with mock.patch(
            "u_agents.pr_watcher._run",
            return_value=_completed(0, json.dumps({"message": "Not Found"})),
        ):
            with self.assertRaises(RuntimeError):
                fetch_review_comments("o/r", 45)

    def test_check_once_defers_when_inline_fetch_raises(self):
        # Failure to confirm inline comments must not mutate DB state.
        db = FakeDbClient([_run(phase="ready_to_merge")])

        def boom(_repo, _pr):
            raise RuntimeError("gh api inline review comments failed")

        updated = check_once(db, fetch_reality=boom)
        self.assertEqual(updated, [])
        self.assertEqual(db.calls, [])


class TestDefaultValidationGate(unittest.TestCase):
    def test_high_priority_bot_comment_is_not_auto_valid_must_fix(self):
        # A Gemini-style high-priority inline comment must be collected but the
        # runtime must NOT classify it valid_must_fix from styling/author alone.
        c = ReviewComment(
            comment_id="3348968705",
            body="![high priority](badge.svg) `ref.read` after `await` should be "
                 "guarded with `context.mounted`.",
            source="inline", path="x.dart", line=144,
            author="gemini-code-assist[bot]", author_type="Bot",
        )
        verdict = default_validate_comment(c)
        self.assertIn(verdict, REVIEW_VERDICTS)
        self.assertNotEqual(verdict, "valid_must_fix")

    def test_default_never_returns_valid_must_fix(self):
        for body in (
            "must-fix: handle missing state",
            "this is blocking",
            "changes requested",
            "just a thought",
        ):
            c = ReviewComment(comment_id="1", body=body, source="inline")
            self.assertNotEqual(default_validate_comment(c), "valid_must_fix")

    def test_optional_and_resolved_markers(self):
        opt = ReviewComment(comment_id="1", body="nit: rename this", source="inline")
        done = ReviewComment(comment_id="2", body="already addressed", source="inline")
        self.assertEqual(default_validate_comment(opt), "valid_optional")
        self.assertEqual(default_validate_comment(done), "invalid")

    def test_plain_actionable_comment_escalates_not_optional(self):
        # Stricter default stance: a substantive inline comment with no marker
        # text must reach the PM validation gate (needs_user_judgment), not be
        # silently downgraded to valid_optional and skipped.
        for body in (
            "please rename this variable to be clearer",
            "consider extracting this block into a helper",
            "this loop reallocates on every iteration",
            "just a thought",
        ):
            with self.subTest(body=body):
                c = ReviewComment(comment_id="1", body=body, source="inline")
                self.assertEqual(
                    default_validate_comment(c), "needs_user_judgment",
                )

    def test_only_explicit_optional_or_empty_is_optional(self):
        # valid_optional from the runtime default is reserved for explicitly
        # optional markers and bodyless reviews; nothing else short-circuits.
        for body, expected in (
            ("nit: rename this", "valid_optional"),
            ("optional: tidy up later", "valid_optional"),
            ("non-blocking suggestion", "valid_optional"),
            ("", "valid_optional"),
            ("guard context.mounted here", "needs_user_judgment"),
        ):
            with self.subTest(body=body):
                c = ReviewComment(comment_id="1", body=body, source="inline")
                self.assertEqual(default_validate_comment(c), expected)

    def test_bot_plain_comment_still_escalates_never_auto_fix(self):
        # Safety preserved: a bot/high-priority comment is still routed through
        # validation, never auto-classified valid_must_fix by the runtime.
        c = ReviewComment(
            comment_id="9", body="guard context.mounted here", source="inline",
            author="gemini-code-assist[bot]", author_type="Bot",
        )
        verdict = default_validate_comment(c)
        self.assertEqual(verdict, "needs_user_judgment")
        self.assertNotEqual(verdict, "valid_must_fix")


class TestReviewCommentTriage(unittest.TestCase):
    def _c(self, body="please fix this", cid="111"):
        return ReviewComment(comment_id=cid, body=body, source="inline", path="a.dart", line=1)

    def test_valid_must_fix_is_actionable_when_unattempted(self):
        c = self._c()
        t = triage_review_comments([c], {}, lambda _c: "valid_must_fix")
        self.assertIn(c.stable_key, t.actionable_keys)
        self.assertEqual(t.bookkeeping[c.stable_key]["verdict"], "valid_must_fix")
        self.assertFalse(t.bookkeeping[c.stable_key]["attempted"])

    def test_attempted_key_is_not_actionable_again(self):
        c = self._c()
        prior = {c.stable_key: {"verdict": "valid_must_fix", "attempted": True}}
        t = triage_review_comments([c], prior, lambda _c: "valid_must_fix")
        self.assertEqual(t.actionable_keys, [])
        # attempted state is preserved.
        self.assertTrue(t.bookkeeping[c.stable_key]["attempted"])

    def test_changed_body_becomes_new_candidate(self):
        c1 = self._c(body="old body")
        prior = {c1.stable_key: {"verdict": "valid_must_fix", "attempted": True}}
        c2 = self._c(body="new different body")  # same id, new body -> new key
        self.assertNotEqual(c1.stable_key, c2.stable_key)
        t = triage_review_comments([c2], prior, lambda _c: "valid_must_fix")
        self.assertIn(c2.stable_key, t.actionable_keys)
        self.assertFalse(t.bookkeeping[c2.stable_key]["attempted"])

    def test_invalid_and_optional_are_not_actionable(self):
        ci = self._c(body="resolved already", cid="1")
        co = self._c(body="nit", cid="2")
        t = triage_review_comments(
            [ci, co], {},
            lambda c: "invalid" if c.comment_id == "1" else "valid_optional",
        )
        self.assertEqual(t.actionable_keys, [])
        self.assertEqual(t.needs_judgment_keys, [])
        self.assertIn(ci.stable_key, t.invalid_keys)
        self.assertIn(co.stable_key, t.optional_keys)

    def test_needs_user_judgment_collected(self):
        c = self._c()
        t = triage_review_comments([c], {}, lambda _c: "needs_user_judgment")
        self.assertIn(c.stable_key, t.needs_judgment_keys)
        self.assertEqual(t.actionable_keys, [])


class TestValidatedCommentReconcile(unittest.TestCase):
    def _inline(self, cid="111", body="please fix this", **o):
        return ReviewComment(
            comment_id=cid, body=body, source="inline", path="a.dart", line=1, **o,
        )

    def test_validated_must_fix_triggers_one_fix_attempt(self):
        db = FakeDbClient([_run(pr_review_fix_rounds=0)])
        c = self._inline()
        assignments = []

        updated = reconcile_pr_run(
            db.runs[0],
            _reality(review_comments=(c,)),
            db,
            assign_fix=lambda run, reality: assignments.append(reality),
            validate_comment=lambda _c: "valid_must_fix",
        )

        self.assertEqual(updated.phase, "fixing")
        self.assertEqual(updated.pr_review_fix_rounds, 1)
        self.assertEqual(len(assignments), 1)
        self.assertEqual(db.calls[0][0], "update_pr_fields")
        self.assertTrue(db.calls[0][5])  # increment_fix_rounds
        meta = db.calls[0][-1]
        entry = meta["pr_review_comments"][c.stable_key]
        self.assertEqual(entry["verdict"], "valid_must_fix")
        self.assertTrue(entry["attempted"])

    def test_same_comment_not_fixed_twice_and_not_ready_to_merge(self):
        # Finding 2: a valid must-fix already attempted once and still present
        # must NOT slip to ready_to_merge even with green CI, and must NOT get a
        # second fix; it escalates to a human instead.
        c = self._inline()
        run = _run(
            pr_review_fix_rounds=1,
            metadata={"pr_review_comments": {
                c.stable_key: {"verdict": "valid_must_fix", "attempted": True},
            }},
        )
        db = FakeDbClient([run])
        assignments = []

        updated = reconcile_pr_run(
            run,
            _reality(review_comments=(c,), ci_green=True),
            db,
            assign_fix=lambda *a: assignments.append(a),
            validate_comment=lambda _c: "valid_must_fix",
        )

        self.assertEqual(updated.phase, "blocked")
        self.assertEqual(assignments, [])
        self.assertEqual(db.calls[0][0], "blocked")
        self.assertIn("remain after", db.calls[0][3].lower())

    def test_changed_body_can_be_fixed_again_as_new_candidate(self):
        old = self._inline(body="old advice")
        new = self._inline(body="new advice entirely")
        run = _run(
            pr_review_fix_rounds=0,
            metadata={"pr_review_comments": {
                old.stable_key: {"verdict": "valid_must_fix", "attempted": True},
            }},
        )
        db = FakeDbClient([run])
        assignments = []

        updated = reconcile_pr_run(
            run,
            _reality(review_comments=(new,)),
            db,
            assign_fix=lambda run, reality: assignments.append(reality),
            validate_comment=lambda _c: "valid_must_fix",
        )

        self.assertEqual(updated.phase, "fixing")
        self.assertEqual(len(assignments), 1)

    def test_needs_user_judgment_blocks(self):
        db = FakeDbClient([_run()])
        c = self._inline()
        updated = reconcile_pr_run(
            db.runs[0],
            _reality(review_comments=(c,)),
            db,
            validate_comment=lambda _c: "needs_user_judgment",
        )

        self.assertEqual(updated.phase, "blocked")
        self.assertEqual(db.calls[0][0], "blocked")
        self.assertIn("user judgment", db.calls[0][3].lower())

    def test_invalid_inline_comment_does_not_block_or_fix(self):
        db = FakeDbClient([_run(pr_review_fix_rounds=0)])
        c = self._inline(body="this suggestion is wrong")
        updated = reconcile_pr_run(
            db.runs[0],
            _reality(review_comments=(c,), ci_green=True),
            db,
            assign_fix=lambda *a: self.fail("must not assign fix for invalid comment"),
            validate_comment=lambda _c: "invalid",
        )

        self.assertEqual(updated.phase, "ready_to_merge")

    def test_merged_pr_wins_over_needs_user_judgment(self):
        db = FakeDbClient([_run()])
        c = self._inline()
        updated = reconcile_pr_run(
            db.runs[0],
            _reality(merged=True, closed=True, review_comments=(c,)),
            db,
            validate_comment=lambda _c: "needs_user_judgment",
        )
        self.assertEqual(updated.phase, "done")


class TestLegacyCommentsRoutedThroughValidation(unittest.TestCase):
    """Finding 1: top-level comments, latestReviews, and a CHANGES_REQUESTED
    reviewDecision must pass through the validation gate, not auto-trigger a
    fix. Marker text / CHANGES_REQUESTED summaries are never auto valid_must_fix.
    """

    @staticmethod
    def _pr_view(**overrides):
        base = {
            "number": 45, "headRefName": "feat/12", "state": "OPEN",
            "mergedAt": None, "statusCheckRollup": [], "reviewDecision": None,
            "comments": [], "latestReviews": [],
        }
        base.update(overrides)
        return _completed(returncode=0, stdout=json.dumps(base))

    def _reality_with(self, **pr_overrides):
        with mock.patch(
            "u_agents.pr_watcher._run",
            side_effect=[self._pr_view(**pr_overrides), _inline_proc()],
        ):
            return fetch_pr_reality("o/r", 45)

    def test_top_level_must_fix_comment_collected_as_review_comment(self):
        reality = self._reality_with(
            comments=[{"id": "c9", "body": "must-fix: guard context.mounted"}],
        )
        srcs = {c.source for c in reality.review_comments}
        self.assertIn("comment", srcs)

    def test_top_level_forward_action_comment_collected_and_handed_off(self):
        reality = self._reality_with(
            comments=[{"id": "c10", "body": "This must be addressed before merge"}],
        )
        comments = [c for c in reality.review_comments if c.source == "comment"]
        self.assertEqual(len(comments), 1)
        self.assertEqual(default_validate_comment(comments[0]), "needs_user_judgment")
        db = FakeDbClient([_run(phase="pr_watching")])
        handoffs = []

        updated = reconcile_pr_run(
            db.runs[0],
            reality,
            db,
            dispatch_handoff=lambda _run, _reality, keys: handoffs.append(list(keys)) or True,
        )

        self.assertEqual(updated.phase, "fixing")
        self.assertEqual(handoffs, [[comments[0].stable_key]])

    def test_latest_review_forward_action_summary_collected(self):
        reality = self._reality_with(
            latestReviews=[{
                "id": "r3",
                "state": "COMMENTED",
                "body": "blocking bug should be resolved",
            }],
        )
        reviews = [c for c in reality.review_comments if c.source == "latest_review"]
        self.assertEqual(len(reviews), 1)
        self.assertEqual(default_validate_comment(reviews[0]), "needs_user_judgment")

    def test_top_level_must_fix_comment_does_not_auto_fix_under_default(self):
        reality = self._reality_with(
            comments=[{"id": "c9", "body": "must-fix: guard context.mounted"}],
        )
        db = FakeDbClient([_run(pr_review_fix_rounds=0)])
        updated = reconcile_pr_run(db.runs[0], reality, db)
        # Escalated for validation, never auto-fixed from marker text alone.
        self.assertEqual(updated.phase, "blocked")
        self.assertNotEqual(db.calls[0][0], "update_pr_fields")
        self.assertIn("user judgment", db.calls[0][3].lower())

    def test_top_level_must_fix_comment_not_fixed_when_validator_rejects(self):
        reality = self._reality_with(
            comments=[{"id": "c9", "body": "must-fix: guard context.mounted"}],
        )
        for verdict in ("invalid", "valid_optional"):
            with self.subTest(verdict=verdict):
                db = FakeDbClient([_run(pr_review_fix_rounds=0)])
                updated = reconcile_pr_run(
                    db.runs[0], replace(reality, ci_green=True), db,
                    assign_fix=lambda *a: self.fail("must not fix a rejected comment"),
                    validate_comment=lambda _c: verdict,
                )
                self.assertEqual(updated.phase, "ready_to_merge")

    def test_changes_requested_review_decision_escalates(self):
        reality = self._reality_with(reviewDecision="CHANGES_REQUESTED")
        sentinels = [c for c in reality.review_comments if c.source == "review_decision"]
        self.assertEqual(len(sentinels), 1)
        db = FakeDbClient([_run()])
        updated = reconcile_pr_run(db.runs[0], reality, db)
        self.assertEqual(updated.phase, "blocked")
        self.assertIn("user judgment", db.calls[0][3].lower())

    def test_changes_requested_latest_review_escalates_not_fixes(self):
        reality = self._reality_with(
            latestReviews=[{"id": "r2", "state": "CHANGES_REQUESTED", "body": "fix"}],
        )
        db = FakeDbClient([_run()])
        updated = reconcile_pr_run(db.runs[0], reality, db)
        self.assertEqual(updated.phase, "blocked")
        self.assertNotEqual(db.calls[0][0], "update_pr_fields")

    def test_changes_requested_state_validates_to_needs_user_judgment(self):
        c = ReviewComment(
            comment_id="rd", body="", source="review_decision",
            state="CHANGES_REQUESTED",
        )
        self.assertEqual(default_validate_comment(c), "needs_user_judgment")

    def test_approved_empty_review_is_optional_not_escalated(self):
        c = ReviewComment(
            comment_id="r1", body="", source="latest_review", state="APPROVED",
        )
        self.assertEqual(default_validate_comment(c), "valid_optional")


class TestBookkeepingMerge(unittest.TestCase):
    """Finding 4: prior per-comment attempted state must survive a pass that
    sees an empty or unrelated comment list."""

    def test_prior_attempted_key_preserved_when_no_current_comments(self):
        prior = {"111:abc": {"verdict": "valid_must_fix", "attempted": True}}
        t = triage_review_comments([], prior, lambda _c: "valid_must_fix")
        self.assertIn("111:abc", t.bookkeeping)
        self.assertTrue(t.bookkeeping["111:abc"]["attempted"])

    def test_prior_key_preserved_alongside_unrelated_current_comment(self):
        prior = {"111:abc": {"verdict": "valid_must_fix", "attempted": True}}
        other = ReviewComment(comment_id="222", body="new note", source="inline")
        t = triage_review_comments([other], prior, lambda _c: "valid_optional")
        self.assertIn("111:abc", t.bookkeeping)
        self.assertTrue(t.bookkeeping["111:abc"]["attempted"])
        self.assertIn(other.stable_key, t.bookkeeping)

    def test_reconcile_persists_prior_attempted_key_with_empty_comments(self):
        prior_key = "111:abc"
        run = _run(
            phase="pr_open",
            metadata={"pr_review_comments": {
                prior_key: {"verdict": "valid_must_fix", "attempted": True},
            }},
        )
        db = FakeDbClient([run])
        reconcile_pr_run(run, _reality(review_comments=()), db)
        meta = db.calls[0][-1]
        self.assertIn(prior_key, meta["pr_review_comments"])
        self.assertTrue(meta["pr_review_comments"][prior_key]["attempted"])


class TestLiveValidationHandoff(unittest.TestCase):
    """Finding 1: the live watcher must dispatch needs_user_judgment comments to
    the existing PM pane (not dead-end), and must not re-send the same stable
    keys every tick."""

    def _inline(self, cid="111", body="please look at this", **o):
        return ReviewComment(
            comment_id=cid, body=body, source="inline", path="a.dart", line=7, **o,
        )

    def test_fresh_needs_judgment_is_handed_off_not_blocked(self):
        db = FakeDbClient([_run(phase="pr_watching")])
        c = self._inline()
        handoffs = []

        updated = reconcile_pr_run(
            db.runs[0],
            _reality(review_comments=(c,)),
            db,
            dispatch_handoff=lambda run, reality, keys: handoffs.append(list(keys)) or True,
            validate_comment=lambda _c: "needs_user_judgment",
        )

        # Dispatched, parked in 'fixing', recorded handed_off, NOT blocked.
        self.assertEqual(handoffs, [[c.stable_key]])
        self.assertEqual(updated.phase, "fixing")
        self.assertEqual(db.calls[0][0], "update_pr_fields")
        meta = db.calls[0][-1]
        self.assertTrue(meta["pr_review_comments"][c.stable_key]["handed_off"])
        self.assertIn(
            c.stable_key,
            meta["pr_watcher"]["review_comment_triage"]["handed_off"],
        )

    def test_already_handed_off_key_escalates_instead_of_resending(self):
        c = self._inline()
        run = _run(
            phase="pr_watching",
            metadata={"pr_review_comments": {
                c.stable_key: {"verdict": "needs_user_judgment", "handed_off": True},
            }},
        )
        db = FakeDbClient([run])
        handoffs = []

        updated = reconcile_pr_run(
            run,
            _reality(review_comments=(c,)),
            db,
            dispatch_handoff=lambda *a: handoffs.append(a) or True,
            validate_comment=lambda _c: "needs_user_judgment",
        )

        # Not re-sent; escalated to a human block.
        self.assertEqual(handoffs, [])
        self.assertEqual(updated.phase, "blocked")
        self.assertEqual(db.calls[0][0], "blocked")
        self.assertIn("user judgment", db.calls[0][3].lower())

    def test_delivery_failure_does_not_mark_handed_off(self):
        db = FakeDbClient([_run(phase="pr_watching")])
        c = self._inline()

        updated = reconcile_pr_run(
            db.runs[0],
            _reality(review_comments=(c,)),
            db,
            dispatch_handoff=lambda *a: False,  # delivery failed
            validate_comment=lambda _c: "needs_user_judgment",
        )

        # Keep watching and retry; handed_off must stay unset so it is re-tried.
        self.assertEqual(updated.phase, "pr_watching")
        meta = db.calls[0][-1]
        self.assertFalse(meta["pr_review_comments"][c.stable_key]["handed_off"])

    def test_without_dispatcher_default_still_blocks(self):
        db = FakeDbClient([_run(phase="pr_watching")])
        c = self._inline()
        updated = reconcile_pr_run(
            db.runs[0],
            _reality(review_comments=(c,)),
            db,
            validate_comment=lambda _c: "needs_user_judgment",
        )
        self.assertEqual(updated.phase, "blocked")

    def test_check_once_threads_dispatch_handoff_to_reconcile(self):
        # The production path used by main()/check_once must reach reconcile's
        # dispatch branch, not just be wired in tests of reconcile directly.
        db = FakeDbClient([_run(phase="pr_watching")])
        c = self._inline()
        handoffs = []

        updated = check_once(
            db,
            fetch_reality=lambda repo, pr: _reality(review_comments=(c,)),
            dispatch_handoff=lambda run, reality, keys: handoffs.append(list(keys)) or True,
            validate_comment=lambda _c: "needs_user_judgment",
        )

        self.assertEqual(handoffs, [[c.stable_key]])
        self.assertEqual(updated[0].phase, "fixing")

    def test_live_dispatch_handoff_sends_prompt_via_tmux(self):
        run = _run(phase="pr_watching")
        c = self._inline()
        reality = _reality(review_comments=(c,))
        sent = {}

        def fake_send_prompt(window, prompt, dry_run):
            sent["window"] = window
            sent["prompt"] = prompt
            sent["dry_run"] = dry_run

        with mock.patch("u_agents.launcher.send_prompt", side_effect=fake_send_prompt):
            ok = live_dispatch_handoff(run, reality, [c.stable_key])

        self.assertTrue(ok)
        self.assertEqual(sent["window"], run.tmux_window)
        self.assertFalse(sent["dry_run"])
        self.assertIn(c.stable_key, sent["prompt"])

    def test_live_dispatch_handoff_returns_false_on_tmux_error(self):
        run = _run(phase="pr_watching")
        reality = _reality(review_comments=(self._inline(),))
        with mock.patch(
            "u_agents.launcher.send_prompt",
            side_effect=RuntimeError("pane is dead"),
        ):
            ok = live_dispatch_handoff(run, reality, [self._inline().stable_key])
        self.assertFalse(ok)

    def test_handoff_prompt_demands_validation_and_at_most_once(self):
        run = _run()
        c = self._inline(body="ref.read after await should be guarded")
        prompt = build_validation_handoff_prompt(
            run, _reality(review_comments=(c,)), [c.stable_key],
        )
        self.assertIn(c.stable_key, prompt)
        self.assertIn("Validate each", prompt)
        self.assertIn("at most once", prompt)
        self.assertIn("valid_must_fix", prompt)
        self.assertIn("mark_pr_open", prompt)

    def test_prompts_use_exact_mark_pr_open_rearm_command(self):
        run = _run()
        c = self._inline(body="ref.read after await should be guarded")
        reality = _reality(review_comments=(c,))
        expected = mark_pr_open_command(
            run.repository_full_name, run.github_issue_number, reality.pr_number,
        )
        for prompt in (
            build_validation_handoff_prompt(run, reality, [c.stable_key]),
            build_fix_prompt(run, reality),
        ):
            with self.subTest(prompt=prompt.splitlines()[0]):
                self.assertIn(expected, prompt)
                self.assertIn("PYTHONPATH=", prompt)
                self.assertIn(sys.executable, prompt)
                self.assertIn("-m u_agents.mark_pr_open", prompt)
                self.assertNotIn("`python -m u_agents.mark_pr_open`", prompt)


class TestStrictHandoffPromptPolicy(unittest.TestCase):
    """Lock the stricter 'address unless clearly invalid' default stance in the
    PM validation handoff prompt so it cannot silently revert to the old lax
    'address only valid_must_fix' wording."""

    def _prompt(self):
        run = _run()
        c = ReviewComment(
            comment_id="111", body="guard context.mounted here",
            source="inline", path="a.dart", line=7,
        )
        return build_validation_handoff_prompt(
            run, _reality(review_comments=(c,)), [c.stable_key],
        )

    def test_default_stance_is_address(self):
        prompt = self._prompt()
        self.assertIn("DEFAULT STANCE", prompt)
        self.assertIn(
            "address every listed comment unless it is clearly invalid", prompt,
        )

    def test_uncertainty_is_not_a_reason_to_skip(self):
        prompt = self._prompt().lower()
        self.assertIn("not being fully certain", prompt)
        self.assertIn(
            "if you are unsure between valid_must_fix and valid_optional, "
            "choose valid_must_fix",
            prompt,
        )

    def test_optional_is_described_as_rare(self):
        self.assertIn("RARE", self._prompt())

    def test_invalid_is_constrained_to_clearly_wrong(self):
        prompt = self._prompt().lower()
        self.assertIn("factually wrong", prompt)
        self.assertIn("contradicts", prompt)

    def test_needs_user_judgment_is_product_decisions(self):
        prompt = self._prompt().lower()
        self.assertIn("needs_user_judgment", prompt)
        self.assertIn("product/spec decision", prompt)

    def test_does_not_use_old_lax_wording(self):
        prompt = self._prompt().lower()
        self.assertNotIn("address only valid_must_fix", prompt)
        self.assertNotIn("only valid_must_fix comments", prompt)

    def test_all_four_verdicts_documented(self):
        prompt = self._prompt()
        for verdict in REVIEW_VERDICTS:
            self.assertIn(verdict, prompt)


class TestPhraseSafeMarkers(unittest.TestCase):
    """Finding 2: forward-looking 'must be addressed' / 'should be resolved'
    phrasings must not be silently classified invalid/optional from a bare
    'addressed'/'resolved' substring."""

    def _c(self, body):
        return ReviewComment(comment_id="1", body=body, source="inline")

    def test_forward_looking_phrases_escalate_not_invalidated(self):
        for body in (
            "This must be addressed before merge",
            "This blocking bug should be resolved",
            "blocking bug should be resolved",
        ):
            with self.subTest(body=body):
                verdict = default_validate_comment(self._c(body))
                self.assertEqual(verdict, "needs_user_judgment")
                self.assertNotIn(verdict, ("invalid", "valid_optional"))

    def test_past_dismissive_phrases_are_invalid(self):
        for body in (
            "already addressed",
            "has been addressed",
            "resolved already",
            "this was resolved in a prior commit",
            "outdated",
            "wontfix",
        ):
            with self.subTest(body=body):
                self.assertEqual(default_validate_comment(self._c(body)), "invalid")

    def test_validation_candidate_survives_forward_resolved_phrasing(self):
        from u_agents.pr_watcher import _body_is_validation_candidate

        # A blocking comment that says it "should be resolved" is still routed
        # to validation; a dismissive "already resolved" is suppressed.
        self.assertTrue(
            _body_is_validation_candidate("blocking bug should be resolved")
        )
        self.assertFalse(
            _body_is_validation_candidate("this is blocking but already addressed")
        )


if __name__ == "__main__":
    unittest.main()
