# audit-harness (plugin)

Quick-start e instalación: ver el `README.md` de la raíz del repo, o correr
`/audit-harness:tutorial` una vez instalado. Este documento es el detalle
interno — árbol de jerarquía, inventario de componentes, y decisiones
tomadas durante la construcción.

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
│   ├── overengineering-auditor    (único que mide "sacar", no "agregar")
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
  de su rama (existen porque 19 auditores posibles cruza el umbral que
  justifica no coordinarlos uno por uno desde Hermes).
- `agents/report-assembler.md` — lee solo el vault, corre correlación
  cruzada entre verticales, escribe el reporte final.
- `agents/*-auditor.md` — 6 auditores núcleo + 13 verticales (12 activas por
  default + `privacy-minors-auditor`, dormante hasta que se confirme que
  aplica). El sexto núcleo, `overengineering-auditor`, es el único que mide
  en la dirección de "sacar" en vez de "agregar" — ver la decisión de Fase 6
  abajo.
- `skills/audit-setup/` — wizard de conexión de servicios + bootstrap. Desde
  la Fase 5, también aprende la memoria propia del proyecto (`CLAUDE.md`,
  `.claude/rules/*.md`, vault de aprendizajes propio si existe) y la escribe
  en `product-model.md` para que el resto de auditores no corra genérico.
- `skills/full-audit/` — entrada para una auditoría a demanda, completa por
  default o acotada por argumento a un lead/vertical puntual
  (`/audit-harness:full-audit security`).
- `skills/remediate/` — corrige de verdad los hallazgos de un `full-audit` ya
  corrido: triage por riesgo, GitFlow issue→develop→main, paralelización
  segura con worktrees, una re-auditoría dirigida al final, y el cierre del
  loop de memoria (promueve al vault portable y, si el proyecto declara su
  propia disciplina de aprendizajes, también escribe ahí). Separado de
  `full-audit` porque descubrir y remediar tienen gates de riesgo distintos
  (remediate toca código real).
- `skills/feature-flow/` — encadena las skills de buenas prácticas del
  proyecto (grill-with-docs → to-prd → to-issues → triage → tdd) con gates
  de confirmación entre paso y paso.
- `skills/pre-push-gate/` — revisión de 3 capas del diff antes de un push.
  Invocación manual a propósito (`/audit-harness:pre-push-gate`) — no hay
  hook de git que lo dispare solo (ver decisión abajo).
- `skills/tutorial/` — lista las 5 fases, cómo acotar alcance, y dónde vive
  el vault. Punto de entrada para quien recién instaló o no recuerda un
  comando.
- `hooks/` — `SessionStart` que avisa (mensaje completo si el proyecto no
  tiene `audit.config.yaml` todavía, mención liviana si ya lo tiene) que
  existe `/audit-harness:tutorial`.
- `bin/audit_vault.py` — CLI del fact store (sin dependencias externas, solo
  stdlib: `sqlite3`, `argparse`, `datetime`). Estrictamente SQLite — las notas
  Markdown del vault (`best-practice.md`, `playbook.md`, `product-model.md`)
  las escriben los agentes directamente con el tool `Write`, no este CLI.
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

**Fase 5 — el vault nunca se estaba usando como cerebro, solo como log.** Una
revisión sobre Quantum Leap Fútbol (el proyecto con la corrida real más
larga: 62 hallazgos, 21 fixes mergeados) encontró que `best-practice.md` y
`playbook.md` seguían siendo exactamente la plantilla vacía, y que ningún
auditor tenía la instrucción de leer `product-model.md` — la única nota con
contenido real y específico del proyecto. `bin/audit_vault.py` es
estrictamente SQLite a propósito (no reemplaza al vault Markdown, lo
complementa); el gap estaba en que nada del lado de los agentes cerraba ese
loop. Fix: `report-assembler` y `remediate` ahora promueven patrones
generalizables al vault portable (con dedup por título antes de escribir), y
los 18 auditores de dominio leen `product-model.md` como fuente primaria
antes de sus checks genéricos — no solo `data-integrity-auditor`, que era el
único que ya lo hacía.
- **Vaults separados, write-back en ambos sentidos — no uno sustituye al
  otro.** El vault portable del harness (lo generalizable, que viaja a otro
  proyecto en la próxima instalación) y el vault propio de aprendizajes del
  proyecto auditado (ej. un vault de Obsidian declarado en su `CLAUDE.md`,
  con su propia disciplina de `tipo`/wikilinks) cumplen roles distintos.
  `remediate` escribe en los dos cuando un fix real lo justifica, siguiendo
  siempre la disciplina que el proyecto auditado ya declaró — nunca
  inventando una propia encima.
