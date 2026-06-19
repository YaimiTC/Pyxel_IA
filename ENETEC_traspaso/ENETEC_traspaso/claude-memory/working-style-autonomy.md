---
name: working-style-autonomy
description: "El usuario quiere que opere con máxima autonomía, sin pedir permisos para operaciones técnicas"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0852c323-f81a-4b41-90ea-80b200e8aa52
---

El usuario pidió (2026-06-14) operar con **total libertad**: NO pedirle permisos ni confirmaciones para operaciones técnicas (Bash/PowerShell, instalar paquetes con pip/winget, Docker, crear/editar archivos, etc.). Solo consultarle en **decisiones de flujo muy específicas** (qué construir, qué enfoque de producto, prioridades), no en la ejecución.

**Why:** Quiere avanzar rápido sin interrupciones; confía en que ejecute y reporte resultados.

**How to apply:** Actúa y reporta en vez de preguntar. Reserva AskUserQuestion para bifurcaciones de producto/diseño genuinas. Se configuró `C:\Proyectos\.claude\settings.local.json` con `defaultMode: acceptEdits` y allow amplio (Bash, PowerShell, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch, Skill). Aun así, seguir confirmando acciones realmente destructivas o irreversibles antes de ejecutarlas.

Relacionado con [[docvalidator-project]].
