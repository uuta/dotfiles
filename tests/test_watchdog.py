import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from u_agents.contract import RepoConfig
from u_agents.agent_runs import AgentRun
from u_agents import watchdog
from u_agents.watchdog import (
    DEFAULT_STATE_DIR,
    DEFAULT_STATE_FILE,
    WindowState,
    build_stall_comment_body,
    check_once,
    load_state,
    main as watchdog_main,
    save_state,
)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        self.t += 1.0
        return self.t


def _run_row(repo_full="uuta/u", issue_number=5, phase="pm_started",
             tmux_window="u-5", pm_pane="agents:u-5.0", lease_until="past"):
    return AgentRun(
        repository_full_name=repo_full,
        github_issue_number=issue_number,
        parent_branch="main",
        branch_name=f"feat/{issue_number}",
        phase=phase,
        runner_id="runner-1",
        machine_id="machine-1",
        locked_by="runner-1@machine-1",
        lease_until=lease_until,
        worktree_basename=str(issue_number),
        tmux_window=tmux_window,
        pm_pane=pm_pane,
    )


class FakeDbClient:
    def __init__(self, active=None, stale=None):
        self.active = list(active or [])
        self.stale = list(stale or [])
        self.observations = []

    def list_active_runs(self):
        return list(self.active)

    def list_stale_runs(self):
        return list(self.stale)

    def record_observation(self, repo_full, issue_number, observation):
        self.observations.append((repo_full, issue_number, observation))

    def close(self):
        return None


