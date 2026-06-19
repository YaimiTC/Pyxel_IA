# ════════════════════════════════════════════════════════════════
#  setup-claude-memory.ps1
#  Conecta la memoria de Claude (carpeta del repo .claude-memory)
#  con la ruta que Claude Code usa en ESTA PC.
#
#  Ejecutar UNA sola vez por PC, después de clonar el repo.
#  Uso:  clic derecho -> "Ejecutar con PowerShell"
#        o en PowerShell:  .\setup-claude-memory.ps1
# ════════════════════════════════════════════════════════════════

$ErrorActionPreference = 'Stop'

$repo      = $PSScriptRoot
$memSource = Join-Path $repo '.claude-memory'
$projKey   = 'C--odoo-enetradex'
$link      = Join-Path $env:USERPROFILE ".claude\projects\$projKey\memory"
$parent    = Split-Path $link -Parent

Write-Host "Repo            : $repo"
Write-Host "Memoria (repo)  : $memSource"
Write-Host "Enlace a crear  : $link"
Write-Host ""

if (-not (Test-Path $memSource)) {
    Write-Host "ERROR: no existe '$memSource'." -ForegroundColor Red
    Write-Host "¿Clonaste el repo e hiciste 'git pull'? El script debe estar dentro del repo."
    exit 1
}

# Crear la carpeta padre del perfil si no existe
New-Item -ItemType Directory -Force -Path $parent | Out-Null

# Si ya hay algo en la ruta del enlace, decidir qué hacer
if (Test-Path $link) {
    $item = Get-Item $link -Force
    if ($item.LinkType -eq 'Junction') {
        Write-Host "Ya existe un enlace aqui. Nada que hacer. ✅" -ForegroundColor Green
        exit 0
    } else {
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $bak = "$link._backup_$stamp"
        Move-Item -Force $link $bak
        Write-Host "Habia una carpeta de memoria real; se respaldo en:" -ForegroundColor Yellow
        Write-Host "  $bak"
    }
}

# Crear el enlace (junction; no requiere permisos de administrador)
New-Item -ItemType Junction -Path $link -Target $memSource | Out-Null

$count = (Get-ChildItem $link | Measure-Object).Count
Write-Host ""
Write-Host "✅ Listo. Enlace creado." -ForegroundColor Green
Write-Host "   $link  ->  $memSource"
Write-Host "   Archivos de memoria visibles: $count"
Write-Host ""
Write-Host "Ya puedes abrir Claude Code en este proyecto y recordara todo."
