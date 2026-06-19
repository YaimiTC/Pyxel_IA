---
name: sync-git-multipc
description: Los proyectos enetradex y agrimpex se sincronizan entre PCs por GitHub privado; memoria de Claude via junction
metadata: 
  node_type: memory
  type: project
  originSessionId: 1bed270a-2ef9-45a7-aabc-ba47e5cc1391
---

El usuario trabaja desde varias PCs (casa/oficina) con internet inestable.
Montado en jun-2026:

- **Código en GitHub privado** (cuenta `ntdiaz87-sudo`):
  - https://github.com/ntdiaz87-sudo/odoo-enetradex.git  (subido OK)
  - https://github.com/ntdiaz87-sudo/odoo-agrimpex.git   (subido OK)
  - https://github.com/ntdiaz87-sudo/odoo-cupet.git      (antes "ceimpex"; carpeta renombrada a C:\odoo_cupet; falta crear repo+push)
  - https://github.com/ntdiaz87-sudo/odoo-scem.git       (aplanado: 3 addons de code.pyxelsolution.com como archivos, .git originales en backup/nested_gits/; custom_muk sin static/description; falta crear repo+push)
  - Avilmat: el usuario decidió NO ponerlo en git.
- Rama `main`. Credenciales ya guardadas en Git Credential Manager -> Claude
  puede hacer push/pull sin login interactivo (el primer login se hizo en la
  terminal del usuario porque el navegador no abre desde el entorno de Claude).
- **Memoria de Claude por git**: carpeta `.claude-memory/` dentro de cada repo,
  enlazada via **junction** a `C:\Users\<user>\.claude\projects\<KEY>\memory`.
  KEY: `C--odoo-enetradex` / `C--odoo-agrimpex`. Script `setup-claude-memory.ps1`
  recrea el enlace en cada PC tras clonar.
- `.gitignore` excluye datos vivos (postgres-data, odoo-data), backup/, images/,
  dumps y zips. La BD NO va por git: se pasa con pg_dump aparte.

**Why:** quiere abrir Claude Code en la otra PC y que "recuerde todo" + tener el
código sincronizado, todo por internet (un solo servicio, GitHub).

**How to apply:** para sincronizar, push/pull normal. En PC nueva: clonar a la
MISMA ruta (C:\odoo_enetradex / C:\odoo_agrimpex) y correr setup-claude-memory.ps1.
La presentación sigue siendo local: ver [[presentacion-localhost]]. Backups de
BD: ver flujo en [[proyecto-enetec-odin]].
