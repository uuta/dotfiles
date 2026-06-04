import re
import unittest
from pathlib import Path

from u_agents.contract import ConfigError
from u_agents.control_plane import (
    ENV_DATABASE_URL,
    ENV_MACHINE_ID,
    ENV_RUNNER_ID,
    database_url_from_env,
    load_runner_identity,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_TEMPLATE = REPO_ROOT / ".u_agents_env.zsh.template"
ZSHRC = REPO_ROOT / ".zshrc"
DOCS = REPO_ROOT / "docs" / "u-agents.md"

# Same forbidden personal markers guarded for the launchd examples.
PERSONAL_PATTERNS = [
    re.compile(r"/Users/yutaaoki(?:/|$)"),
    re.compile(r"\byutaaoki\b"),
    re.compile(r"\buuta\b"),
]


def _exports(text: str) -> dict:
    out = {}
    for m in re.finditer(r'^\s*export\s+([A-Z_]+)="?([^"\n]*)"?\s*$', text, re.M):
        out[m.group(1)] = m.group(2)
    return out


class TestEnvTemplate(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENV_TEMPLATE.exists(), f"missing {ENV_TEMPLATE}")
        self.text = ENV_TEMPLATE.read_text(encoding="utf-8")
        self.exports = _exports(self.text)

    def test_template_exports_all_required_vars(self):
        for key in (ENV_DATABASE_URL, ENV_RUNNER_ID, ENV_MACHINE_ID):
            self.assertIn(key, self.exports, f"template missing export {key}")

    def test_database_url_has_valid_scheme(self):
        url = self.exports[ENV_DATABASE_URL]
        self.assertEqual(database_url_from_env({ENV_DATABASE_URL: url}), url)

    def test_identity_placeholders_fail_loudly_until_edited(self):
        with self.assertRaises(ConfigError):
            load_runner_identity({
                ENV_RUNNER_ID: self.exports[ENV_RUNNER_ID],
                ENV_MACHINE_ID: self.exports[ENV_MACHINE_ID],
            })

    def test_template_has_no_personal_values(self):
        for pat in PERSONAL_PATTERNS:
            self.assertIsNone(
                pat.search(self.text),
                f"template contains forbidden pattern {pat.pattern!r}",
            )

    def test_template_instructs_private_file_mode(self):
        self.assertIn("chmod 600 ~/.u_agents_env.zsh", self.text)


class TestZshrcSourcesEnv(unittest.TestCase):
    def test_zshrc_guards_and_sources_local_env_file(self):
        text = ZSHRC.read_text(encoding="utf-8")
        # Guarded source so shells without the local file are unaffected, and
        # the real file lives outside the repo (in $HOME), never tracked.
        self.assertRegex(
            text,
            r'\[\[ -f "\$HOME/\.u_agents_env\.zsh" \]\] && source "\$HOME/\.u_agents_env\.zsh"',
        )


class TestRuntimeEnvDocs(unittest.TestCase):
    def test_docs_instruct_private_file_mode(self):
        text = DOCS.read_text(encoding="utf-8")
        self.assertIn("chmod 600 ~/.u_agents_env.zsh", text)


if __name__ == "__main__":
    unittest.main()
