#!/usr/bin/env python3
"""SessionStart hook: nudges toward /audit-harness:tutorial.

Stdlib-only, same philosophy as bin/audit_vault.py -- no dependencies to
install for a hook that runs on every session start of every project where
the plugin is installed.

Nunca debe crashear visiblemente el arranque de una sesión: cualquier error
se loguea a archivo (ver _log_error) y el hook responde con un contexto
mínimo en vez de abortar sin salida.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import traceback


def _log_dir() -> str:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return os.path.join(base, "audit-harness")


def _log_error(exc: BaseException) -> None:
    try:
        d = _log_dir()
        os.makedirs(d, exist_ok=True)
        log_path = os.path.join(d, "hook-errors.log")
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] session-start.py: {exc!r}\n")
            f.write(traceback.format_exc())
            f.write("\n")
        os.chmod(log_path, 0o600)  # puede acumular rutas/tracebacks locales -- solo el dueño lo lee
    except OSError:
        pass  # el logging de errores nunca debe ser, en sí mismo, otra fuente de crash


def _print_context(context: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))


def main() -> None:
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        raw = {}

    # json.load acepta cualquier JSON válido -- un objeto, pero también una
    # lista, un string, un número o null. Si no es un dict, .get() más abajo
    # rompería con AttributeError; tratamos "válido pero con forma rara"
    # igual que "inválido".
    input_data = raw if isinstance(raw, dict) else {}

    cwd = input_data.get("cwd") or os.getcwd()
    configured = os.path.isfile(os.path.join(cwd, "audit.config.yaml"))

    if not configured:
        context = (
            "El plugin audit-harness está instalado pero este proyecto todavía "
            "no está conectado (no existe audit.config.yaml en la raíz). Si es "
            "relevante para lo que el usuario está pidiendo, o si esta parece "
            "ser la primera vez que se usa el harness en este repo, decile en "
            "tus propias palabras algo como: 'Instalé audit-harness. Escribí "
            "/audit-harness:tutorial para ver todos los flujos, o "
            "/audit-harness:audit-setup para conectarlo a este proyecto.' No "
            "lo repitas si el usuario ya lo sabe o ya está en medio de otra "
            "tarea claramente no relacionada."
        )
    else:
        context = (
            "audit-harness ya está conectado a este proyecto "
            "(audit.config.yaml existe). Si en algún momento resulta relevante "
            "y el usuario no parece saberlo, podés mencionar que "
            "/audit-harness:tutorial lista todos los flujos disponibles -- no "
            "hace falta decirlo proactivamente en cada sesión."
        )

    _print_context(context)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # nunca dejar que esto rompa el arranque de sesión del usuario
        _log_error(exc)
        _print_context(
            "audit-harness: el hook de SessionStart encontró un error interno "
            "(logueado en ~/.claude/audit-harness/hook-errors.log). No es "
            "necesario que menciones esto al usuario salvo que pregunte por "
            "problemas con el plugin."
        )
