# audit-harness

Marketplace propio de Claude Code para el harness de auditoría agéntica:
Hermes despacha auditores de seguridad, pentest activo, integridad de datos,
arquitectura, build e infra sobre cualquier proyecto — con un fact store
propio (SQLite+FTS5) para no repetir hallazgos entre corridas, y un vault de
conocimiento (playbooks + best-practices) que viaja de proyecto en proyecto.

Diseño completo (arquitectura, decisiones y roadmap) en el Artifact de mapa
del harness — no documentado acá, ese documento es la fuente de verdad del
diseño.

## Instalar en este u otro proyecto

Ya instalado en esta máquina a nivel usuario (`scope: user`) — está disponible
en cualquier sesión de Claude Code en cualquier proyecto, sin pasos extra.

Para instalarlo en otra máquina:

```bash
claude plugin marketplace add /ruta/a/audit-harness
claude plugin install audit-harness@audit-harness-marketplace
```

o, para desarrollo/testing sin instalar nada:

```bash
claude --plugin-dir /ruta/a/audit-harness/plugins/audit-harness
```

## Primer uso en un proyecto

Dentro de una sesión de Claude Code, en la raíz del repo que querés auditar:

```
/audit-harness:audit-setup
```

Detecta qué servicios ya están conectados, genera `audit.config.yaml` y
bootstrapea `docs/audit-vault/` (incluido `facts.db`). Después:

```
/audit-harness:full-audit
```

Antes de cada `git push`, corré manualmente (decisión explícita: sin hook que
se auto-dispare):

```
/audit-harness:pre-push-gate
```

## Estado — Fase 1 + 2 del roadmap

Implementado y validado (`claude plugin validate` pasa, instalación probada
de punta a punta):

- Hermes (orquestador, solo despacha/trackea) + report-assembler (separado,
  corre correlación cruzada entre verticales antes de reportar)
- 5 auditores núcleo: security, offensive (pentest local/staging), data
  integrity, build, infra
- `bin/audit_vault.py` — fact store SQLite+FTS5 funcional (init/add/search/
  list/resolve, incluida la búsqueda `--cross-vertical`)
- Skills `/audit-harness:audit-setup`, `/audit-harness:full-audit`,
  `/audit-harness:feature-flow` (encadena grill-with-docs → to-prd →
  to-issues → triage → tdd con gates de confirmación) y
  `/audit-harness:pre-push-gate` (3 capas: seguridad/estructural/
  automatización — **invocación manual, a propósito**: un hook de git que se
  dispara solo en cada push, headless y sin supervisión, quedó descartado por
  el clasificador de permisos de Auto Mode — y con razón)
- Plantillas del vault de conocimiento (`playbook`, `best-practice`,
  `product-model`)

Pendiente (próxima fase, no implementado todavía):

- Las 13 verticales adicionales (producto/legal/ops/IA) del mapa original
- Jerarquía de 2 niveles (leads temáticos) — solo si una corrida real llega a
  8+ auditores simultáneos
