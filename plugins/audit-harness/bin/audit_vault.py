#!/usr/bin/env python3
"""
audit_vault.py — fact store del audit harness (SQLite + FTS5, embebido, sin servicio).

Un hecho (fact) es un hallazgo atómico de una auditoría: "endpoint X carece de
rate limiting", severidad alta, evidencia "backend/app/routes/x.py:42". El store
existe para dos cosas, nada más:

  1. no repetir el mismo hallazgo en cada corrida (dedupe vía `search` antes de
     que un auditor escriba, y antes de que Hermes despache; reforzado con un
     UNIQUE index -- ver SCHEMA -- para que un `search` que falla o un caller
     que se olvida de dedupear no produzca filas duplicadas en silencio)
  2. correlacionar hallazgos de distintas verticales con la misma causa raíz
     (`search --cross-vertical`, usado por el report-assembler; agrupa por
     archivo+línea superpuesta extraído del campo evidence, no por igualdad
     exacta del string -- dos evidencias "x.py:42" y "x.py:42-45 (detalle)"
     correlacionan)

No reemplaza el vault de notas Markdown (docs/audit-vault/*.md): ese es para
conocimiento narrativo curado (playbooks, best-practices, product-model). Este
es para cientos de hallazgos chicos que no merecen nota propia.

Uso:
  audit_vault.py init     --db PATH
  audit_vault.py add      --db PATH --project P --vertical V --statement S --severity SEV [--evidence E]
  audit_vault.py search   --db PATH [--project P] [--vertical V] [--status open] [--cross-vertical] QUERY
  audit_vault.py list     --db PATH [--project P] [--vertical V] [--status open]
  audit_vault.py resolve  --db PATH ID --by COMMIT_OR_PR [--wontfix] [--project P]

Límite conocido de `init`/el idempotente `executescript(SCHEMA)` en cada comando:
`CREATE TABLE IF NOT EXISTS` no migra una tabla ya existente. Si una versión
futura necesita agregar una columna a `facts`, un `facts.db` viejo no se va a
actualizar solo -- hace falta un paso de migración explícito (`ALTER TABLE`)
en ese momento. No se construye un framework de migraciones ahora porque no
hay ningún cambio de schema pendiente que lo justifique (YAGNI) -- esto es
una limitación documentada, no un bug a ciegas.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sqlite3
import sys

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project TEXT NOT NULL,
  vertical TEXT NOT NULL,
  statement TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('critical','high','medium','low')),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','wontfix')),
  evidence TEXT,
  detected_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT
);

-- Dedupe real, no solo por convención del llamador: dos 'add' con los mismos
-- project/vertical/statement/evidence no crean dos filas. Nota de SQLite: un
-- NULL nunca es IGUAL a otro NULL para efectos de UNIQUE, así que esto no
-- dedupea dos facts con evidence=NULL -- en la práctica evidence siempre se
-- pasa, así que no se construye nada extra para ese caso límite.
CREATE UNIQUE INDEX IF NOT EXISTS ux_facts_dedupe
  ON facts(project, vertical, statement, evidence);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
  statement, evidence, content='facts', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
  INSERT INTO facts_fts(rowid, statement, evidence) VALUES (new.id, new.statement, new.evidence);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, statement, evidence) VALUES('delete', old.id, old.statement, old.evidence);
END;

-- No hay trigger AFTER UPDATE a propósito: el único UPDATE real (cmd_resolve)
-- nunca toca statement/evidence (las dos columnas indexadas en facts_fts),
-- así que no hay nada que resincronizar. Si en el futuro se agrega un
-- comando que edite statement/evidence de un fact ya creado, reintroducí un
-- trigger AFTER UPDATE (mismo patrón que facts_ad + facts_ai combinados)
-- ANTES de ese comando, no después.
"""

