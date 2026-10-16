---
tipo: best-practice
vertical: security
stack: [sqlite-fts5]
fecha: 2026-10-16
fuente: "audit-harness fact #1 (security) + #10 (testing-coverage), auditoría audit-harness 2026-10-16"
---

# Nunca pasar input de usuario/agente crudo a un motor de búsqueda de terceros (FTS5, Elasticsearch, etc.) sin capturar sus propios errores de sintaxis

## Por qué
Un motor de full-text search expone su propia gramática (operadores `AND/OR/NOT`, comillas, filtros de columna `col:term`, `*`, `-`), distinta a la del lenguaje de la app. Cuando se expone con un bind directo (`WHERE fts MATCH ?`) a una query que viene de un humano o -- peor -- de un agente LLM que compone el string a partir de contenido de terceros, cualquier carácter especial de esa gramática revienta como excepción nativa del motor, no como un error de validación controlado. Se reprodujo en vivo en audit-harness: queries tan comunes como `'foo AND'`, `'(foo'` o incluso `'check-in'` (el guión se interpreta como operador) rompen el comando sin ningún manejo de errores, justo en el flujo que el propio sistema usa como anti-duplicados antes de escribir un hallazgo nuevo.

## Cómo se detecta una violación
Grep por `MATCH ?` (o el equivalente del motor) y verificar que la llamada esté envuelta en un `try/except` que capture la excepción nativa del motor (`sqlite3.OperationalError` para FTS5, excepciones de parseo de Elasticsearch/Lucene, etc.) y devuelva un error de validación legible en vez de un traceback crudo. Repro rápida: correr la query con un operador booleano al final, una comilla sin cerrar, o un guión suelto, y confirmar si el comando crashea sin manejo.

## Excepciones válidas
Herramientas de uso estrictamente interno/CLI de un solo desarrollador, donde un traceback en stdout es un costo aceptable y no rompe un flujo automatizado de otro proceso -- aun así, conviene documentar el bug conocido en vez de dejarlo implícito.

---
tipo: best-practice
vertical: infra
stack: [python, json-stdin-hooks]
fecha: 2026-10-16
fuente: "audit-harness fact #2 (infra) + #11 (testing-coverage), auditoría audit-harness 2026-10-16"
---

# Validar que un JSON externo decodificado sea del tipo esperado (dict) antes de llamar `.get()` sobre él

## Por qué
`json.loads`/`json.load` acepta cualquier valor JSON válido -- un objeto, pero también una lista, un string, un número o `null`. Capturar solo `JSONDecodeError`/`ValueError` protege contra JSON *inválido*, no contra JSON *válido pero con la forma equivocada*. Si el código asume `dict` y llama `.get(...)` sin chequear el tipo, un JSON válido no-objeto produce un `AttributeError` no capturado. Se reprodujo en vivo en `hooks/session-start.py` de audit-harness: `echo '[1,2,3]' | python3 hooks/session-start.py` → `AttributeError: 'list' object has no attribute 'get'`, crasheando un hook que corre en cada arranque de sesión.

## Cómo se detecta una violación
Grep por `json.loads(`/`json.load(` seguido de `.get(` sobre el resultado, sin un `isinstance(data, dict)` (o equivalente) entre ambas líneas. Repro: alimentar el parser con una lista, un string y un número JSON válidos y confirmar si crashea con `AttributeError`/`TypeError` en vez de fallar con un mensaje controlado.

## Excepciones válidas
Cuando el JSON viene de un contrato interno fuertemente tipado y versionado (ej. validado por un framework antes de llegar a este código), la validación de forma puede vivir en esa capa anterior -- pero debe existir en ALGÚN punto del pipeline, no asumirse.

---
tipo: best-practice
vertical: build
stack: [multi-agent-prompts, markdown-agent-definitions]
fecha: 2026-10-16
fuente: "audit-harness fact #5 (build) + #6 (architecture), auditoría audit-harness 2026-10-16"
---

# No copy-pastear el mismo bloque de instrucciones/contrato en más de un archivo de definición de agente -- factorizar a una fuente única referenciada

## Por qué
En una arquitectura de múltiples agentes/prompts de sistema definidos como archivos Markdown separados, es tentador copiar el mismo bloque (preámbulo de contexto, contrato de invocación de una herramienta, ejemplo de uso) en cada archivo nuevo porque cada uno se edita de forma aislada. El costo aparece cuando ese bloque necesita cambiar: hay que editar N archivos a mano, y si se editan de a uno con el tiempo empieza el drift silencioso -- en audit-harness, dos de los 18 archivos que comparten el preámbulo de "memoria del proyecto" ya divergieron en la redacción inicial sin que nada lo marcara. Si el contrato real de una herramienta cambia (ej. un flag que pasa de opcional a requerido), los archivos no actualizados quedan documentando un contrato que ya no existe.

## Cómo se detecta una violación
Buscar el mismo bloque de texto (o uno casi idéntico, con 1-2 sustantivos cambiados) repetido en 3 o más archivos de definición de agente/prompt. Un `grep` del primer renglón único del bloque que devuelva más de 2-3 coincidencias en archivos distintos es la señal. Confirmar además si ya hay drift real comparando el bloque completo entre archivos (no solo el título) -- si dos copias ya no son idénticas, el problema ya está activo, no es solo un riesgo futuro.

## Excepciones válidas
Bloques de 1-2 líneas sin lógica real (ej. un footer de licencia) donde el costo de factorizar supera el costo de mantener la duplicación. El umbral de audit-harness fue ~8 líneas repetidas en 18 archivos (~145 líneas totales) -- bloques de ese tamaño o mayor, repetidos en 3+ archivos, casi siempre valen la factorización.

---
tipo: best-practice
vertical: data-integrity
stack: [sqlite, cli-tools]
fecha: 2026-10-16
fuente: "audit-harness fact #7 (data-integrity), auditoría audit-harness 2026-10-16"
---

# Un "anti-duplicado por convención del llamador" sin UNIQUE/upsert en el schema no es un anti-duplicado real

## Por qué
Documentar que "hay que correr `search` antes de `add`" como mecanismo anti-duplicados depende 100% de que todo caller (humano o agente) respete esa convención siempre, incluso bajo concurrencia o cuando el paso previo falla. En audit-harness, el propio `search` puede crashear ante sintaxis FTS5 inválida (ver nota de best-practice sobre FTS5 en este mismo archivo) -- si eso pasa, el caller que debía deduplicar antes de escribir queda sin ninguna señal, y nada en el schema lo frena: `INSERT` puro sin `UNIQUE` sobre `(project, vertical, statement, evidence)` ni `ON CONFLICT` permite escribir el mismo hallazgo dos veces sin error ni aviso, verificado en repro directo.

## Cómo se detecta una violación
Revisar el `CREATE TABLE` de cualquier tabla cuyo docstring/comentario prometa "no duplicados" o "dedupe": si no tiene una constraint `UNIQUE` (compuesta si hace falta) y el `INSERT` correspondiente no usa `INSERT OR IGNORE`/`ON CONFLICT DO NOTHING`/upsert equivalente, la promesa de no-duplicados es solo documentación, no un contrato del schema. Repro: ejecutar la misma operación de escritura dos veces con los mismos argumentos y confirmar si quedan dos filas idénticas salvo el id.

## Excepciones válidas
Casos donde duplicados exactos son intencionales y esperables (ej. un log de eventos donde el mismo evento puede ocurrir dos veces legítimamente) -- ahí no aplica esta regla porque no hay promesa de unicidad que proteger.