- **`full-audit` acepta alcance por argumento, no solo por prosa libre** —
  `/audit-harness:full-audit security` despacha solo ese lead/vertical. La
  prosa libre ("auditá solo RLS") sigue funcionando igual; el argumento es
  un atajo, no un reemplazo.
- **Descubrir los flujos no puede depender de que alguien se acuerde de leer
  el README.** Un hook de `SessionStart` (stdlib-only, mismo criterio que
  `audit_vault.py`) avisa del nuevo skill `/audit-harness:tutorial` — mensaje
  completo si el proyecto no tiene `audit.config.yaml` todavía, mención
  liviana si ya está conectado (para no repetir el mensaje completo cada
  sesión en proyectos ya configurados).

**Fase 6 — `overengineering-auditor`, el único que mide en la dirección
contraria.** Los otros 18 auditores buscan qué falta (un check, un backup, un
test, un rate limit). Sobre-ingeniería es el patrón opuesto — código,
abstracciones o configuración que ya sobran — y ningún auditor existente lo
cubría: `build-optimizer` mide bundle/deps, no diseño; la skill nativa
`/improve-codebase-architecture` busca huecos de estructura, dirección
opuesta a "sacar". Se agregó como sexto auditor núcleo (siempre dispatcheado
por `lead-code-quality`, igual que `data-integrity`/`build`, sin necesidad de
habilitarlo en `verticals_enabled`) y es invocable solo con
`/audit-harness:full-audit overengineering`. El agente deja explícito en su
propio texto cómo no duplicar `/improve-codebase-architecture`, `/simplify` ni
`build-optimizer` — tres mecanismos parecidos que miden cosas distintas.

**La primera versión de este auditor se reescribió para no ser ella misma
sobre-ingeniería** (6 categorías por intuición, sin ningún anclaje). La
versión final está parada en literatura real, no en vibes: el filtro
explícito es Fred Brooks (*No Silver Bullet*, 1986) — complejidad esencial
(del problema) vs. accidental (del código) — y cada categoría tiene un
nombre citable y una forma mecánica de verificarla: "speculative generality"
de Fowler/YAGNI, la Regla de Tres (Sandi Metz: "preferí duplicar a abstraer
mal"), y módulos *shallow*/*pass-through* de Ousterhout (*A Philosophy of
Software Design*). El código muerto dejó de grepearse a mano — se delega a
la herramienta correcta por stack (`knip` en JS/TS, que para 2026 ya
reemplazó a `ts-prune`/`depcheck`; `vulture` en Python, con su propio
scoring de confianza; `staticcheck`/`deadcode` en Go) en vez de reinventar
la detección con grep, que es precisamente el tipo de esfuerzo redundante
que este auditor existe para señalar en el código de otros. Se sacó también
la categoría de "testing con mocks excesivos" del borrador original — no
tenía un ancla establecida propia y se superponía con
`testing-coverage-auditor`.

Cada agente referencia `<plugin-root>/bin/audit_vault.py` — cuando el plugin
está instalado vía marketplace, ese path es el del plugin instalado en
`~/.claude/plugins/`; cuando se corre con `--plugin-dir` para desarrollo, es
la ruta local que le pasaste al flag.
