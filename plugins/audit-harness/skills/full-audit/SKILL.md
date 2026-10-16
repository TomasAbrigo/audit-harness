---
name: full-audit
description: Auditoría a demanda sobre código ya existente (no solo desarrollo nuevo) -- completa por default, o acotada a un lead/vertical puntual vía argumento (ej. "security", "multi-tenant"). Despacha a Hermes con los auditores del alcance resuelto y todos los MCPs conectados, y termina en un reporte armado por el report-assembler.
disable-model-invocation: true
---

Corré esto como `/audit-harness:full-audit [alcance]`. Requiere que
`audit-setup` ya haya corrido al menos una vez en este proyecto (si no existe
`audit.config.yaml`, corré ese primero).

**Ejemplos:**
```
/audit-harness:full-audit                  -> todo lo habilitado en audit.config.yaml
/audit-harness:full-audit security         -> solo ese vertical/auditor
/audit-harness:full-audit security-legal   -> solo ese lead (y su fan-out interno)
/audit-harness:full-audit multi-tenant cv-drift   -> varios verticales puntuales
```
También podés pedirlo en prosa libre ("auditá solo RLS") — $ARGUMENTS es el
atajo corto para no tener que escribirlo, no la única forma.

## Qué hacer

1. Leé `audit.config.yaml` para saber `verticals_enabled`,
   `pentest_active_envs` y `vault_path`.

1.5. **Resolvé el alcance.** Si `$ARGUMENTS` no está vacío, interpretá cada
   token como nombre de lead (`security-legal`, `code-quality`,
   `infra-ops-producto`) o de vertical/auditor puntual (`security`, `pentest`,
   `data-integrity`, `build`, `infra`, `multi-tenant`, `llm-security`,
   `cv-drift`, `testing-coverage`, `finops`, `backup-dr`, `sbom`, `docker`,
   `cicd`, `incident-response`, `accessibility`, `feature-flags`,
   `privacy-minors`) — ese es el alcance acotado, ignorá el resto de
   `verticals_enabled` para esta corrida. Si está vacío, el alcance es "todo
   lo habilitado en `audit.config.yaml`". Si un token no matchea ningún lead
   ni vertical conocido, preguntale al usuario en vez de adivinar o ignorarlo
   en silencio.

2. Invocá al subagente `hermes` (vía el tool `Agent`) pasándole: el alcance
   resuelto en el paso 1.5, el path del proyecto, y el `vault_path`. Hermes se
   encarga de despachar los auditores — no despaches vos los auditores de
   dominio directamente, eso rompe el diseño (Hermes necesita ser quien
   consulta `facts.db` antes de cada despacho).

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