class TestDefaultStatePath(unittest.TestCase):
    def test_default_watchdog_state_lives_under_package_u_agents(self):
        expected_state_dir = Path(watchdog.__file__).resolve().parent / "state"
        self.assertTrue(DEFAULT_STATE_DIR.is_absolute())
        self.assertEqual(DEFAULT_STATE_DIR, expected_state_dir)
        self.assertEqual(DEFAULT_STATE_DIR / DEFAULT_STATE_FILE,
                         expected_state_dir / "watchdog.json")

    def test_default_watchdog_state_does_not_follow_process_cwd(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as d:
            try:
                os.chdir(d)
                self.assertEqual(
                    DEFAULT_STATE_DIR,
                    Path(watchdog.__file__).resolve().parent / "state",
                )
            finally:
                os.chdir(original_cwd)


class TestStateRoundtrip(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            state = {
                "u-5": WindowState(last_hash="abc", unchanged_checks=2,
                                   pinged=True, stall_comment_posted=False,
                                   last_update=123.0),
            }
            save_state(f, state)
            got = load_state(f)
            self.assertEqual(got["u-5"].last_hash, "abc")
            self.assertEqual(got["u-5"].unchanged_checks, 2)
            self.assertTrue(got["u-5"].pinged)


class TestWatchdogMainStateDir(unittest.TestCase):
    def test_explicit_state_dir_is_respected(self):
        with (
            tempfile.TemporaryDirectory() as d,
            mock.patch(
                "u_agents.watchdog._resolve_config",
                return_value=Path("/dev/null"),
            ),
            mock.patch("u_agents.watchdog.load_config", return_value=[]),
            mock.patch("u_agents.watchdog.AgentRunsClient.from_env",
                       return_value=FakeDbClient()),
            mock.patch("u_agents.watchdog.check_once") as check_once_mock,
        ):
            rc = watchdog_main(["--once", "--state-dir", d])

        self.assertEqual(rc, 0)
        check_once_mock.assert_called_once()
        self.assertEqual(check_once_mock.call_args.args[1],
                         Path(d) / DEFAULT_STATE_FILE)


class TestCheckOnce(unittest.TestCase):
    def setUp(self):
        self.repo = RepoConfig("uuta/u", "/Users/y/u", "main")
        self.window = "u-5"
        self.tmp = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tmp.name) / "w.json"
        self.captures = []  # list of (call_index -> text)
        self.pings = []
        self.comments = []
        self.clock = FakeClock()

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, capture_text):
        def list_windows():
            return [self.window]
        def capture(w):
            self.assertEqual(w, self.window)
            return capture_text
        def ping(w, dry):
            self.pings.append(w)
        def comment(repo_full, num, w, text, unchanged, dry):
            self.comments.append((repo_full, num, w, unchanged))
        return check_once(
            [self.repo], self.state_file, stall_checks=2, dry_run=False,
            list_windows=list_windows, capture=capture, ping=ping,
            comment=comment, now=self.clock,
        )

    def test_changing_output_never_pings(self):
        self._run("frame 1")
        self._run("frame 2")
        self._run("frame 3")
        self.assertEqual(self.pings, [])
        self.assertEqual(self.comments, [])

    def test_pings_after_stall_threshold(self):
        # first call seeds the hash (unchanged_checks=0)
        self._run("idle")
        # second: matches -> unchanged_checks=1, no ping (threshold=2)
        self._run("idle")
        self.assertEqual(self.pings, [])
        # third: matches -> unchanged_checks=2, ping fires
        self._run("idle")
        self.assertEqual(self.pings, [self.window])
        self.assertEqual(self.comments, [])

    def test_comments_after_ping_and_continued_stall(self):
        # seed
        self._run("idle")
        # reach ping at threshold=2
        self._run("idle")
        self._run("idle")
        self.assertEqual(self.pings, [self.window])
        # need unchanged_checks >= stall_checks*2 = 4 to comment
        self._run("idle")  # 3
        self.assertEqual(self.comments, [])
        self._run("idle")  # 4 -> comment
        self.assertEqual(self.comments, [("uuta/u", 5, self.window, 4)])
        # subsequent stalls do not re-comment
        self._run("idle")
        self.assertEqual(len(self.comments), 1)

    def test_change_resets_state(self):
        self._run("a")
        self._run("a")
        self._run("a")  # pinged
        self.assertEqual(self.pings, [self.window])
        self._run("b")  # change -> reset
        st = load_state(self.state_file)[self.window]
        self.assertEqual(st.unchanged_checks, 0)
        self.assertFalse(st.pinged)
        self.assertFalse(st.stall_comment_posted)

    def test_removes_gone_windows(self):
        # seed with a stale entry
        seed = {"gone-1": WindowState(last_hash="x", unchanged_checks=1,
                                       last_update=10.0)}
        save_state(self.state_file, seed)
        self._run("idle")
        state = load_state(self.state_file)
        self.assertNotIn("gone-1", state)
        self.assertIn(self.window, state)

    def test_ping_failure_is_persisted_and_not_retried_next_tick(self):
        attempts = []

        def list_windows():
            return [self.window]

        def capture(_w):
            return "idle"

        def ping(w, _dry):
            attempts.append(w)
            raise RuntimeError("pane gone")

        def comment(*_args):
            pass

        # seed, then reach the ping threshold
        check_once(
            [self.repo], self.state_file, stall_checks=2, dry_run=False,
            list_windows=list_windows, capture=capture, ping=ping,
            comment=comment, now=self.clock,
        )
        check_once(
            [self.repo], self.state_file, stall_checks=2, dry_run=False,
            list_windows=list_windows, capture=capture, ping=ping,
            comment=comment, now=self.clock,
        )
        check_once(
            [self.repo], self.state_file, stall_checks=2, dry_run=False,
            list_windows=list_windows, capture=capture, ping=ping,
            comment=comment, now=self.clock,
        )

        self.assertEqual(attempts, [self.window])
        self.assertTrue(load_state(self.state_file)[self.window].pinged)

        # Next launchd-style tick sees pinged=True and does not retry.
        check_once(
            [self.repo], self.state_file, stall_checks=2, dry_run=False,
            list_windows=list_windows, capture=capture, ping=ping,
            comment=comment, now=self.clock,
        )
        self.assertEqual(attempts, [self.window])

    def test_db_backed_lookup_pings_stale_run_after_stall(self):
        db = FakeDbClient(active=[], stale=[_run_row()])
        pings = []

        def list_windows():
            return [self.window]

        def capture(_w):
            return "idle"

        def ping(w, _dry):
            pings.append(w)

        check_once(
            [self.repo], self.state_file, stall_checks=1, dry_run=False,
            list_windows=list_windows, capture=capture, ping=ping,
            comment=lambda *_args: None, now=self.clock, db_client=db,
            verify_run=lambda _run: True,
        )
        check_once(
            [self.repo], self.state_file, stall_checks=1, dry_run=False,
            list_windows=list_windows, capture=capture, ping=ping,
            comment=lambda *_args: None, now=self.clock, db_client=db,
            verify_run=lambda _run: True,
        )

        self.assertEqual(pings, [self.window])
        self.assertEqual(db.observations[0][2]["watchdog"], "stale_lease")

    def test_missing_db_tmux_window_records_mismatch_without_pane_action(self):
        db = FakeDbClient(active=[_run_row(tmux_window="u-5")])
        captures = []
        pings = []

        check_once(
            [self.repo], self.state_file, stall_checks=1, dry_run=False,
            list_windows=lambda: [],
            capture=lambda w: captures.append(w) or "idle",
            ping=lambda w, _dry: pings.append(w),
            comment=lambda *_args: None,
            now=self.clock,
            db_client=db,
            verify_run=lambda _run: True,
        )

        self.assertEqual(captures, [])
        self.assertEqual(pings, [])
        self.assertEqual(db.observations[0][2]["watchdog"], "tmux_window_missing")

    def test_failed_github_verification_records_observation(self):
        db = FakeDbClient(active=[_run_row()])

        check_once(
            [self.repo], self.state_file, stall_checks=1, dry_run=False,
            list_windows=lambda: [self.window],
            capture=lambda _w: "idle",
            ping=lambda *_args: None,
            comment=lambda *_args: None,
            now=self.clock,
            db_client=db,
            verify_run=lambda _run: False,
        )

        self.assertEqual(
            db.observations[0][2]["watchdog"],
            "github_issue_verification_failed",
        )


