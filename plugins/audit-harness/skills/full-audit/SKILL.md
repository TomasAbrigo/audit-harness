---
name: full-audit
description: Auditoría completa del proyecto, a demanda, sobre código ya existente (no solo desarrollo nuevo). Despacha a Hermes con todos los auditores habilitados y todos los MCPs conectados, y termina en un reporte armado por el report-assembler.
disable-model-invocation: true
---

Corré esto como `/audit-harness:full-audit`. Requiere que `audit-setup` ya haya
corrido al menos una vez en este proyecto (si no existe `audit.config.yaml`,
corré ese primero).

## Qué hacer

1. Leé `audit.config.yaml` para saber `verticals_enabled`,
   `pentest_active_envs` y `vault_path`.

2. Invocá al subagente `hermes` (vía el tool `Agent`) pasándole: el alcance
   pedido por el usuario (todo, o un subconjunto de verticales), el path del
   proyecto, y el `vault_path`. Hermes se encarga de despachar los auditores —
   no despaches vos los auditores de dominio directamente, eso rompe el
   diseño (Hermes necesita ser quien consulta `facts.db` antes de cada
   despacho).

3. Cuando Hermes confirme que terminó de despachar y disparó al
   `report-assembler`, esperá su resultado — no lo generes vos ni lo
   adivines.

4. Una vez que el `report-assembler` entregue el reporte, publicalo como
   Artifact (seguí la guía de artifacts del entorno para el diseño) y
   mencioná, en texto, un resumen de una o dos líneas por severidad — no
   repitas el reporte completo en el chat, el Artifact es la fuente.

5. Si el usuario quiere implementar los fixes (no solo leer el reporte),
   el siguiente paso es `/audit-harness:remediate` — ese skill, no este,
   cubre triage por riesgo, GitFlow, paralelización segura y la
   re-auditoría dirigida al final.

## Nota sobre alcance

"Con todo su poder" significa: todos los MCPs que estén conectados en la
sesión (Supabase, Vercel, GitHub, y los que correspondan) y todos los
auditores en `verticals_enabled` — no un subconjunto arbitrario. Si el usuario
pidió explícitamente un dominio puntual ("auditá solo seguridad"), respetá eso
y no despaches el resto.
