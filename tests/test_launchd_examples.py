"""Sanity checks for examples/launchd/*.plist.

These guard against three classes of regression:
1. Plist files must parse (otherwise `launchctl load` would fail on the user).
2. Each plist must invoke the expected agents module.
3. No personal paths leaked into the tracked example.
"""
import plistlib
import re
import unittest
from pathlib import Path


EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "launchd"
LAUNCHER_PLIST = EXAMPLES / "local.u-agents.launcher.plist"
WATCHDOG_PLIST = EXAMPLES / "local.u-agents.watchdog.plist"

# Patterns that must NEVER appear in a tracked example.
PERSONAL_PATTERNS = [
    re.compile(r"/Users/yutaaoki(?:/|$)"),
    re.compile(r"\byutaaoki\b"),
    re.compile(r"\buuta\b"),
]


def _load(path: Path) -> dict:
    with path.open("rb") as f:
        return plistlib.load(f)


class TestLauncherPlist(unittest.TestCase):
    def setUp(self):
        self.assertTrue(LAUNCHER_PLIST.exists(), f"missing {LAUNCHER_PLIST}")
        self.plist = _load(LAUNCHER_PLIST)

    def test_label_namespaced(self):
        self.assertEqual(self.plist["Label"], "local.u-agents.launcher")

    def test_invokes_launcher_module(self):
        args = self.plist["ProgramArguments"]
        self.assertIn("-m", args)
        self.assertIn("u_agents.launcher", args)
        # python interpreter is the first arg, must be an absolute path.
        self.assertTrue(
            args[0].startswith("/"),
            f"ProgramArguments[0] must be an absolute python path, got: {args[0]}",
        )

    def test_passes_config_flag(self):
        args = self.plist["ProgramArguments"]
        self.assertIn("--config", args)
        idx = args.index("--config")
        self.assertTrue(args[idx + 1].endswith("repositories.yml"),
                        f"--config target should end with repositories.yml, got: {args[idx + 1]}")

    def test_five_minute_interval(self):
        self.assertEqual(self.plist["StartInterval"], 300)

    def test_run_at_load_disabled(self):
        # Avoid firing immediately on launchctl load.
        self.assertFalse(self.plist.get("RunAtLoad", False))

    def test_working_directory_points_at_repo_checkout(self):
        # Required so `u_agents/` is importable.
        self.assertIn("WorkingDirectory", self.plist)
        self.assertTrue(self.plist["WorkingDirectory"].startswith("/"),
                        "WorkingDirectory must be absolute")

    def test_log_paths_set(self):
        self.assertIn("StandardOutPath", self.plist)
        self.assertIn("StandardErrorPath", self.plist)

    def test_path_env_includes_homebrew(self):
        env = self.plist.get("EnvironmentVariables", {})
        self.assertIn("/opt/homebrew/bin", env.get("PATH", ""))


class TestWatchdogPlist(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WATCHDOG_PLIST.exists(), f"missing {WATCHDOG_PLIST}")
        self.plist = _load(WATCHDOG_PLIST)

    def test_label_namespaced(self):
        self.assertEqual(self.plist["Label"], "local.u-agents.watchdog")

    def test_invokes_watchdog_module(self):
        args = self.plist["ProgramArguments"]
        self.assertIn("-m", args)
        self.assertIn("u_agents.watchdog", args)

    def test_uses_once_flag(self):
        # Critical: launchd must own the cadence. The long-loop form is
        # opaque to launchd and a hung process would silently stop the
        # watchdog. See docs/u-agents.md "Why watchdog uses --once".
        self.assertIn("--once", self.plist["ProgramArguments"])

    def test_does_not_opt_in_to_pane_tail(self):
        # --include-pane-tail leaks pane content to GitHub. Tracked example
        # must NOT enable it; users opt in deliberately after reading docs.
        self.assertNotIn("--include-pane-tail", self.plist["ProgramArguments"])

    def test_one_minute_interval(self):
        self.assertEqual(self.plist["StartInterval"], 60)

    def test_run_at_load_disabled(self):
        self.assertFalse(self.plist.get("RunAtLoad", False))

    def test_log_paths_set(self):
        self.assertIn("StandardOutPath", self.plist)
        self.assertIn("StandardErrorPath", self.plist)


class TestNoPersonalPaths(unittest.TestCase):
    """Fix #5 (config) reaffirmed: example plists must be free of personal data."""

    def _scan(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_launcher_plist_has_no_personal_paths(self):
        text = self._scan(LAUNCHER_PLIST)
        for pat in PERSONAL_PATTERNS:
            self.assertIsNone(
                pat.search(text),
                f"{LAUNCHER_PLIST.name} contains forbidden pattern {pat.pattern!r}",
            )

    def test_watchdog_plist_has_no_personal_paths(self):
        text = self._scan(WATCHDOG_PLIST)
        for pat in PERSONAL_PATTERNS:
            self.assertIsNone(
                pat.search(text),
                f"{WATCHDOG_PLIST.name} contains forbidden pattern {pat.pattern!r}",
            )

    def test_examples_use_your_name_placeholder(self):
        for path in (LAUNCHER_PLIST, WATCHDOG_PLIST):
            text = self._scan(path)
            self.assertIn("your-name", text,
                          f"{path.name} should use the 'your-name' placeholder")


if __name__ == "__main__":
    unittest.main()
