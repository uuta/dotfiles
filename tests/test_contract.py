import json
import tempfile
import unittest
from pathlib import Path

from u_agents.contract import (
    LABEL_IN_PROGRESS,
    LABEL_READY,
    RepoConfig,
    branch_name,
    load_config,
    parse_window_name,
    pm_pane_target,
    tmux_window_name,
    worktree_path,
)


class TestRepoConfig(unittest.TestCase):
    def test_derived_paths(self):
        r = RepoConfig(
            full_name="uuta/trander-flutter",
            workspace_root="/workspace/trander-flutter",
            default_branch="master",
        )
        self.assertEqual(r.short_name, "trander-flutter")
        self.assertEqual(r.main_checkout, "/workspace/trander-flutter/master")
        self.assertEqual(r.worktrees_root, "/workspace/trander-flutter/.worktrees")

    def test_strips_trailing_slash(self):
        r = RepoConfig(
            full_name="o/r",
            workspace_root="/tmp/x/",
            default_branch="main",
        )
        self.assertEqual(r.main_checkout, "/tmp/x/main")
        self.assertEqual(r.worktrees_root, "/tmp/x/.worktrees")


class TestNaming(unittest.TestCase):
    def setUp(self):
        self.repo = RepoConfig("uuta/trander-flutter", "/tmp/tf", "master")

    def test_tmux_window_name(self):
        self.assertEqual(tmux_window_name(self.repo, 233), "trander-flutter-233")

    def test_pm_pane_target(self):
        self.assertEqual(pm_pane_target("trander-flutter-233"),
                         "agents:trander-flutter-233.0")

    def test_branch_and_worktree(self):
        self.assertEqual(branch_name(233), "feat/233")
        self.assertEqual(worktree_path(self.repo, 233), "/tmp/tf/.worktrees/233")

    def test_parse_window_name(self):
        self.assertEqual(parse_window_name("trander-flutter-233"),
                         ("trander-flutter", 233))
        self.assertEqual(parse_window_name("u-5"), ("u", 5))
        self.assertIsNone(parse_window_name("_init"))
        self.assertIsNone(parse_window_name("misc-not-a-number"))


class TestLoadConfig(unittest.TestCase):
    def test_load_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            p.write_text(json.dumps({
                "repositories": [
                    {"full_name": "o/a", "workspace_root": "/w/a",
                     "default_branch": "main", "enabled": True},
                    {"full_name": "o/b", "workspace_root": "/w/b",
                     "default_branch": "master", "enabled": False},
                ]
            }))
            repos = load_config(p)
            self.assertEqual(len(repos), 2)
            self.assertEqual(repos[0].short_name, "a")
            self.assertFalse(repos[1].enabled)

    def test_load_yaml(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.yml"
            p.write_text(
                "repositories:\n"
                "  - full_name: o/a\n"
                "    workspace_root: /w/a\n"
                "    default_branch: main\n"
                "    enabled: true\n"
            )
            repos = load_config(p)
            self.assertEqual(len(repos), 1)
            self.assertEqual(repos[0].full_name, "o/a")

    def test_missing_field_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            p.write_text(json.dumps({"repositories": [{"full_name": "o/a"}]}))
            with self.assertRaises(Exception):
                load_config(p)


class TestLabelConstants(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(LABEL_READY, "status:ready")
        self.assertEqual(LABEL_IN_PROGRESS, "status:in-progress")


if __name__ == "__main__":
    unittest.main()
