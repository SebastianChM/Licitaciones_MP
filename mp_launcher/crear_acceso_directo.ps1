<#
.SYNOPSIS
    Crea el acceso directo MP_Licitaciones.lnk en la raíz del proyecto.
.DESCRIPTION
    USUARIOS FINALES   → doble clic en MP_Licitaciones.lnk  (este script lo genera)
                         o en MP_Licitaciones.vbs  (también en la raíz).
    DESARROLLADORES    → pueden usar mp_launcher\MP_Licitaciones_DEV.vbs
                         o ejecutar mp_launcher\MP_Licitaciones.py directamente.

    El acceso directo apunta al VBS de la raíz vía wscript.exe para que
    Windows muestre el ícono personalizado MP.ico en el Explorador.
    Ejecutar una vez tras instalar o mover la carpeta del proyecto.
.NOTES
    Prerequisito: instalar.bat debe haberse ejecutado antes (.venv creado).
#>

$ErrorActionPreference = "Stop"

$launcherDir  = $PSScriptRoot
$projectRoot  = Split-Path $launcherDir -Parent
$venvBase     = Join-Path $env:LOCALAPPDATA "MP\Licitaciones_MP"
$pythonExe    = Join-Path $venvBase ".venv\Scripts\python.exe"
$vbsPath      = Join-Path $projectRoot "MP_Licitaciones.vbs"
$icoPath      = Join-Path $launcherDir "MP.ico"
$desktopPath  = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "MP_Licitaciones.lnk"
$wscript      = "$env:SystemRoot\System32\wscript.exe"

# ── Prerequisitos ────────────────────────────────────────────────────────────
if (-not (Test-Path $vbsPath)) {
    Write-Error "MP_Licitaciones.vbs no encontrado en:`n  $vbsPath"
    exit 1
}

# ── Generar ícono si no existe ───────────────────────────────────────────────
if (-not (Test-Path $icoPath)) {
    Write-Host "Generando icono MP.ico..." -ForegroundColor Cyan
    & $pythonExe (Join-Path $launcherDir "generar_icono.py")
}

# ── Crear acceso directo ─────────────────────────────────────────────────────
$wsh              = New-Object -ComObject WScript.Shell
$lnk              = $wsh.CreateShortcut($shortcutPath)
$lnk.TargetPath       = $wscript
$lnk.Arguments        = "`"$vbsPath`""
$lnk.WorkingDirectory = $projectRoot
$lnk.IconLocation     = "$icoPath,0"
$lnk.Description      = "MP - Sistema de Licitaciones Mercado Publico"
$lnk.WindowStyle      = 1
$lnk.Save()

Write-Host ""
Write-Host "  Acceso directo creado en el escritorio:" -ForegroundColor Green
Write-Host "  $shortcutPath" -ForegroundColor White
Write-Host ""
Write-Host "  Haz doble clic en el icono del escritorio para iniciar la aplicacion." -ForegroundColor Cyan
