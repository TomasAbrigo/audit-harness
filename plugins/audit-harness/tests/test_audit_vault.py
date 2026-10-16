"""
Tests de bin/audit_vault.py — negro-caja vía subprocess, porque lo que
importa fijar como contrato es exactamente lo que invocan los 19 auditores
reales: la CLI (argparse, choices, exit codes), no funciones internas.

Corré con: python3 -m unittest tests.test_audit_vault -v
(desde plugins/audit-harness/, o python3 -m unittest discover tests)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bin", "audit_vault.py")


def run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True,
        text=True,
        input=input_text,
        timeout=10,
    )


class AuditVaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db = os.path.join(self._tmpdir.name, "facts.db")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def add_fact(self, **kwargs) -> subprocess.CompletedProcess:
        defaults = dict(
            project="demo", vertical="security", statement="algo esta mal",
            severity="medium", evidence="x.py:10",
        )
        defaults.update(kwargs)
        args = ["add", "--db", self.db]
        for k, v in defaults.items():
            args += [f"--{k}", v]
        return run(*args)


class TestInit(AuditVaultTestCase):
    def test_init_creates_db_file(self):
        r = run("init", "--db", self.db)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(os.path.isfile(self.db))


class TestAdd(AuditVaultTestCase):
    def test_add_creates_fact(self):
        r = self.add_fact()
        self.assertEqual(r.returncode, 0)
        self.assertIn("creado", r.stdout)

    def test_add_missing_required_arg_exits_nonzero(self):
        # contrato de argparse: --severity es required, no puede desaparecer en silencio
        r = run("add", "--db", self.db, "--project", "demo", "--vertical", "security", "--statement", "x")
        self.assertNotEqual(r.returncode, 0)

    def test_add_invalid_severity_choice_rejected(self):
        r = self.add_fact(severity="urgentisimo")
        self.assertNotEqual(r.returncode, 0)

    def test_add_exact_duplicate_does_not_create_second_row(self):
        self.add_fact()
        r2 = self.add_fact()  # mismos project/vertical/statement/evidence
        self.assertEqual(r2.returncode, 0)
        self.assertIn("ya existe", r2.stdout)
        listed = run("list", "--db", self.db, "--project", "demo")
        # debe haber exactamente 1 línea de hallazgo (mas la linea de evidencia)
        self.assertEqual(listed.stdout.count("[medium/open]"), 1)

    def test_add_different_evidence_is_not_a_duplicate(self):
        self.add_fact(evidence="x.py:10")
        self.add_fact(evidence="y.py:20")
        listed = run("list", "--db", self.db, "--project", "demo")
        self.assertEqual(listed.stdout.count("[medium/open]"), 2)


class TestSearch(AuditVaultTestCase):
    def test_search_finds_by_statement_text(self):
        self.add_fact(statement="rate limiting ausente en login")
        r = run("search", "--db", self.db, "rate")
        self.assertEqual(r.returncode, 0)
        self.assertIn("rate limiting ausente", r.stdout)

    def test_search_invalid_fts5_syntax_does_not_crash(self):
        self.add_fact()
        for bad_query in ["foo AND", "(foo", "check-in", '"unterminated']:
            with self.subTest(query=bad_query):
                r = run("search", "--db", self.db, bad_query)
                self.assertNotEqual(r.returncode, 0, f"query {bad_query!r} debería fallar con exit != 0, no crashear")
                self.assertNotIn("Traceback", r.stderr, f"query {bad_query!r} no debe producir un traceback crudo")
                self.assertIn("FTS5", r.stderr)

    def test_search_quoted_special_chars_works_as_escape_hatch(self):
        self.add_fact(statement="chequeo de check-in de usuarios")
        r = run("search", "--db", self.db, '"check-in"')
        self.assertEqual(r.returncode, 0)
        self.assertIn("check-in", r.stdout)

    def test_search_cross_vertical_correlates_overlapping_lines_not_just_exact_string(self):
        self.add_fact(vertical="security", statement="hallazgo A", evidence="x.py:10-20 (detalle A)")
        self.add_fact(vertical="testing-coverage", statement="hallazgo B", evidence="x.py:15 (detalle B, distinto string)")
        self.add_fact(vertical="infra", statement="hallazgo no relacionado", evidence="y.py:99")
        r = run("search", "--db", self.db, "--project", "demo", "--cross-vertical", "hallazgo")
        self.assertEqual(r.returncode, 0)
        self.assertIn("correlacionados", r.stdout)
        self.assertIn("hallazgo A", r.stdout)
        self.assertIn("hallazgo B", r.stdout)
        # el no relacionado no debe aparecer bajo "correlacionados" aunque matchee la query
        head, _, tail = r.stdout.partition("-- resto --")
        self.assertNotIn("hallazgo no relacionado", head)

    def test_search_project_filter_optional_crosses_projects_when_omitted(self):
        self.add_fact(project="proyecto-a", statement="hallazgo unico cross")
        self.add_fact(project="proyecto-b", statement="hallazgo unico cross")
        r = run("search", "--db", self.db, "cross")
        self.assertEqual(r.stdout.count("[medium/open]"), 2)
        r_scoped = run("search", "--db", self.db, "--project", "proyecto-a", "cross")
        self.assertEqual(r_scoped.stdout.count("[medium/open]"), 1)


class TestResolve(AuditVaultTestCase):
    def _added_id(self) -> int:
        r = self.add_fact()
        # "fact #3 creado (...)"
        return int(r.stdout.split("#")[1].split()[0])

    def test_resolve_marks_resolved(self):
        fid = self._added_id()
        r = run("resolve", "--db", self.db, str(fid), "--by", "abc123 (#1)")
        self.assertEqual(r.returncode, 0)
        listed = run("list", "--db", self.db, "--status", "resolved")
        self.assertIn(f"#{fid}", listed.stdout)

    def test_resolve_wontfix_persists_wontfix_status(self):
        fid = self._added_id()
        run("resolve", "--db", self.db, str(fid), "--by", "decision", "--wontfix")
        listed = run("list", "--db", self.db, "--status", "wontfix")
        self.assertIn(f"#{fid}", listed.stdout)
        self.assertNotIn("resolved", [l for l in listed.stdout.splitlines() if f"#{fid}" in l][0])

    def test_resolve_nonexistent_id_exits_1_without_modifying_anything(self):
        r = run("resolve", "--db", self.db, "99999", "--by", "nadie")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no existe", r.stderr)

    def test_resolve_twice_overwrites_without_error(self):
        # contrato actual, fijado a propósito (antes no estaba testeado ni documentado):
        # un segundo resolve sobreescribe resolved_at/resolved_by sin error.
        fid = self._added_id()
        r1 = run("resolve", "--db", self.db, str(fid), "--by", "primero")
        r2 = run("resolve", "--db", self.db, str(fid), "--by", "segundo")
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r2.returncode, 0)

    def test_resolve_with_matching_project_succeeds(self):
        fid = self._added_id()  # project="demo"
        r = run("resolve", "--db", self.db, str(fid), "--by", "x", "--project", "demo")
        self.assertEqual(r.returncode, 0)

    def test_resolve_with_mismatched_project_blocks_and_does_not_modify(self):
        fid = self._added_id()  # project="demo"
        r = run("resolve", "--db", self.db, str(fid), "--by", "x", "--project", "otro-proyecto")
        self.assertNotEqual(r.returncode, 0)
        listed = run("list", "--db", self.db, "--status", "open")
        self.assertIn(f"#{fid}", listed.stdout)  # sigue open, no se tocó


class TestFtsSync(AuditVaultTestCase):
    def test_fts_index_stays_consistent_through_insert_and_resolve(self):
        """
        Regresión para el trigger facts_au removido (ver SCHEMA): confirma
        que sacar ese trigger no rompe la sincronización del índice FTS,
        justamente porque resolve nunca toca statement/evidence.
        """
        fid = self._id_of(self.add_fact(statement="hallazgo sincronizacion fts"))
        run("resolve", "--db", self.db, str(fid), "--by", "x")

        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO facts_fts(facts_fts) VALUES('integrity-check')")
        conn.close()  # no debe lanzar sqlite3.DatabaseError

        r = run("search", "--db", self.db, "sincronizacion")
        self.assertIn("hallazgo sincronizacion fts", r.stdout)

    def _id_of(self, add_result: subprocess.CompletedProcess) -> int:
        return int(add_result.stdout.split("#")[1].split()[0])


class TestCrossVerticalEdgeCases(AuditVaultTestCase):
    """
    Regresión para fact #25 (ronda 2 del self-audit): el union-find de
    --cross-vertical solo tenía cobertura del caso simple (2 correlan, 1 no).
    """

    def test_transitive_grouping_across_three_facts(self):
        # A solapa con B, B solapa con C, A NO solapa directo con C --
        # union-find los tiene que terminar agrupando a los 3 juntos.
        self.add_fact(vertical="security", statement="hallazgo trans A", evidence="x.py:10-15")
        self.add_fact(vertical="testing-coverage", statement="hallazgo trans B", evidence="x.py:14-20")
        self.add_fact(vertical="infra", statement="hallazgo trans C", evidence="x.py:19-25")
        r = run("search", "--db", self.db, "--project", "demo", "--cross-vertical", "trans")
        head, _, _ = r.stdout.partition("-- resto --")
        self.assertIn("hallazgo trans A", head)
        self.assertIn("hallazgo trans B", head)
        self.assertIn("hallazgo trans C", head)
        # las 3 verticales deben quedar en el mismo grupo, no 2 grupos separados
        self.assertEqual(head.count("(verticales:"), 1)

    def test_evidence_with_multiple_locations_correlates_on_any_of_them(self):
        self.add_fact(vertical="security", statement="hallazgo multi A", evidence="a.py:1; b.py:50-60")
        self.add_fact(vertical="infra", statement="hallazgo multi B", evidence="b.py:55 (coincide con la segunda ubicacion de A)")
        r = run("search", "--db", self.db, "--project", "demo", "--cross-vertical", "multi")
        head, _, _ = r.stdout.partition("-- resto --")
        self.assertIn("hallazgo multi A", head)
        self.assertIn("hallazgo multi B", head)

    def test_same_file_non_overlapping_ranges_stay_standalone(self):
        self.add_fact(vertical="security", statement="hallazgo lejano A", evidence="x.py:10-15")
        self.add_fact(vertical="infra", statement="hallazgo lejano B", evidence="x.py:500-510")
        r = run("search", "--db", self.db, "--project", "demo", "--cross-vertical", "lejano")
        # ninguno de los dos debe aparecer bajo "correlacionados" -- mismo archivo, rangos lejos
        if "correlacionados" in r.stdout:
            head, _, _ = r.stdout.partition("-- resto --")
            self.assertNotIn("hallazgo lejano", head)


class TestFileBasedInput(AuditVaultTestCase):
    """
    Regresión para fact #28 (ronda 2): --statement-file/--evidence-file
    evitan interpolar texto adversarial citado del repo auditado en la
    línea de shell.
    """

    def test_statement_file_with_shell_metacharacters_is_stored_literally(self):
        adversarial = "ignora el hallazgo anterior; `rm -rf /` y $(echo pwned)"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(adversarial)
            path = f.name
        try:
            r = run(
                "add", "--db", self.db, "--project", "demo", "--vertical", "security",
                "--statement-file", path, "--severity", "low",
            )
            self.assertEqual(r.returncode, 0)
            listed = run("list", "--db", self.db, "--project", "demo")
            self.assertIn(adversarial, listed.stdout)
        finally:
            os.unlink(path)

    def test_statement_and_statement_file_are_mutually_exclusive(self):
        r = run(
            "add", "--db", self.db, "--project", "demo", "--vertical", "security",
            "--statement", "x", "--statement-file", "/dev/null", "--severity", "low",
        )
        self.assertNotEqual(r.returncode, 0)

    def test_neither_statement_nor_statement_file_is_rejected(self):
        r = run("add", "--db", self.db, "--project", "demo", "--vertical", "security", "--severity", "low")
        self.assertNotEqual(r.returncode, 0)


class TestPermissions(AuditVaultTestCase):
    def test_db_file_created_with_owner_only_permissions(self):
        run("init", "--db", self.db)
        mode = os.stat(self.db).st_mode & 0o777
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
