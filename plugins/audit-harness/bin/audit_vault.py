#!/usr/bin/env python3
"""
audit_vault.py — fact store del audit harness (SQLite + FTS5, embebido, sin servicio).

Un hecho (fact) es un hallazgo atómico de una auditoría: "endpoint X carece de
rate limiting", severidad alta, evidencia "backend/app/routes/x.py:42". El store
existe para dos cosas, nada más:

  1. no repetir el mismo hallazgo en cada corrida (dedupe vía `search` antes de
     que un auditor escriba, y antes de que Hermes despache)
  2. correlacionar hallazgos de distintas verticales con la misma causa raíz
     (`search --cross-vertical`, usado por el report-assembler)

No reemplaza el vault de notas Markdown (docs/audit-vault/*.md): ese es para
conocimiento narrativo curado (playbooks, best-practices, product-model). Este
es para cientos de hallazgos chicos que no merecen nota propia.

Uso:
  audit_vault.py init     --db PATH
  audit_vault.py add      --db PATH --project P --vertical V --statement S --severity SEV [--evidence E]
  audit_vault.py search   --db PATH [--project P] [--vertical V] [--status open] [--cross-vertical] QUERY
  audit_vault.py list     --db PATH [--project P] [--vertical V] [--status open]
  audit_vault.py resolve  --db PATH ID --by COMMIT_OR_PR [--wontfix]
"""

import argparse
import datetime
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

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
  statement, evidence, content='facts', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
  INSERT INTO facts_fts(rowid, statement, evidence) VALUES (new.id, new.statement, new.evidence);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, statement, evidence) VALUES('delete', old.id, old.statement, old.evidence);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, statement, evidence) VALUES('delete', old.id, old.statement, old.evidence);
  INSERT INTO facts_fts(rowid, statement, evidence) VALUES (new.id, new.statement, new.evidence);
END;
"""


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
        """INSERT INTO facts (project, vertical, statement, severity, evidence, detected_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (args.project, args.vertical, args.statement, args.severity, args.evidence, now_iso()),
    )
    conn.commit()
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
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if args.cross_vertical:
        by_evidence: dict = {}
        for r in rows:
            key = (r["evidence"] or "").strip()
            by_evidence.setdefault(key, []).append(r)
        correlated = {k: v for k, v in by_evidence.items() if k and len(v) > 1}
        if correlated:
            print("-- hallazgos correlacionados (misma evidencia, distinta vertical) --")
            for evidence, group in correlated.items():
                verticals = sorted({g["vertical"] for g in group})
                print(f"\n{evidence}  (verticales: {', '.join(verticals)})")
                _print_rows(group)
            print("\n-- resto --")
        _print_rows([r for r in rows if (r["evidence"] or "").strip() not in correlated])
    else:
        _print_rows(rows)


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

    p_add = sub.add_parser("add", help="registra un hallazgo nuevo")
    p_add.add_argument("--db", required=True)
    p_add.add_argument("--project", required=True)
    p_add.add_argument("--vertical", required=True)
    p_add.add_argument("--statement", required=True)
    p_add.add_argument("--severity", required=True, choices=["critical", "high", "medium", "low"])
    p_add.add_argument("--evidence", default=None)
    p_add.set_defaults(func=cmd_add)

    p_search = sub.add_parser("search", help="full-text search (dedupe antes de escribir o despachar)")
    p_search.add_argument("--db", required=True)
    p_search.add_argument("--project", default=None)
    p_search.add_argument("--vertical", default=None)
    p_search.add_argument("--status", default=None, choices=["open", "resolved", "wontfix"])
    p_search.add_argument("--cross-vertical", action="store_true", help="ignora --vertical, agrupa por evidencia superpuesta")
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_search)

    p_list = sub.add_parser("list", help="lista sin full-text search")
    p_list.add_argument("--db", required=True)
    p_list.add_argument("--project", default=None)
    p_list.add_argument("--vertical", default=None)
    p_list.add_argument("--status", default=None, choices=["open", "resolved", "wontfix"])
    p_list.set_defaults(func=cmd_list)

    p_resolve = sub.add_parser("resolve", help="cierra un hallazgo")
    p_resolve.add_argument("--db", required=True)
    p_resolve.add_argument("id", type=int)
    p_resolve.add_argument("--by", required=True, help="commit o PR que lo resolvió")
    p_resolve.add_argument("--wontfix", action="store_true", help="cerrar como wontfix en vez de resolved")
    p_resolve.set_defaults(func=cmd_resolve)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
