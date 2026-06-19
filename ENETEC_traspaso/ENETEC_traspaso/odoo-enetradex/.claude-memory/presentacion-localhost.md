---
name: presentacion-localhost
description: El sistema ENETEC se presenta SIEMPRE en localhost (Docker local); git/GitHub es solo para mover código
metadata: 
  node_type: memory
  type: project
  originSessionId: 1bed270a-2ef9-45a7-aabc-ba47e5cc1391
---

A la hora de presentar el sistema ODIN 2.0 al cliente, debe verse en
**localhost** (`http://localhost:8469`, Docker local), funcionando offline.

GitHub/git es ÚNICAMENTE un canal para sincronizar el código entre las PCs del
usuario (casa/oficina) y respaldo — NO hostea ni publica Odoo. El código puede
estar "arriba" (GitHub) y local a la vez; lo que Docker ejecuta es siempre la
copia local.

**Why:** el usuario trabaja desde varias PCs y con internet inestable; quiere
sincronizar por internet (git pull/push) pero la demo no puede depender de
conexión.

**How to apply:** nunca proponer desplegar Odoo en la nube ni servirlo por una
URL pública para la presentación. Flujo correcto: `git pull` (traer código) ->
`docker compose up` -> presentar en localhost. Ver [[entorno-odin-enetec]] y
[[proyecto-enetec-odin]].
