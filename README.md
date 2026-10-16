# audit-harness

## Uso rápido

**1. Instalar** (una vez por máquina):

```bash
claude plugin marketplace add /ruta/a/audit-harness
claude plugin install audit-harness@audit-harness-marketplace
```

Queda disponible en *cualquier* proyecto de esa máquina, sin pasos extra.

**2. Conectar el proyecto** (una vez por repo, dentro de una sesión de Claude
Code, parado en la raíz del repo que querés auditar):

```
/audit-harness:audit-setup
```

**3. Auditar** (cuando quieras, las veces que quieras):

```
/audit-harness:full-audit
```

Te devuelve un Artifact con todos los hallazgos, rankeados por severidad.

**4. Corregir de verdad** (opcional, cuando quieras implementar los fixes en
vez de solo leer el reporte):

```
/audit-harness:remediate
```

Triage por riesgo, GitFlow issue→develop→main, y una re-auditoría dirigida al
final antes de tocar `main`.

**Otros dos comandos del día a día:**

```
/audit-harness:feature-flow      # antes de arrancar una feature nueva
/audit-harness:pre-push-gate     # a mano, antes de cada git push
```

Eso es todo lo que hace falta saber para usarlo. El resto de este documento
es cómo está armado por dentro.

---

## Qué es

Hermes orquesta una jerarquía de auditores — seguridad, pentest, integridad
de datos, arquitectura, build, infra, y 13 verticales de producto/legal/ops —
sobre cualquier proyecto. Fact store propio (SQLite+FTS5) para no repetir
hallazgos entre corridas, y un vault de conocimiento (playbooks +
best-practices) que viaja de proyecto en proyecto.

Diseño completo (arquitectura, decisiones y roadmap) en el Artifact de mapa
del harness — no se repite acá, ese documento es la fuente de verdad del
diseño original.

## Desarrollo / testing sin instalar

```bash
claude --plugin-dir /ruta/a/audit-harness/plugins/audit-harness
```

## Estado

Fase 1 a 4 del roadmap original, completas: Hermes + jerarquía de 2 niveles
(3 leads) + 5 auditores núcleo + 13 verticales (12 activas + `privacy-minors`
dormante) + report-assembler + fact store + 5 skills (el quinto, `remediate`,
agregado después de validar el flujo completo de descubrimiento→fix→merge en
una corrida real de punta a punta sobre un proyecto real). Validado con
`claude plugin validate --strict` e instalado de punta a punta — 23 agentes,
5 skills.

Ver `plugins/audit-harness/README.md` para el árbol de jerarquía completo,
el inventario de componentes, y las decisiones tomadas durante la
construcción.
