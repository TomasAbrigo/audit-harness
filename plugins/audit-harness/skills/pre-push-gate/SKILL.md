---
name: pre-push-gate
description: Revisión manual del diff antes de un push — 3 capas (seguridad, estructural, automatización/patrones del proyecto). Corré esto vos mismo en tu sesión de Claude Code antes de pushear; no hay ningún hook de git que se dispare solo.
disable-model-invocation: true
---

Corré esto como `/audit-harness:pre-push-gate` antes de un `git push`, dentro
de tu sesión normal de Claude Code — con supervisión real, no en background.
No existe un hook de git que te lo imponga automáticamente: la decisión de
correrlo es tuya, cada vez.

## Primero, conseguí el diff vos mismo

```bash
BASE="$(git merge-base HEAD @{upstream} 2>/dev/null || git merge-base HEAD origin/main 2>/dev/null)"
git diff "$BASE"...HEAD
```

Si no hay upstream configurado, usá la rama contra la que vas a abrir el PR.

## Revisalo en 3 capas, en este orden

### Capa 1 — Seguridad (la que debería hacerte frenar el push)

- Secretos commiteados: API keys, tokens, connection strings, credenciales.
- Inyección (SQL, comandos, path traversal) en código nuevo.
- Un endpoint nuevo sin chequeo de auth donde los endpoints vecinos sí lo
  tienen.

Cualquier hallazgo acá es **severidad crítica**.

### Capa 2 — Estructural

- Imports que no van a resolver (típico de código con una API inventada).
- Una función/endpoint que el diff remueve pero que todavía se llama en otro
  lado del repo.
- Sobre-ingeniería evidente para el tamaño del cambio real (una abstracción
  nueva para un solo caso de uso).

Severidad alta/media — avisa, no bloquea.

### Capa 3 — Automatización / patrones ya resueltos en el proyecto

- Si existe `.claude/rules/*.md` en el repo, comprobá que el diff no reinventa
  un patrón que esa regla ya resuelve (ej. paginación manual donde hay un
  helper documentado, `insert` donde la regla pide `upsert`). Citá la regla
  concreta si aplica — no un "podría estar mal", el archivo y la línea de la
  regla.
- Señalá, sin bloquear, si el diff toca un área que un auditor de dominio del
  harness debería revisar más a fondo (ej. toca políticas RLS → "convendría
  correr el auditor de multi-tenant antes de mergear esto").

## Dedupe con el fact store

Si existe `docs/audit-vault/facts.db` en el repo, antes de reportar un
hallazgo de capa 2 o 3, consultá si ya está registrado como `open`:

```
python3 <plugin-root>/bin/audit_vault.py search --db docs/audit-vault/facts.db \
  --status open "<tema>"
```

Si ya está, no lo repitas en el aviso — ya se sabe. Si es nuevo, registralo
con `audit_vault.py add` antes de terminar.

## Cerrá con un veredicto claro

Listá los hallazgos agrupados por capa, cada uno con archivo:línea. Terminá
con uno de estos dos veredictos, explícito:

- **No pushear todavía** — si encontraste algo de Capa 1, con qué hay que
  arreglar antes.
- **OK para pushear** — si no hay nada de Capa 1 (lo de Capa 2/3 queda a tu
  criterio, son avisos, no bloqueos).
