---
name: remediate
description: Corrige de verdad los hallazgos de un full-audit ya corrido (no solo los documenta) -- triage por riesgo, GitFlow issue→develop→main, paralelización segura con worktrees, una re-auditoría dirigida al final, y el cierre del loop de memoria (vault portable + vault propio del proyecto si declara uno). Usar después de full-audit, cuando el usuario quiere implementar los fixes, no solo leer el reporte.
disable-model-invocation: true
---

Corré esto como `/audit-harness:remediate` después de `/audit-harness:full-audit`.
Este skill no descubre hallazgos nuevos -- parte de `facts.db` con status `open` y
los cierra con código real, commits y merges reales. Todo lo de abajo viene de
una corrida real end-to-end (62 hallazgos, 21 fixes de código, 1 cuasi-incidente
de pérdida de datos) -- no es teoría previa a probarse.

## 0. Triage por riesgo, antes de tocar código

Pedile al usuario que etiquete (o etiquetá vos con su ok) cada hallazgo `open`
en una de tres categorías -- la categoría decide el tratamiento, no la
severidad:

- **riesgo cero**: el fix no puede romper nada observable (agregar un header,
  loguear una excepción que antes se tragaba, pinear una versión, agregar un
  test). **Auto-merge si los tests pasan**, sin pedir aprobación por ítem.
- **riesgo bajo-medio**: toca lógica real pero el blast radius es acotado y
  entendible (rate limiting, CORS, code-splitting, Dockerfile). Implementar y
  armar el PR, pero **no auto-mergear** -- queda para la revisión por lotes del
  paso 4.
- **riesgo alto / necesita plan**: seguridad explotable, integridad de datos,
  cualquier cosa donde adivinar el fix "a tu gusto" sin preguntar sería
  irresponsable (ej. un account-takeover real). **Grill-me uno por uno, en
  vivo, en el chat** -- explicar qué se va a editar y por qué antes de
  tocarlo, nunca adivinar.

Separado de estas tres: cualquier hallazgo que requiera credenciales, acceso a
un servicio externo, o una decisión de negocio/legal que el agente no puede
tomar (renovar una API key, provisionar un bucket real, upgradear un plan
pago, una decisión de licenciamiento) se **documenta como pendiente** -- nunca
se inventa ni se auto-resuelve. Etiquetalo `needs-your-action` y seguí de
largo.

## 1. GitFlow: una rama por issue, todas confluyen en `develop`

```
issue/hallazgo → rama fix/issue-N-slug → PR a develop → (todas mergeadas) → PR develop→main
```

`main` nunca recibe un fix individual directo. `develop` es donde se acumulan
todos los fixes de esta corrida antes de la re-auditoría del paso 4.

## 2. Paralelizar fixes: aislamiento de worktree es OBLIGATORIO, no opcional

Si vas a despachar más de un fix en paralelo (vía `Agent`/forks), **cada uno
tiene que trabajar en su propio `git worktree`**, nunca en el directorio
compartido del repo:

```bash
git worktree add /tmp/fix-issue-N -b fix/issue-N-slug origin/develop
```

Esto no es una preferencia de estilo -- en la corrida real que originó este
skill, dos forks sin worktree corriendo sobre el mismo directorio causaron que
uno pisara el `checkout` del otro y que un `git clean` de un tercero borrara
trabajo sin commitear de los demás (recuperable solo porque estaba en el
contexto de conversación, no en git). Nunca asumas que "van a terminar rápido,
no van a chocar" -- van a chocar.

**Dentro de un worktree, nunca corras `git stash` / `git stash pop` a secas.**
Todos los worktrees de un mismo repo comparten una sola lista de stash. Un
`git stash pop` sin verificar primero `git stash list` puede traer de vuelta
el stash de **otra sesión/worktree**, no el tuyo -- y si el pop falla a mitad
de camino, deja archivos de otra sesión mezclados con los tuyos (no se pierde
nada -- el stash original queda intacto -- pero genera un falso positivo de
"borré algo" que cuesta mucho diagnosticar). Si necesitás guardar trabajo
a medio hacer, commiteá a la rama del worktree en vez de stashear.

## 3. Conflictos de merge esperables al converger a `develop`

Dos patrones de conflicto van a aparecer casi seguro si varios fixes tocan
infraestructura compartida (Dockerfiles, lockfiles):

- **Lockfile (`uv.lock`, `package-lock.json`, etc.) marcado como conflicto**:
  nunca lo resuelvas a mano editando el TOML/JSON generado. Quedate con
  cualquiera de las dos versiones (`git checkout --theirs <lockfile>`) y
  regenéralo de cero (`uv lock`, `npm install`) a partir del `pyproject.toml`/
  `package.json` ya mergeado -- ese sí se mergea bien con git porque es texto
  con estructura real.
- **Conflicto add/add en un archivo nuevo** (dos ramas crean el mismo archivo
  nuevo de forma independiente, ej. dos fixes de Docker que ambos agregan
  `Dockerfile.worker`): normalmente una versión es un superset literal de la
  otra (una rama agrega líneas encima de lo que la otra ya tenía). Diffeá
  ambas versiones contra el archivo conflictuado antes de resolver -- si una
  contiene a la otra, quedate con la más completa entera, no mezcles a mano.