class TestCheckOnceUnknownRepo(unittest.TestCase):
    def test_unresolvable_window_skips_comment(self):
        repo = RepoConfig("o/known", "/w", "main")
        with tempfile.TemporaryDirectory() as d:
            sf = Path(d) / "w.json"
            comments = []
            def list_windows():
                return ["unknown-9"]
            text = "idle"
            def capture(w):
                return text
            def ping(w, dry):
                pass
            def comment(*a):
                comments.append(a)
            for _ in range(6):
                check_once(
                    [repo], sf, stall_checks=2, dry_run=False,
                    list_windows=list_windows, capture=capture, ping=ping,
                    comment=comment, now=lambda: 1.0,
                )
            self.assertEqual(comments, [])


class TestStallCommentBody(unittest.TestCase):
    """Fix #2: default comment body must not leak captured pane content."""

    def test_default_body_excludes_pane_tail(self):
        capture = (
            "secret_token=ABC123XYZ\n"
            "/Users/secret/path/file.py\n"
            "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig\n"
        )
        body = build_stall_comment_body("u-5", capture, unchanged_checks=6)
        self.assertNotIn("ABC123XYZ", body)
        self.assertNotIn("/Users/secret", body)
        self.assertNotIn("Bearer", body)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", body)
        self.assertNotIn("<details>", body)
        # But operator-useful metadata is present.
        self.assertIn("agents:u-5.0", body)
        self.assertIn("unchanged-check count: 6", body)
        self.assertIn("tmux attach", body)
        self.assertIn("u-5", body)

    def test_default_body_documents_intentional_omission(self):
        body = build_stall_comment_body("u-5", "anything", unchanged_checks=4)
        self.assertIn("intentionally not posted", body)

    def test_opt_in_body_includes_sanitized_tail(self):
        capture = "line 1\nline 2 has <tag> & ampersand\n```\nfake fence\n```\n"
        body = build_stall_comment_body(
            "u-5", capture, unchanged_checks=4, include_tail=True,
        )
        self.assertIn("<details>", body)
        self.assertIn("sensitive", body.lower())
        # HTML-escaped to prevent breaking out of <pre>.
        self.assertIn("&lt;tag&gt;", body)
        self.assertIn("&amp; ampersand", body)
        # Original raw < and unescaped ``` could only be hostile if literally
        # present; they shouldn't be in the comment unescaped.
        self.assertNotIn("<tag>", body)
        # The literal backticks are allowed inside <pre> (they don't break out),
        # but the <pre> wrapper itself must be present so they render verbatim.
        self.assertIn("<pre>", body)
        self.assertIn("</pre>", body)


