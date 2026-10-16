#!/usr/bin/env python3
"""SessionStart hook: nudges toward /audit-harness:tutorial.

Stdlib-only, same philosophy as bin/audit_vault.py -- no dependencies to
install for a hook that runs on every session start of every project where
the plugin is installed.
"""
import json
import os
import sys


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        input_data = {}

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

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))


if __name__ == "__main__":
    main()
