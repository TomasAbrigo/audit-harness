---
name: pre-push-gate
description: Revisión headless del diff antes de un push — 3 capas (seguridad, estructural, automatización/patrones del proyecto). Severidad crítica bloquea el push; el resto solo avisa. Pensado para correr vía `claude -p` desde el hook .githooks/pre-push, pero también se puede invocar manualmente para un dry-run.
disable-model-invocation: true
---

Te llega un diff (contra la base del push) en el prompt. Revisalo en 3 capas,
en este orden, priorizando lo que más importa primero.

## Capa 1 — Seguridad (la que puede bloquear el push)

- Secretos commiteados: API keys, tokens, connection strings, credenciales.
- Inyección (SQL, comandos, path traversal) en código nuevo.
- Un endpoint nuevo sin chequeo de auth donde los endpoints vecinos sí lo
  tienen.

Cualquier hallazgo acá es **severidad crítica**.

## Capa 2 — Estructural

- Imports que no van a resolver (típico de código con una API inventada).
- Una función/endpoint que el diff remueve pero que todavía se llama en otro
  lado del repo.
- Sobre-ingeniería evidente para el tamaño del cambio real (una abstracción
  nueva para un solo caso de uso).

Severidad alta/media — avisa, no bloquea.

## Capa 3 — Automatización / patrones ya resueltos en el proyecto

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

## Formato de salida (estricto)

Listá los hallazgos en 3 líneas o menos, cada uno con archivo:línea. Si no hay
nada que avisar, no escribas nada más que la línea final. Terminá tu
respuesta con **exactamente** una de estas dos líneas, y nada después:

- `BLOQUEAR_PUSH` — si encontraste algo de Capa 1
- `PUSH_OK` — si no
