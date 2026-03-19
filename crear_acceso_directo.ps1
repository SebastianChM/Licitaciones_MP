# Script para crear acceso directo en el escritorio
# Ejecutar como: powershell -ExecutionPolicy Bypass -File crear_acceso_directo.ps1

param(
    [string]$Titulo = "MP Licitaciones",
    [string]$Descripcion = "Sistema de Licitaciones Mercado Publico - Sebastian Chirino"
)

try {
    Write-Host "Creando acceso directo en el escritorio..." -ForegroundColor Cyan
    
    # Rutas
    $EscritorioPath = [Environment]::GetFolderPath("Desktop")
    $ProyectoPath = $PSScriptRoot
    $LanzadorPath = Join-Path $ProyectoPath "Lanzador_MP.bat"
    $AccesoDirectoPath = Join-Path $EscritorioPath "$Titulo.lnk"
    
    # Verificar que existe el lanzador
    if (-not (Test-Path $LanzadorPath)) {
        Write-Host "ERROR: No se encuentra el archivo $LanzadorPath" -ForegroundColor Red
        exit 1
    }
    
    # Crear objeto WScript.Shell
    $Shell = New-Object -ComObject WScript.Shell
    $AccesoDirecto = $Shell.CreateShortcut($AccesoDirectoPath)
    
    # Configurar propiedades del acceso directo
    $AccesoDirecto.TargetPath = $LanzadorPath
    $AccesoDirecto.WorkingDirectory = $ProyectoPath
    $AccesoDirecto.Description = $Descripcion
    $AccesoDirecto.WindowStyle = 1  # Ventana normal
    
    # Intentar usar un icono personalizado (opcional)
    $IconoPath = Join-Path $ProyectoPath "icono_mp.ico"
    if (Test-Path $IconoPath) {
        $AccesoDirecto.IconLocation = "$IconoPath,0"
    }
    
    # Guardar el acceso directo
    $AccesoDirecto.Save()
    
    Write-Host "EXITO: Acceso directo creado exitosamente:" -ForegroundColor Green
    Write-Host "   Ubicacion: $AccesoDirectoPath" -ForegroundColor White
    Write-Host "   Apunta a: $LanzadorPath" -ForegroundColor White
    Write-Host "   Directorio trabajo: $ProyectoPath" -ForegroundColor White
    
    Write-Host ""
    Write-Host "LISTO! Ahora puedes hacer doble clic en el icono del escritorio para ejecutar el sistema." -ForegroundColor Yellow
    
    # Abrir el escritorio para mostrar el acceso directo
    Start-Process explorer.exe $EscritorioPath
    
} catch {
    Write-Host "ERROR al crear el acceso directo: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Pausa para que el usuario vea el resultado
Write-Host ""
Write-Host "Presiona cualquier tecla para continuar..." -ForegroundColor Gray
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null