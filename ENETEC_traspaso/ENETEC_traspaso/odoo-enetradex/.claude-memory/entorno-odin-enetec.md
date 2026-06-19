---
name: entorno-odin-enetec
description: Acceso al entorno ODIN de ENETEC ya desplegado por pyxel (URL y credenciales de prueba)
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4c1918a5-33b6-4251-837d-dc0bfe097d44
---

Entorno ODIN de ENETEC ya desplegado por pyxel (instancia de referencia para el clon [[proyecto-enetec-odin]]).

- **URL:** https://enete.pyxelsolution.com/
- **Admin:** usuario `erp_odin` / pass `erp_odin`
- **Usuarios de prueba para correr flujos:**
  - Proveedor SIN acreditar: `proveedornoacreditado` / `proveedornoacreditado`
  - Cliente SIN acreditar: `usuarionoacreditado` / `usuarionoacreditado`
  - Cliente acreditado: `nuevocliente@test.test` / `nuevocliente`

**Decisión (2026-06-13):** esta instancia es **SOLO para inspeccionar** el estado actual; el clon local se sigue construyendo desde el código base de Agrimpex. Puede contener customizaciones de ENETEC más avanzadas que Agrimpex — sirve para comparar qué ya está implementado. Para inspeccionarla se necesita login (WebFetch no autentica; usar navegador/Chrome MCP).

**Decisión pendiente:** comportamiento de las listas de documentos de acreditación (bloqueante vs checklist guía) → lo define ENETEC, no decidir aún. Ver [[requisitos-enetec-cliente]].
