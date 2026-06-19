---
name: enetec-workspace-activo
description: proyecto activo = ENETEC/ODIN 2.0; ubicación local del repo y datos clave del stack
metadata: 
  node_type: memory
  type: project
  originSessionId: 3a3fa3d8-c453-4e92-bec5-f2aa61e59c10
---

Proyecto en el que se está trabajando (foco único, decidido 2026-06-15): **ENETEC / ODIN 2.0** (Odoo 17 + Docker), repo `ntdiaz87-sudo/odoo-enetradex`.

- **Ubicación local del repo:** `C:\Proyectos\odoo-enetradex` (NO `C:\odoo_enetradex` que es la ruta antigua que aún figura en su `CLAUDE.md`; el `docker-compose.yml` usa rutas relativas, así que funciona desde aquí).
- **Memoria del proyecto:** junction creado con projKey `C--Proyectos-odoo-enetradex` → `...\odoo-enetradex\.claude-memory` (11 notas propias del proyecto).
- **Stack:** contenedores `enetradex_odoo` + `enetradex_postgres`; UI en http://localhost:8469 (longpolling 8472); BD `enetradex_dev` (creada limpia + datos demo el 2026-06-15, con los 15 módulos custom instalados).
- Para tareas dentro del repo aplican sus propias reglas de autonomía (ver su `CLAUDE.md`): docker exec/compose/cp/logs preaprobados; preguntar antes de tocar compose/Dockerfile/odoo.conf, otros contenedores, o restore de BD.

**Why:** el usuario clonó este repo localmente y decidió trabajar solo en él; la ruta real difiere de la documentada.
**How to apply:** asumir ENETEC como proyecto por defecto; operar contra `C:\Proyectos\odoo-enetradex` y el stack `enetradex_*`. Relacionado: [[git-workflow]], [[verify-web-designs]], [[dev-machine-no-nvidia]].
