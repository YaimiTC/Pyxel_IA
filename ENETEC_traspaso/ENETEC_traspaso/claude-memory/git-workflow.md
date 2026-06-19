---
name: git-workflow
description: "Flujo Git del usuario — local-first, push a la nube solo con su aprobación explícita"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0852c323-f81a-4b41-90ea-80b200e8aa52
---

El usuario trabaja **local-first**: desarrolla y prueba todo en localhost. Quiere:
- **Commits locales** libremente (snapshots en el Git local de `C:\Proyectos`).
- **Push a su cuenta GitHub privada SOLO cuando él lo apruebe explícitamente** ("cuando termine y yo esté de acuerdo"). NUNCA hacer `git push` sin su OK directo.
- **Base de datos organizada aparte**: la BD de Odoo vive en volúmenes Docker (no en Git) y puede tener datos sensibles → backups **locales** con scripts en `C:\Proyectos\scripts\` (db-backup.ps1 / db-restore.ps1), carpeta `backups/` gitignored. No subir dumps con datos personales a la nube.

**Why:** Mantiene el control de qué llega a la nube y protege datos sensibles (carnés/clientes).

**How to apply:** Puedo `git add`/`commit` local en hitos. Para `git push`, esperar su aprobación explícita. Cuando vaya a subir, recordarle qué incluye y confirmar.

**Remoto YA configurado:** repo privado **https://github.com/ntdiaz87-sudo/validador-de-documentos** (cuenta GitHub `ntdiaz87-sudo`), rama `main`, `origin` con tracking. Carpeta local sigue siendo `C:\Proyectos` (no renombrar: rompe montajes Docker y autoMemoryDirectory). gh en `C:\Program Files\GitHub CLI\gh.exe`. IMPORTANTE: la sesión de gh quedó autenticada en el entorno **Bash** (keyring); ejecutar comandos `gh` vía la herramienta **Bash**, no PowerShell (PowerShell no ve la sesión). `git push`/`git pull` funcionan desde cualquiera. Identidad commits: Nilo T <ntdiaz87@gmail.com>.

Relacionado con [[working-style-autonomy]] y [[docvalidator-project]].