# Extrae referencias "archivo:línea" o "archivo:línea-línea" de un campo
# evidence de texto libre (puede tener varias, separadas por "; ", "," o
# dentro de paréntesis). No es un parser perfecto -- es una heurística barata
# para correlacionar hallazgos por ubicación real en vez de por igualdad
# exacta de string.
_LOC_RE = re.compile(r"([^\s,;()]+\.\w+):(\d+)(?:-(\d+))?")


def _parse_locations(evidence: str | None) -> list[tuple[str, int, int]]:
    if not evidence:
        return []
    out = []
    for path, start, end in _LOC_RE.findall(evidence):
        start_i = int(start)
        end_i = int(end) if end else start_i
        out.append((path, start_i, end_i))
    return out


def _locations_overlap(locs_a, locs_b) -> bool:
    for pa, sa, ea in locs_a:
        for pb, sb, eb in locs_b:
            if pa == pb and sa <= eb and sb <= ea:
                return True
    return False


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def cmd_init(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"facts.db listo en {args.db}")


def cmd_add(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    conn.executescript(SCHEMA)  # idempotente: asegura schema aunque no se haya corrido init
    cur = conn.execute(
        """INSERT OR IGNORE INTO facts (project, vertical, statement, severity, evidence, detected_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (args.project, args.vertical, args.statement, args.severity, args.evidence, now_iso()),
    )
    conn.commit()
    if cur.rowcount == 0:
        existing = conn.execute(
            "SELECT id FROM facts WHERE project = ? AND vertical = ? AND statement = ? AND evidence IS ?",
            (args.project, args.vertical, args.statement, args.evidence),
        ).fetchone()
        conn.close()
        existing_id = existing["id"] if existing else "?"
        print(f"fact ya existe (#{existing_id}), no se duplica ({args.vertical})")
        return
    fact_id = cur.lastrowid
    conn.close()
    print(f"fact #{fact_id} creado ({args.severity}, {args.vertical})")


def _print_rows(rows) -> None:
    if not rows:
        print("(sin resultados)")
        return
    for r in rows:
        tag = f"#{r['id']} [{r['severity']}/{r['status']}] {r['vertical']}"
        print(f"{tag} — {r['statement']}")
        if r["evidence"]:
            print(f"    evidencia: {r['evidence']}")


def cmd_search(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    conn.executescript(SCHEMA)
    sql = """
        SELECT f.* FROM facts f
        JOIN facts_fts ON facts_fts.rowid = f.id
        WHERE facts_fts MATCH ?
    """
    params: list = [args.query]
    if args.project:
        sql += " AND f.project = ?"
        params.append(args.project)
    if args.vertical and not args.cross_vertical:
        sql += " AND f.vertical = ?"
        params.append(args.vertical)
    if args.status:
        sql += " AND f.status = ?"
        params.append(args.status)
    sql += " ORDER BY f.detected_at DESC"
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        print(
            f"query FTS5 inválida: {e}\n"
            "FTS5 interpreta comillas, '*', '-', 'AND/OR/NOT' y 'columna:término' como "
            "sintaxis propia, no texto literal -- envolvé el término en comillas dobles "
            'si contiene caracteres especiales, ej. search \'"check-in"\'.',
            file=sys.stderr,
        )
        sys.exit(1)
    conn.close()

    if not args.cross_vertical:
        _print_rows(rows)
        return

    n = len(rows)
    locs = [_parse_locations(r["evidence"]) for r in rows]
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        if not locs[i]:
            continue
        for j in range(i + 1, n):
            if locs[j] and _locations_overlap(locs[i], locs[j]):
                union(i, j)

    groups: dict = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    correlated_indices = {root for root, idxs in groups.items() if len(idxs) > 1}
    if correlated_indices:
        print("-- hallazgos correlacionados (archivo+línea superpuesta, no string exacto) --")
        for root in correlated_indices:
            idxs = groups[root]
            group_rows = [rows[i] for i in idxs]
            verticals = sorted({r["vertical"] for r in group_rows})
            locations = sorted({
                f"{p}:{s}" + (f"-{e}" if e != s else "")
                for i in idxs for p, s, e in locs[i]
            })
            print(f"\n{'; '.join(locations)}  (verticales: {', '.join(verticals)})")
            _print_rows(group_rows)
        print("\n-- resto --")

    standalone = [rows[i] for i in range(n) if find(i) not in correlated_indices]
    _print_rows(standalone)


def cmd_list(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    conn.executescript(SCHEMA)
    sql = "SELECT * FROM facts WHERE 1=1"
    params: list = []
    if args.project:
        sql += " AND project = ?"
        params.append(args.project)
    if args.vertical:
        sql += " AND vertical = ?"
        params.append(args.vertical)
    if args.status:
        sql += " AND status = ?"
        params.append(args.status)
    sql += " ORDER BY detected_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    _print_rows(rows)


def cmd_resolve(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    conn.executescript(SCHEMA)

    if args.project:
        owner = conn.execute("SELECT project FROM facts WHERE id = ?", (args.id,)).fetchone()
        if owner is None:
            conn.close()
            print(f"no existe el fact #{args.id}", file=sys.stderr)
            sys.exit(1)
        if owner["project"] != args.project:
            conn.close()
            print(
                f"fact #{args.id} pertenece al proyecto '{owner['project']}', "
                f"no a '{args.project}' -- no se modifica",
                file=sys.stderr,
            )
            sys.exit(1)

    status = "wontfix" if args.wontfix else "resolved"
    cur = conn.execute(
        "UPDATE facts SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
        (status, now_iso(), args.by, args.id),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if changed:
        print(f"fact #{args.id} marcado como {status} (por {args.by})")
    else:
        print(f"no existe el fact #{args.id}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    p = argparse.ArgumentParser(description="Fact store del audit harness (SQLite+FTS5)")
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="crea facts.db y el schema si no existen")
    p_init.add_argument("--db", required=True)
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="registra un hallazgo nuevo (idempotente: un duplicado exacto no crea fila nueva)")
    p_add.add_argument("--db", required=True)
    p_add.add_argument("--project", required=True)
    p_add.add_argument("--vertical", required=True)
    p_add.add_argument("--statement", required=True)
    p_add.add_argument("--severity", required=True, choices=["critical", "high", "medium", "low"])
    p_add.add_argument("--evidence", default=None)
    p_add.set_defaults(func=cmd_add)

    p_search = sub.add_parser("search", help="full-text search (dedupe antes de escribir o despachar)")
    p_search.add_argument("--db", required=True)
    p_search.add_argument("--project", default=None, help="si se omite, busca en TODOS los proyectos de este facts.db")
    p_search.add_argument("--vertical", default=None)
    p_search.add_argument("--status", default=None, choices=["open", "resolved", "wontfix"])
    p_search.add_argument("--cross-vertical", action="store_true", help="ignora --vertical, agrupa por archivo+línea superpuesta")
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_search)

    p_list = sub.add_parser("list", help="lista sin full-text search")
    p_list.add_argument("--db", required=True)
    p_list.add_argument("--project", default=None, help="si se omite, lista TODOS los proyectos de este facts.db")
    p_list.add_argument("--vertical", default=None)
    p_list.add_argument("--status", default=None, choices=["open", "resolved", "wontfix"])
    p_list.set_defaults(func=cmd_list)

    p_resolve = sub.add_parser("resolve", help="cierra un hallazgo")
    p_resolve.add_argument("--db", required=True)
    p_resolve.add_argument("id", type=int)
    p_resolve.add_argument(
        "--by", required=True,
        help="commit o PR que lo resolvió -- convención: '<sha-corto> (#PR)', ej. '6268cb9 (#201)'",
    )
    p_resolve.add_argument("--wontfix", action="store_true", help="cerrar como wontfix en vez de resolved")
    p_resolve.add_argument(
        "--project", default=None,
        help="opcional: si se pasa, verifica que el fact pertenezca a este proyecto antes de modificarlo "
             "(defensa extra si un facts.db llegara a compartirse entre proyectos)",
    )
    p_resolve.set_defaults(func=cmd_resolve)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
