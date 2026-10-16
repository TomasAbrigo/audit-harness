---
name: tutorial
description: Lista todos los flujos del audit-harness -- las 5 fases, cómo acotar el alcance (completo/por lead/por vertical), y dónde vive el vault. Punto de entrada para quien recién instaló el plugin o no se acuerda qué comando usar.
disable-model-invocation: true
---

Corré esto como `/audit-harness:tutorial`. No hace nada más que mostrarte lo
que sigue — no toca archivos ni dispara ningún auditor.

## Las 5 fases, en orden de uso real

| Cuándo | Comando |
|---|---|
| Una vez, al conectar un proyecto nuevo | `/audit-harness:audit-setup` |
| Antes de empezar una feature nueva | `/audit-harness:feature-flow` |
| Cuando quieras saber el estado real del proyecto | `/audit-harness:full-audit` |
| Para implementar los fixes de un full-audit (no solo leerlos) | `/audit-harness:remediate` |
| A mano, antes de cada `git push` | `/audit-harness:pre-push-gate` |

`audit-setup` es el único paso obligatorio antes que los demás — detecta
stack, servicios conectados, y aprende la memoria propia del proyecto
(`CLAUDE.md`, `.claude/rules/*.md`, vault de aprendizajes si tiene uno) para
que el resto no corra genérico.

## Alcance: completo, por lead, o por vertical

`/audit-harness:full-audit` sin argumentos corre **todo** lo habilitado en
`audit.config.yaml`, despachado en 2 niveles (Hermes → 3 leads → hasta 18
auditores). Para acotar:

```
/audit-harness:full-audit                  -> todo
/audit-harness:full-audit security         -> un vertical/auditor puntual
/audit-harness:full-audit security-legal   -> un lead completo (y su fan-out interno)
/audit-harness:full-audit multi-tenant cv-drift   -> varios verticales a la vez
```

o en prosa libre, hablándole a Hermes directamente ("auditá solo RLS",
"corré solo el lead de infra") — el argumento es el atajo corto, no la única
forma.

**Los 3 leads:** `security-legal` (security, pentest, multi-tenant,
llm-security, privacy-minors) · `code-quality` (data-integrity, build,
testing-coverage, cv-drift, arquitectura) · `infra-ops-producto` (infra,
docker, cicd, finops, backup-dr, incident-response, accessibility,
feature-flags, sbom).

Árbol completo y detalle de cada auditor: `agents/hermes.md` y el README del
plugin.

## El vault: dos cerebros, no uno

- **`<vault_path>/facts.db`** — hallazgos crudos de la corrida actual, por
  proyecto. Se consulta con `bin/audit_vault.py` (`list`, `search`,
  `resolve`).
- **`<vault_path>/product-model.md`** — memoria específica de ESTE proyecto
  (dominio, entidades sensibles, multi-tenancy, y sus reglas propias). La
  leen todos los auditores antes de aplicar checks genéricos.
- **`<vault_path>/best-practice.md` y `playbook.md`** — lo generalizable, que
  viaja a cualquier OTRO proyecto donde se instale el harness. Se completan
  solos al final de `full-audit` (vía `report-assembler`) y de `remediate`
  — no hace falta escribirlos a mano.
- Si el proyecto auditado tiene su propia disciplina de aprendizajes (ej. un
  vault de Obsidian declarado en su `CLAUDE.md`), `remediate` también
  escribe ahí, siguiendo esa disciplina — sin pisarla ni inventar una propia.

## Más detalle

- Diseño completo, árbol de agentes, y decisiones tomadas durante la
  construcción: `plugins/audit-harness/README.md`.
- Quick-start de instalación: `README.md` en la raíz del repo.
