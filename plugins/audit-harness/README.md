# audit-harness (plugin)

Componentes:

- `agents/hermes.md` — orquestador. Despacha, consulta `facts.db` antes de
  cada despacho, nunca agrega los hallazgos crudos en su propio contexto.
- `agents/report-assembler.md` — subagente separado de Hermes. Lee solo el
  vault (facts.db + notas Markdown), corre correlación cruzada entre
  verticales, escribe el reporte final.
- `agents/security-auditor.md`, `offensive-auditor.md`,
  `data-integrity-auditor.md`, `build-optimizer.md`, `infra-auditor.md` —
  auditores núcleo.
- `skills/audit-setup/` — wizard de conexión de servicios + bootstrap.
- `skills/full-audit/` — entrada para una auditoría completa a demanda.
- `bin/audit_vault.py` — CLI del fact store (sin dependencias externas, solo
  stdlib: `sqlite3`, `argparse`, `datetime`).
- `templates/vault/` — plantillas de notas del vault de conocimiento.

Cada agente referencia `<plugin-root>/bin/audit_vault.py` — cuando el plugin
está instalado vía marketplace, ese path es el del plugin instalado en
`~/.claude/plugins/`; cuando se corre con `--plugin-dir` para desarrollo, es
la ruta local que le pasaste al flag.
