# audit-harness (plugin)

## Jerarquía (Hermes → 3 leads → auditores)

```
hermes
├── lead-security-legal
│   ├── security-auditor
│   ├── offensive-auditor          (pentest activo, local/staging)
│   ├── multi-tenant-auditor
│   ├── llm-security-auditor
│   └── privacy-minors-auditor     (DORMANTE por default)
├── lead-code-quality
│   ├── data-integrity-auditor
│   ├── build-optimizer
│   ├── testing-coverage-auditor
│   └── cv-drift-auditor
└── lead-infra-ops-producto
    ├── infra-auditor
    ├── docker-security-auditor
    ├── cicd-auditor
    ├── finops-auditor
    ├── backup-dr-auditor
    ├── incident-response-auditor
    ├── accessibility-auditor
    ├── feature-flags-auditor
    └── sbom-auditor
```

`report-assembler` corre aparte, disparado por Hermes al terminar — lee
`facts.db` + el vault Markdown, nunca las transcripciones de los auditores.

## Componentes

- `agents/hermes.md` — orquestador. Despacha a los 3 leads, consulta
  `facts.db` antes de arrancar, nunca agrega hallazgos crudos.
- `agents/lead-*.md` — 3 leads temáticos. Cada uno maneja el fan-out interno
  de su rama (existen porque 18 auditores posibles cruza el umbral que
  justifica no coordinarlos uno por uno desde Hermes).
- `agents/report-assembler.md` — lee solo el vault, corre correlación
  cruzada entre verticales, escribe el reporte final.
- `agents/*-auditor.md` — 5 auditores núcleo + 13 verticales (12 activas por
  default + `privacy-minors-auditor`, dormante hasta que se confirme que
  aplica).
- `skills/audit-setup/` — wizard de conexión de servicios + bootstrap.
- `skills/full-audit/` — entrada para una auditoría completa a demanda.
- `skills/remediate/` — corrige de verdad los hallazgos de un `full-audit` ya
  corrido: triage por riesgo, GitFlow issue→develop→main, paralelización
  segura con worktrees, y una re-auditoría dirigida al final. Separado de
  `full-audit` porque descubrir y remediar tienen gates de riesgo distintos
  (remediate toca código real).
- `skills/feature-flow/` — encadena las skills de buenas prácticas del
  proyecto (grill-with-docs → to-prd → to-issues → triage → tdd) con gates
  de confirmación entre paso y paso.
- `skills/pre-push-gate/` — revisión de 3 capas del diff antes de un push.
  Invocación manual a propósito (`/audit-harness:pre-push-gate`) — no hay
  hook de git que lo dispare solo (ver decisión abajo).
- `bin/audit_vault.py` — CLI del fact store (sin dependencias externas, solo
  stdlib: `sqlite3`, `argparse`, `datetime`).
- `templates/vault/` — plantillas de notas del vault de conocimiento.

## Decisiones tomadas durante la construcción

- **`pre-push-gate` es manual, no un hook automático.** Un hook de git que
  se dispara solo en cada push, headless y sin supervisión directa, quedó
  bloqueado por el clasificador de permisos de Auto Mode — correctamente: es
  el patrón de "agente con permisos elevados ejecutándose sin que nadie lo
  vea". La skill corre el mismo chequeo, pero invocada a mano dentro de una
  sesión normal.
- **`privacy-minors-auditor` existe pero está apagado por default.** Se
  construyó completo (no es un stub) pero no entra a `verticals_enabled`
  salvo que el proyecto confirme explícitamente que trackea datos de
  menores — decisión explícita tomada durante el diseño, no un olvido.
- **La jerarquía de 2 niveles se construyó ahora** porque 13 verticales + 5
  núcleo = hasta 18 auditores posibles por corrida, cruzando el umbral de
  "8+" que se había fijado como trigger para no construirla antes de tiempo.
- **`remediate` es un skill separado de `full-audit`**, agregado después de
  la primera corrida real end-to-end (62 hallazgos → 21 fixes mergeados a
  producción en Quantum Leap Fútbol). `full-audit` solo descubre y reporta;
  implementar fixes de verdad resultó tener sus propios gates (triage por
  riesgo, GitFlow, aislamiento de worktree) que no tiene sentido mezclar en
  el mismo skill que corre auditores read-only.
- **Aislamiento de `git worktree` es obligatorio al paralelizar fixes**, no
  una sugerencia de estilo. En la corrida real, dos forks sin worktree sobre
  el mismo directorio compartido causaron una colisión real: un `git clean`
  de un fork borró trabajo sin commitear de otro. Nada se perdió de forma
  irrecuperable (estaba en el contexto de conversación), pero fue puro azar,
  no diseño. Ahora es una regla explícita en `skills/remediate/SKILL.md`.
- **`git stash` es peligroso entre worktrees del mismo repo** porque
  comparten una sola lista de stash. Un fork que corrió `git stash pop` a
  secas en su propio worktree trajo de vuelta el stash de *otra* sesión —
  generó una falsa alarma de "borré el spreadsheet del usuario" que costó una
  verificación completa de filesystem+git para descartar. El stash original
  nunca se tocó (seguía intacto), pero el skill ahora prohíbe el stash
  bare y pide commitear a la rama del worktree en su lugar.
- **GitHub solo autocierra issues (`Closes #N`) al mergear a la *default
  branch*** del repo, no a cualquier rama. Con un flujo issue→develop→main,
  los issues quedan "open" después de mergear todo a `develop` y se cierran
  solos recién cuando `develop` llega a `main` — no es un bug ni hace falta
  cerrarlos a mano antes. Documentado en `skills/remediate/SKILL.md` para que
  no se interprete como que el merge a `develop` no funcionó.
- **La re-auditoría después de remediar no necesita ser un full-audit desde
  cero.** Repetir la jerarquía completa de Hermes es caro (la corrida real
  chocó varias veces contra el límite de sesión de la cuenta haciéndolo una
  sola vez); confirmar cada fix contra su test de regresión + grep de
  regresión sobre los archivos tocados es mucho más barato y cubre lo mismo
  para el caso común ("¿estos fixes puntuales cerraron de verdad?").
- **Conflictos de lockfile (`uv.lock`, `package-lock.json`) nunca se resuelven
  a mano** — se regeneran desde el manifest ya mergeado (`pyproject.toml`,
  `package.json`), que sí mergea bien porque es texto con estructura real.

Cada agente referencia `<plugin-root>/bin/audit_vault.py` — cuando el plugin
está instalado vía marketplace, ese path es el del plugin instalado en
`~/.claude/plugins/`; cuando se corre con `--plugin-dir` para desarrollo, es
la ruta local que le pasaste al flag.
