# ============================================================
#  Backup LOCAL de la base de datos de Odoo (+ filestore/adjuntos)
#  Genera ficheros en C:\Proyectos\backups (gitignored, NO se sube a la nube).
#  Uso:  .\scripts\db-backup.ps1            (BD por defecto: docverif)
#        .\scripts\db-backup.ps1 -Db otra
# ============================================================
param(
    [string]$Db = "docverif",
    [string]$DbContainer = "odoo17-db",
    [string]$AppContainer = "odoo17-app"
)

$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$root = "C:\Proyectos\backups"
New-Item -ItemType Directory -Force -Path $root | Out-Null

# 1) Dump de la BD (formato custom de pg_dump, comprimido y binario-seguro).
#    Se vuelca dentro del contenedor y se copia con docker cp (evita corromper
#    el binario por la redireccion de PowerShell).
$dumpName = "${Db}_$ts.dump"
$dumpPath = Join-Path $root $dumpName
Write-Host "1) Dump de BD '$Db' ..."
docker exec $DbContainer pg_dump -U odoo -Fc -f "/tmp/$dumpName" $Db
docker cp "${DbContainer}:/tmp/$dumpName" $dumpPath
docker exec $DbContainer rm "/tmp/$dumpName"
Write-Host "   -> $dumpPath"

# 2) Filestore (adjuntos de Odoo: imagenes de carnes, etc.)
$fsName = "${Db}_filestore_$ts"
$fsPath = Join-Path $root $fsName
Write-Host "2) Filestore (adjuntos) ..."
try {
    docker cp "${AppContainer}:/var/lib/odoo/filestore/$Db" $fsPath
    Write-Host "   -> $fsPath"
} catch {
    Write-Host "   (sin filestore para '$Db', se omite)"
}

Write-Host "`nBackup completo: $root"
Get-ChildItem $root -Filter "${Db}_*$ts*" | Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,2)}}
