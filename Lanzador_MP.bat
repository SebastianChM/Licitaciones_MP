@echo off
REM Lanzador de Licitaciones MP
REM Este archivo ejecuta la interfaz gráfica del sistema

title MP - Licitaciones Mercado Publico

echo.
echo ================================================
echo    🏛️ MP CONSULTING - LICITACIONES MP
echo ================================================
echo.
echo Iniciando interfaz grafica...
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Activar entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    echo Activando entorno virtual...
    call ".venv\Scripts\activate.bat"
)

REM Ejecutar el lanzador
python lanzador_licitaciones.py

REM Si hay error, mostrar mensaje
if errorlevel 1 (
    echo.
    echo ❌ Error al ejecutar el sistema
    echo Presiona cualquier tecla para salir...
    pause >nul
)

REM Desactivar entorno virtual
if exist ".venv\Scripts\deactivate.bat" (
    call ".venv\Scripts\deactivate.bat"
)