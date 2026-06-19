# Proyecto Odoo 17 Community — Desarrollo local

## Estructura

```
odoo17/
├── odoo/            Código fuente de Odoo 17 (clon shallow de github.com/odoo/odoo, rama 17.0)
├── custom_addons/   Tus módulos personalizados (mi_modulo es la plantilla de ejemplo)
├── venv/            Entorno virtual Python 3.12
├── data/            Filestore y sesiones (se crea al primer arranque)
├── odoo.conf        Configuración (puerto 8069, BD en localhost)
└── start-odoo.ps1   Script de arranque
```

## Requisitos ya instalados

- PostgreSQL 16 (servicio `postgresql-x64-16`, puerto 5432)
  - Superusuario: `postgres` / contraseña `postgres`
  - Usuario de Odoo: `odoo` / contraseña `odoo` (con permiso CREATEDB)

## Arrancar Odoo

```powershell
cd D:\trabajo\Pyxel\IA\odoo17
.\start-odoo.ps1
```

Luego abre http://localhost:8069 — la primera vez te pedirá crear la base de datos.

### Modo desarrollo (recarga automática al editar Python)

```powershell
.\start-odoo.ps1 --dev=reload
```

### Actualizar un módulo tras cambiar su código

```powershell
.\start-odoo.ps1 -d <nombre_bd> -u mi_modulo
```

(Los cambios en XML/vistas requieren `-u`; los cambios solo en Python con `--dev=reload` se recargan solos.)

## Crear un módulo nuevo

Copia `custom_addons/mi_modulo` con otro nombre, renombra el modelo y ajusta
`__manifest__.py`. Después en Odoo: Aplicaciones → Actualizar lista de aplicaciones
(necesitas activar el modo desarrollador en Ajustes).

## Notas

- Los reportes PDF requieren wkhtmltopdf 0.12.6 (opcional): https://wkhtmltopdf.org/downloads.html
- Para actualizar el código de Odoo: `cd odoo && git pull`
