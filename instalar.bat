@echo off
REM ============================================================
REM  MP - Licitaciones Mercado Publico — Instalacion inicial
REM  Ejecutar una sola vez antes del primer uso.
REM ============================================================
title MP - Instalacion del sistema
chcp 65001 >nul

cd /d "%~dp0"

echo.
echo ================================================
echo    MP CONSULTING - Instalacion del sistema
echo ================================================
echo.

REM --- 1. Verificar Python -----------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo         Descargalo desde https://www.python.org/downloads/
    echo         Asegurate de marcar "Add Python to PATH" al instalar.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v encontrado

REM --- 2. Crear entorno virtual ------------------------------------
if exist ".venv\Scripts\activate.bat" (
    echo [OK] Entorno virtual ya existe, omitiendo creacion.
) else (
    echo [1/3] Creando entorno virtual (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
)

REM --- 3. Instalar dependencias ------------------------------------
echo [2/3] Instalando dependencias (puede tardar unos minutos)...
call ".venv\Scripts\pip" install --upgrade pip --quiet
call ".venv\Scripts\pip" install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias.
    echo         Revisa tu conexion a Internet e intenta de nuevo.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

REM --- 4. Crear .env si no existe ----------------------------------
echo [3/3] Configurando archivo de variables de entorno...
if exist ".env" (
    echo [OK] Archivo .env ya existe, no se sobreescribe.
) else (
    copy ".env.example" ".env" >nul
    echo [OK] Archivo .env creado desde plantilla.
    echo.
    echo  IMPORTANTE: Abre el archivo .env con un editor de texto
    echo  y completa los valores de las API Keys:
    echo    - LICIT_MERCADO_PUBLICO_TICKET  (API Key de Mercado Publico)
    echo    - LICIT_CMF_API_KEY             (opcional, para valor UTM en vivo)
    echo.
)

REM --- 5. Crear acceso directo en el escritorio --------------------
echo Creando acceso directo en el escritorio...
powershell -ExecutionPolicy Bypass -File "%~dp0crear_acceso_directo.ps1" -Titulo "MP Licitaciones" >nul 2>&1
if errorlevel 1 (
    echo [AVISO] No se pudo crear el acceso directo automaticamente.
    echo         Puedes ejecutar el sistema con: Lanzador_MP.bat
) else (
    echo [OK] Acceso directo creado en el escritorio.
)

REM --- Fin ----------------------------------------------------------
echo.
echo ================================================
echo    Instalacion completada exitosamente.
echo    Usa "MP Licitaciones" en tu escritorio
echo    o haz doble clic en Lanzador_MP.bat
echo ================================================
echo.
pause
