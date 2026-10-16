---
tipo: product-model
proyecto: ""
fecha_ultima_actualizacion: ""
---

# Cómo funciona este producto

Esta nota NO viaja a otro proyecto — se reconstruye desde cero en cada
instalación nueva del harness. Hermes y los auditores la leen antes de auditar
para entender el dominio, no solo el código.

## Qué hace el producto
<una descripción breve, orientada a qué datos procesa y para quién>

## Arquitectura real (no la ideal)
<componentes principales y cómo se conectan — puede diferir de lo documentado en otro lado>

## Entidades sensibles
<qué datos son sensibles en este producto puntual — biométricos, financieros, de menores, etc. — y por qué>

## Multi-tenancy / aislamiento
<cómo se separan los datos entre clientes/organizaciones, si aplica>

## Puntos de entrada externos
<APIs públicas, webhooks, integraciones de terceros>

## Reglas y memoria propias (fuente primaria para auditores)
<qué documentación propia ya existe en este proyecto sobre sus bugs/decisiones/
convenciones -- ej. CLAUDE.md, .claude/rules/*.md, ADRs, un vault de
aprendizajes propio (Obsidian u otro). Un path por línea, con qué cubre.
Todo auditor de dominio lee esta sección antes de aplicar sus checks
genéricos -- si hay una regla propia para su vertical, esa es la fuente
primaria, no el fallback genérico. Si el proyecto no documentó nada todavía,
decilo explícitamente en vez de dejar la sección vacía sin explicación.>
