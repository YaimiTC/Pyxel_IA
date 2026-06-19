# ============================================================
#  Restaura la base de datos de Odoo desde un backup .dump
#  CUIDADO: RECREA la BD (borra la actual con ese nombre).
#  Uso:  .\scripts\db-restore.ps1 -DumpFile C:\Proyectos\backups\docverif_XXXX.dump
#        (opcional) -FilestoreDir C:\Proyectos\backups\docverif_filestore_XXXX
# ============================================================
param(
    [Parameter(Mandatory = $true)][string]$DumpFile,
    [string]$FilestoreDir = "",
    [string]$Db = "docverif",
    [string]$DbContainer = "odoo17-db",
    [string]$AppContainer = "odoo17-app"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $DumpFile)) { throw "No existe el dump: $DumpFile" }

Write-Host "Parando Odoo para restaurar limpio ..."
docker stop $AppContainer | Out-Null

Write-Host "Recreando BD '$Db' ..."
docker exec $DbContainer psql -U odoo -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$Db';" | Out-Null
docker exec $DbContainer psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $Db;" | Out-Null
docker exec $DbContainer psql -U odoo -d postgres -c "CREATE DATABASE $Db OWNER odoo;" | Out-Null

Write-Host "Restaurando dump ..."
docker cp $DumpFile "${DbContainer}:/tmp/restore.dump"
docker exec $DbContainer pg_restore -U odoo -d $Db --no-owner /tmp/restore.dump
docker exec $DbContainer rm /tmp/restore.dump

if ($FilestoreDir -and (Test-Path $FilestoreDir)) {
    Write-Host "Restaurando filestore ..."
    docker start $AppContainer | Out-Null
    docker exec $AppContainer mkdir -p "/var/lib/odoo/filestore/$Db"
    docker cp "$FilestoreDir/." "${AppContainer}:/var/lib/odoo/filestore/$Db"
} else {
    docker start $AppContainer | Out-Null
}

Write-Host "`nRestauracion completa. Odoo reiniciado."
