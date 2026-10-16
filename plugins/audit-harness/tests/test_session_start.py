"""
Tests de hooks/session-start.py — negro-caja vía subprocess (el hook lee de
stdin y escribe a stdout, igual que lo invoca Claude Code).

Corré con: python3 -m unittest tests.test_session_start -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "hooks", "session-start.py")


def run_hook(stdin_text: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, SCRIPT],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
        env=full_env,
    )


def context_of(result: subprocess.CompletedProcess) -> str:
    payload = json.loads(result.stdout)
    return payload["hookSpecificOutput"]["additionalContext"]


class SessionStartHookTests(unittest.TestCase):
    def test_dict_with_cwd_without_config_suggests_setup(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_hook(json.dumps({"cwd": d}))
            self.assertEqual(r.returncode, 0)
            self.assertIn("audit-setup", context_of(r))

    def test_dict_with_cwd_with_config_mentions_already_connected(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "audit.config.yaml"), "w").close()
            r = run_hook(json.dumps({"cwd": d}))
            self.assertEqual(r.returncode, 0)
            self.assertIn("ya está conectado", context_of(r))

    def test_json_list_does_not_crash(self):
        r = run_hook("[1, 2, 3]")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        context_of(r)  # no debe tirar al parsear -- sigue siendo JSON válido de salida

    def test_json_scalar_does_not_crash(self):
        r = run_hook("42")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_json_string_does_not_crash(self):
        r = run_hook('"hola"')
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_invalid_json_falls_back_without_crash(self):
        r = run_hook("esto no es json {")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_empty_stdin_falls_back_without_crash(self):
        r = run_hook("")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_missing_cwd_falls_back_to_os_getcwd_without_crash(self):
        r = run_hook(json.dumps({"no_cwd_field": True}))
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_output_is_always_valid_json_on_stdout(self):
        for stdin_text in ["{}", "[1]", "null", "not json", ""]:
            with self.subTest(stdin=stdin_text):
                r = run_hook(stdin_text)
                json.loads(r.stdout)  # no debe tirar


if __name__ == "__main__":
    unittest.main()
