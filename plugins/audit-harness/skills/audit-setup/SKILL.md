---
name: audit-setup
description: Wizard de conexión de servicios y bootstrap del audit harness para este proyecto. Detecta qué ya está conectado y solo pide lo que falta; genera audit.config.yaml y el vault inicial.
disable-model-invocation: true
---

Corré esto como `/audit-harness:audit-setup`. Es re-ejecutable — si ya corrió
antes, solo actualiza lo que falta, no pisa lo que ya está configurado.

## 1. Detectar qué ya está conectado

Antes de pedir nada, revisá qué ya existe:

- **GitHub**: `gh auth status` — si falla, hace falta `gh auth login`.
- **Vercel**: ¿hay `.vercel/` en el repo o algún MCP de Vercel disponible en la
  sesión? Si no hay nada, preguntá si el proyecto deploya en Vercel.
- **Supabase**: ¿hay `supabase/` en el repo, o un MCP de Supabase conectado?
- **Render**: ¿hay `render.yaml`? Si lo hay, preguntá si existe
  `RENDER_API_KEY` en el entorno (no lo pidas en texto plano en el chat —
  solo confirmá si está seteada).

Para cada uno, reportá en una lista corta qué está conectado y qué falta —
**solo pedile al usuario lo que falta**, no repitas el flujo completo de algo
que ya funciona.

## 2. Completar `audit.config.yaml`

Si no existe en la raíz del repo, creálo preguntando lo mínimo necesario
(stack detectado automáticamente donde se pueda — mirá `package.json`,
`requirements.txt`/`pyproject.toml`, `Dockerfile` — y confirmá con el usuario
en vez de preguntar todo desde cero):

```yaml
stack: []              # detectado + confirmado
paths:
  backend: ""           # si aplica
  frontend: ""          # si aplica
environments:
  local: {}
  staging: {}
deploy_targets: []
pentest_active_envs: [local]   # nunca agregar "production" sin que el usuario lo pida explícitamente
vault_path: docs/audit-vault/

# núcleo + las 12 verticales activas por default. privacy-minors NO se activa
# acá -- queda apagada hasta que se confirme explícitamente que el proyecto
# trackea datos de menores (ver agents/privacy-minors-auditor.md).
verticals_enabled:
  - security
  - pentest
  - data-integrity
  - build
  - infra
  - multi-tenant
  - llm-security
  - cv-drift
  - testing-coverage
  - finops
  - backup-dr
  - sbom
  - docker
  - cicd
  - incident-response
  - accessibility
  - feature-flags
```

Preguntale al usuario, antes de cerrar el setup, si alguna de estas no aplica
al proyecto (ej. `cv-drift` si no entrena modelos propios, `docker` si no usa
contenedores) — sacala de la lista en vez de dejar que corra sin sentido.

## 2.5. Aprender la memoria propia del proyecto

Este paso es lo que hace que el harness sea útil a ESTE proyecto puntual y no
solo corra checks genéricos. Antes de bootstrapear el vault, buscá qué
documentación propia ya existe:

- `CLAUDE.md` en la raíz (o equivalente) — convenciones, reglas de
  arquitectura, y si declara su propio vault de aprendizajes (ej. un vault de
  Obsidian en `docs/obsidian/`, con su índice y su disciplina de notas).
- `.claude/rules/*.md` — reglas enforceable ya escritas (ej. integridad de
  datos, seguridad) que un auditor de dominio debería usar como fuente
  primaria en vez de sus patrones genéricos.
- ADRs o decisiones de arquitectura documentadas, si el repo tiene algo así
  (`docs/adr/`, `docs/decisions/`, o lo que `CLAUDE.md` señale).

No hace falta leer todo el contenido en detalle acá — alcanza con confirmar
qué existe y en qué path, para que los auditores lo lean ellos mismos cuando
corran.

## 3. Bootstrap del vault

Si `docs/audit-vault/` no existe en el repo que se está auditando:

```bash
mkdir -p docs/audit-vault
python3 <plugin-root>/bin/audit_vault.py init --db docs/audit-vault/facts.db
```

Copiá las plantillas de `<plugin-root>/templates/vault/*.template.md` a
`docs/audit-vault/` quitándoles el sufijo `.template`, solo si no existen ya
(no sobreescribas notas que el usuario ya haya empezado a llenar).

En `product-model.md` (nuevo o ya existente), completá o actualizá la sección
`## Reglas y memoria propias (fuente primaria para auditores)` con lo que
encontraste en el paso 2.5 — un path por línea, con qué cubre cada uno. Si no
existe nada de eso todavía en el proyecto, escribilo explícitamente ("este
proyecto no tiene reglas propias documentadas todavía") en vez de dejar la
sección en blanco sin explicación — así un auditor que la lea sabe que
confirmaste la ausencia, no que te olvidaste de revisar.

## 4. Confirmar al usuario

Cerrá con un resumen corto: qué quedó conectado, qué archivo de config se
creó/actualizó, y qué comando corre a continuación
(`/audit-harness:full-audit`).