Si sabés de antemano que dos issues van a tocar el mismo archivo nuevo (ej.
"dividir Dockerfile" y "correr como non-root" van a tocar el mismo
Dockerfile.worker), mergeá primero la que *crea* el archivo y dejá que la que
lo *modifica* se rebase después -- ahorra el conflicto en vez de limpiarlo.

## 4. Gate de merge: tests locales, no el estado de CI

Usá la suite de tests local (`pytest`, `vitest`, build) como gate antes de
cada merge a `develop` -- no esperes a GitHub Actions. Si CI está rota por una
razón ya conocida e independiente (ej. un fix para esa rotura todavía no
mergeado), esperar a CI bloquea sin aportar señal real.

**Falso positivo conocido:** una suite de tests de integración RLS contra
Supabase real puede fallar en bloque por rate-limit del propio Supabase Auth
si corre junto con el resto de la suite (demasiados logins en poco tiempo), no
por una regresión real. Si *todos* los fallos caen en una sola suite de
integración y ninguno en el resto, re-correla sola/aislada antes de tratarla
como regresión.

## 5. Después de mergear todo a `develop`: re-auditoría dirigida, no necesariamente full-audit

Volver a correr la jerarquía completa de Hermes (3 leads + hasta 18
auditores) desde cero es la opción más exhaustiva pero también la más cara --
en la corrida real que originó este skill, una sola pasada completa ya había
chocado varias veces contra el límite de sesión de la cuenta. Para confirmar
que los fixes de *esta* tanda cerraron de verdad, alcanza con una pasada más
barata:

1. Para cada hallazgo con fix de código (no los `needs-your-action`), confirmá
   que el test de regresión que el propio fix agregó pasa, y si el hallazgo
   era explotable de verdad (ej. SSRF, account-takeover), re-corré el
   repro/exploit contra el código corregido para confirmar que ya no abre.
2. Gregeá los archivos tocados por *todos* los PRs de esta tanda contra las
   reglas de integridad de datos del proyecto (si existen, ej.
   `.claude/rules/backend-data-integrity.md`) -- un fix apurado puede
   introducir la misma clase de bug que arregló en otro lado.
3. Marcá cada hallazgo cerrado en `facts.db`:
   ```
   audit_vault.py resolve <id> --db <vault_path>/facts.db --by "<sha-corto> (#PR)"
   ```
4. Si esto encuentra algo roto, arreglalo y repetí -- recién ahí el full-audit
   completo desde cero se justifica (algo más allá de esta tanda cambió, o el
   usuario pide específicamente la cobertura completa).

## 6. `develop` → `main`

Solo después de que el paso 5 no encuentre nada pendiente. Esto dispara
deploys reales si el proyecto tiene CD conectado a `main` -- confirmá
explícitamente con el usuario antes de este merge puntual, incluso si todo lo
anterior corrió sin pedir confirmación paso a paso (es la acción de más blast
radius de todo el flujo).

**Gotcha de GitHub:** las keywords `Closes #N` / `Fixes #N` en el cuerpo de un
PR solo auto-cierran el issue cuando ese PR se mergea a la **default branch**
del repo (normalmente `main`), no cuando se mergea a `develop`. No te
sorprendas si los issues siguen "open" después de mergear todo a `develop` --
van a cerrarse solos en cuanto `develop` llegue a `main`. No hace falta
cerrarlos a mano en el paso 4.

## 7. Cerrar el loop de memoria

Esto es lo que diferencia "arreglé el bug" de "el harness aprendió del bug".
Para cada hallazgo que cerraste con código real en esta tanda (no los
`needs-your-action`):

1. **Promové la versión generalizable al vault portable del harness** --
   mismo mecanismo que el paso 6 de `agents/report-assembler.md`: grepeá los
   títulos ya existentes en `<vault_path>/best-practice.md` y
   `<vault_path>/playbook.md`, y agregá o actualizá una entrada siguiendo
   `templates/vault/best-practice.template.md` / `playbook.template.md`. Un
   fix real que cerró un hallazgo es la mejor fuente posible para esto -- no
   lo dejes solo en el commit.

2. **Si el proyecto que estás remediando declaró su propia disciplina de
   documentación de aprendizajes** (típicamente en su `CLAUDE.md` -- ej. un
   vault de Obsidian con `tipo: incidente/decision/gotcha/...` y reglas de
   wikilink propias), escribí o actualizá ahí una nota siguiendo ESA
   disciplina exacta para cualquier hallazgo que haya sido un incidente real
   con causa raíz identificada (especialmente si es un *bug class* que puede
   repetirse en otro módulo) o una decisión de arquitectura tomada durante el
   remediate. Nunca inventes una convención propia encima de la que el
   proyecto ya tiene -- leé su propio índice/nota-guía primero y segui ese
   formato. Si el proyecto no declaró ninguna disciplina así, omití este paso
   sin marcarlo como pendiente ni inventar una.

3. Estos dos destinos cumplen roles distintos y no son intercambiables: el
   vault portable (paso 1) es lo que viaja a OTROS proyectos la próxima vez
   que se instale el harness; la nota en el proyecto auditado (paso 2) es la
   memoria de ESE proyecto puntual, con su propio nivel de detalle y sus
   propios nombres reales (archivos, commits, clientes). Un hallazgo
   importante casi siempre justifica escribir en los dos lados, no en uno
   solo.
