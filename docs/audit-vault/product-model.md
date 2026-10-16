---
tipo: product-model
proyecto: audit-harness
fecha_ultima_actualizacion: 2026-10-16
---

# Cómo funciona este producto

Esta nota NO viaja a otro proyecto — se reconstruye desde cero en cada
instalación nueva del harness. Hermes y los auditores la leen antes de auditar
para entender el dominio, no solo el código.

## Qué hace el producto

No es una app con usuarios finales — es un **plugin de Claude Code**: un
conjunto de definiciones de agentes/skills en Markdown (prompts de sistema
para subagentes) más un CLI de Python sin dependencias
(`bin/audit_vault.py`) que persiste hallazgos en SQLite. Se instala en
cualquier máquina/proyecto vía marketplace de plugin, y corre auditorías
agénticas (seguridad, integridad de datos, build, infra, y 13 verticales de
producto/legal/ops) sobre OTROS repos — este mismo repo es, irónicamente, el
primer sujeto de su propia vertical `overengineering`.

## Arquitectura real (no la ideal)

- `plugins/audit-harness/agents/*.md` — 24 agentes (prompts de sistema para
  subagentes): 1 orquestador (Hermes), 3 leads temáticos, 1 report-assembler,
  19 auditores de dominio (6 núcleo + 13 verticales). Ningún código
  ejecutable — es texto que la CLI de Claude Code interpreta como system
  prompt de un subagente.
- `plugins/audit-harness/skills/*/SKILL.md` — 6 skills (flujos invocables con
  `/audit-harness:<nombre>`), también texto puro interpretado como
  instrucciones, no código.
- `plugins/audit-harness/bin/audit_vault.py` — el único código ejecutable
  real del repo. CLI Python 3, stdlib-only (`sqlite3`, `argparse`,
  `datetime`), sin dependencias de terceros. Mantiene `facts.db`
  (SQLite+FTS5) por proyecto auditado.
- `plugins/audit-harness/hooks/session-start.py` — segundo (y último) script
  ejecutable real: hook de `SessionStart`, lee JSON de stdin, no tiene
  dependencias externas.
- `plugins/audit-harness/templates/vault/*.template.md` — plantillas de
  notas Markdown que cada proyecto auditado copia a su propio
  `docs/audit-vault/`.
- Nada de esto corre como servidor. No hay proceso de larga duración, no hay
  puerto abierto, no hay base de datos compartida entre usuarios — cada
  instalación del plugin opera localmente dentro de una sesión de Claude
  Code.

## Entidades sensibles

Ninguna propia. El dato potencialmente sensible no es del harness — es el
código y los hallazgos de seguridad de LOS PROYECTOS QUE AUDITA, que quedan
en el `facts.db` de CADA proyecto auditado (nunca en este repo). Este repo
en sí no persiste código ni secretos de terceros.

## Multi-tenancy / aislamiento

No aplica — no hay usuarios ni clientes de este "producto" en el sentido de
una app multi-tenant. Cada instalación es de un solo desarrollador sobre su
propia máquina/proyecto.

## Puntos de entrada externos

- Ninguna API pública ni webhook. El único "input externo" real es: (a) el
  contenido de los repos que audita (código ajeno que los auditores leen
  dentro de su propio contexto — esto SÍ es una superficie real de prompt
  injection, de ahí que `llm-security` esté habilitado en
  `audit.config.yaml` para esta auto-auditoría), y (b) el JSON de stdin que
  recibe `hooks/session-start.py` en cada arranque de sesión de Claude Code.

## Reglas y memoria propias (fuente primaria para auditores)

Este proyecto NO tiene documentación propia de reglas/incidentes todavía —
no existe `CLAUDE.md`, no existe `.claude/rules/*.md`, no existe un vault de
aprendizajes propio (Obsidian u otro) dentro de este repo. Las únicas
decisiones de diseño documentadas viven en la sección "Decisiones tomadas
durante la construcción" de `plugins/audit-harness/README.md` — no sigue el
formato de nota atómica de ningún otro proyecto, es prosa narrativa dentro
del README. Los auditores de dominio no tienen ninguna fuente primaria
propia que priorizar sobre sus checks genéricos en esta corrida.
