---
name: feature-flow
description: Encadena el flujo de buenas prácticas para una feature nueva — afilar el diseño, convertir a PRD, cortar en issues, triage, implementar con TDD — con un gate de confirmación entre cada paso. Usa las skills del proyecto si existen; si alguna falta, avisa y sigue con una versión mínima en vez de fallar entero.
disable-model-invocation: true
---

Corré esto como `/audit-harness:feature-flow` cuando el usuario arranca una
feature nueva y quiere pasar por el flujo completo de buenas prácticas, no
tirarse directo a programar.

## Antes de arrancar

Revisá qué skills de este flujo existen en el proyecto actual — buscá en
`.claude/skills/` del repo, o entre los plugins instalados. El flujo estándar,
con el nombre más común de cada skill entre paréntesis:

1. **Afilar el diseño** (`grill-with-docs`, o `grill-me` si no es una tarea
   técnica)
2. **Convertir a PRD** (`to-prd` o `write-a-prd`)
3. **Cortar en issues** (`to-issues` o `prd-to-issues`)
4. **Triage** (`triage`)
5. **Implementar** (`tdd`, red-green-refactor), un issue a la vez

Si alguna de estas skills no existe en el proyecto, **no falles el flujo
entero por eso**: avisá que ese paso no tiene skill dedicada acá, y hacé una
versión mínima vos mismo (ej. sin `to-prd`, escribís un PRD corto a mano antes
de seguir), o preguntale al usuario si prefiere saltar el paso.

## Gates entre pasos — no son opcionales

No avances al paso siguiente sin que el anterior esté confirmado por el
usuario:

- No cortes issues sin que el PRD esté confirmado.
- No empieces a implementar con TDD sin que los issues estén confirmados
  (y pasados por triage, si esa skill existe en el proyecto).

El punto del flujo es que cada etapa sea una revisión real del usuario, no un
trámite automático — si vos mismo completás todos los pasos sin parar a
confirmar, el flujo no cumplió su función.

## Dónde termina

Este flujo termina en el merge de cada issue implementado. La revisión
automática del diff antes de subirlo es responsabilidad de `pre-push-gate`
(si está instalado en el repo), no de este flujo — no dupliques esa revisión
acá.
