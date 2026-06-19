---
name: verify-web-designs
description: Siempre verificar visualmente los diseños web y correr los flujos con las herramientas antes de pasar al usuario
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0852c323-f81a-4b41-90ea-80b200e8aa52
---

Para cualquier trabajo de **interfaz web** (portal Odoo, maquetas, cambios de diseño): SIEMPRE
verificar visualmente cómo queda usando las herramientas disponibles (navegador Chrome MCP
`mcp__Claude_in_Chrome__*`, o computer-use para screenshot) y **correr el flujo end-to-end**
(login, navegar, subir, ver estado). Asegurarme YO primero de que se ve y funciona bien, y
SOLO DESPUÉS pasárselo al usuario para su revisión.

**Why:** El usuario no quiere recibir cosas sin comprobar; quiere que yo valide visualmente
y funcionalmente antes de su revisión final.

**How to apply:** Tras cualquier cambio de UI: renderizar la página real (no solo verificar
que el HTML devuelve 200), tomar screenshot, revisar que coincide con el diseño y que el flujo
corre. Reportar con evidencia (lo que vi). App local: Odoo en http://localhost:8069 (cliente
demo `cliente@demo.cu`/`cliente123`). Relacionado con [[working-style-autonomy]] y [[docvalidator-project]].