class TestLoadStateCorruption(unittest.TestCase):
    """Fix #4: load_state must not raise on corrupted JSON."""

    def test_corrupted_json_returns_empty_and_warns(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            f.write_text("{not valid json", encoding="utf-8")
            # Should not raise.
            state = load_state(f)
            self.assertEqual(state, {})

    def test_truncated_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            f.write_text('{"u-5": {"last_hash": "ab', encoding="utf-8")
            self.assertEqual(load_state(f), {})

    def test_empty_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            f.write_text("", encoding="utf-8")
            self.assertEqual(load_state(f), {})

    def test_after_corruption_save_overwrites_cleanly(self):
        # End-to-end recovery: corruption → load returns {} → save writes
        # valid JSON that subsequent load reads correctly.
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            f.write_text("garbage", encoding="utf-8")
            self.assertEqual(load_state(f), {})
            save_state(f, {"u-9": WindowState(last_hash="h", unchanged_checks=1)})
            again = load_state(f)
            self.assertEqual(again["u-9"].last_hash, "h")

    def test_root_not_dict_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            f.write_text('["u-5"]', encoding="utf-8")
            self.assertEqual(load_state(f), {})

    def test_value_not_dict_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            f.write_text(
                '{"u-5": {"last_hash": "ok"}, "u-6": "bad"}',
                encoding="utf-8",
            )
            state = load_state(f)
            self.assertEqual(sorted(state), ["u-5"])
            self.assertEqual(state["u-5"].last_hash, "ok")

    def test_unknown_fields_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            f.write_text(
                '{"u-5": {"last_hash": "ok", "future_field": "kept out"}}',
                encoding="utf-8",
            )
            state = load_state(f)
            self.assertEqual(state["u-5"].last_hash, "ok")
            self.assertFalse(hasattr(state["u-5"], "future_field"))


class TestAtomicSaveState(unittest.TestCase):
    """Fix #4: save_state must be atomic and not leave temp files behind."""

    def test_no_temp_files_remain_after_save(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            save_state(f, {"u-1": WindowState(last_hash="x")})
            entries = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(entries, ["w.json"])

    def test_save_does_not_corrupt_existing_state_when_payload_fails(self):
        # If something in the payload is unserializable, the old file must
        # remain intact. We simulate by trying to save a non-dataclass value,
        # which raises before os.replace.
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.json"
            save_state(f, {"u-1": WindowState(last_hash="original")})
            before = f.read_text(encoding="utf-8")
            with self.assertRaises(TypeError):
                # asdict() will fail on a non-dataclass object
                save_state(f, {"u-1": object()})  # type: ignore[arg-type]
            after = f.read_text(encoding="utf-8")
            self.assertEqual(before, after)
            # And no .tmp leftovers polluting the dir.
            entries = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(entries, ["w.json"])

    def test_save_in_nonexistent_parent_creates_it(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "nested" / "deep" / "w.json"
            save_state(f, {"u-1": WindowState(last_hash="x")})
            self.assertTrue(f.exists())


if __name__ == "__main__":
    unittest.main()
