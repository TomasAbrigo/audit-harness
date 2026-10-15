#!/usr/bin/env bash
# Instala el pre-push gate en el repo actual. Correr desde la raiz del repo
# que se quiere auditar (no desde el repo del harness).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [ -z "$REPO_ROOT" ]; then
  echo "error: no estas dentro de un repo git" >&2
  exit 1
fi

mkdir -p "$REPO_ROOT/.githooks"
cp "$SCRIPT_DIR/../templates/hooks/pre-push.sh" "$REPO_ROOT/.githooks/pre-push"
chmod +x "$REPO_ROOT/.githooks/pre-push"
git -C "$REPO_ROOT" config core.hooksPath .githooks

echo "pre-push gate instalado en $REPO_ROOT/.githooks/pre-push"
echo "core.hooksPath configurado -- el hook queda committeado y se comparte con el equipo"

if ! claude plugin list 2>/dev/null | grep -q "audit-harness@"; then
  echo ""
  echo "aviso: el plugin audit-harness no parece estar instalado en esta maquina."
  echo "el hook va a fallar en silencio (deja pasar el push) hasta que corras:"
  echo "  claude plugin install audit-harness@audit-harness-marketplace"
fi
