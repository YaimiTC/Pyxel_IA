# Arranca Odoo 17 con la configuración del proyecto.
# Uso:
#   .\start-odoo.ps1                      -> arranque normal
#   .\start-odoo.ps1 --dev=reload         -> recarga automática al cambiar código Python
#   .\start-odoo.ps1 -u mi_modulo -d odoo17_dev  -> actualizar un módulo en la BD
& "$PSScriptRoot\venv\Scripts\python.exe" "$PSScriptRoot\odoo\odoo-bin" -c "$PSScriptRoot\odoo.conf" @args
