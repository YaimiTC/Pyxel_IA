# Memoria de Claude — sincronizada por git

Esta carpeta (`.claude-memory/`) contiene la **memoria del proyecto** que usa
Claude Code (lo que "recuerda" de ENETEC / ODIN 2.0).

Vive dentro del repo para que viaje por git entre tus PCs. En cada PC, un
**enlace (junction)** conecta esta carpeta con la ruta interna de Claude:

```
C:\Users\<TU_USUARIO>\.claude\projects\C--odoo-enetradex\memory
        └──(junction)──►  C:\odoo_enetradex\.claude-memory
```

## En una PC NUEVA (1ª vez)
1. Clona el repo en `C:\odoo_enetradex`.
2. Ejecuta en la raíz del repo:  `.\setup-claude-memory.ps1`
   (clic derecho → "Ejecutar con PowerShell")
3. Abre Claude Code en el proyecto. Recordará todo.

## Día a día
- Cuando Claude guarda una nota nueva, cae aquí automáticamente (vía el enlace).
- `git push` la sube; `git pull` en la otra PC la baja. Sin pasos extra.

> No edites estos `.md` a mano salvo que sepas lo que haces: los gestiona Claude.
