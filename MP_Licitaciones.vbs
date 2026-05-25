' ============================================================
'  MP_Licitaciones — Lanzador universal (auto-instalacion)
' ============================================================
'
'  Doble clic en este archivo para iniciar la aplicacion.
'
'  Primera vez: instala automaticamente el entorno Python y
'               las dependencias. Solo requiere tener Python
'               instalado con "Add Python to PATH" marcado.
'
'  Resto de veces: abre la aplicacion directamente.
'
'  No se requiere ninguna accion del usuario en el flujo normal.
' ============================================================
Option Explicit

Dim fso, wsh, raiz, venvBase, pythonw, python, script, reqFile, envFile, envExample, ret

Set fso = CreateObject("Scripting.FileSystemObject")
Set wsh = CreateObject("WScript.Shell")

raiz       = fso.GetParentFolderName(WScript.ScriptFullName)
venvBase   = wsh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\MP\Licitaciones_MP"
pythonw    = venvBase & "\.venv\Scripts\pythonw.exe"
python     = venvBase & "\.venv\Scripts\python.exe"
script     = raiz & "\mp_launcher\MP_Licitaciones.py"
reqFile    = raiz & "\requirements.txt"
envFile    = raiz & "\.env"
envExample = raiz & "\.env.example"

' ── Primera vez: instalar entorno ─────────────────────────────────────────
If Not fso.FileExists(python) Then

    ' Verificar que Python este disponible en el sistema
    ret = wsh.Run("cmd /c python --version >nul 2>&1", 0, True)
    If ret <> 0 Then
        MsgBox "Python no esta instalado o no esta en el PATH." & vbCrLf & vbCrLf & _
               "Descargalo desde https://www.python.org/downloads/" & vbCrLf & _
               "Marca ""Add Python to PATH"" al instalar y vuelve a intentarlo.", _
               vbCritical, "MP - Licitaciones"
        WScript.Quit 1
    End If

    ' Crear carpeta base del entorno (dos niveles: MP y luego Licitaciones_MP)
    Dim mpDir
    mpDir = wsh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\MP"
    If Not fso.FolderExists(mpDir) Then fso.CreateFolder mpDir
    If Not fso.FolderExists(venvBase) Then fso.CreateFolder venvBase

    ' Crear entorno virtual (ventana visible para mostrar progreso)
    ret = wsh.Run("cmd /c title MP - Preparando entorno... & python -m venv """ & venvBase & "\.venv""", 1, True)
    If ret <> 0 Then
        MsgBox "No se pudo crear el entorno virtual." & vbCrLf & _
               "Asegurate de que Python este en el PATH y vuelve a intentarlo.", _
               vbCritical, "MP - Licitaciones"
        WScript.Quit 1
    End If

    ' Actualizar pip (silencioso)
    wsh.Run "cmd /c """ & python & """ -m pip install --upgrade pip --quiet", 0, True

    ' Instalar dependencias (ventana visible con progreso, sin interaccion)
    ret = wsh.Run("cmd /c title MP - Instalando dependencias... & """ & python & """ -m pip install -r """ & reqFile & """", 1, True)
    If ret <> 0 Then
        MsgBox "No se pudieron instalar las dependencias." & vbCrLf & _
               "Revisa tu conexion a Internet e intenta de nuevo.", _
               vbCritical, "MP - Licitaciones"
        WScript.Quit 1
    End If

    ' Copiar .env desde ejemplo si no existe aun
    If Not fso.FileExists(envFile) And fso.FileExists(envExample) Then
        fso.CopyFile envExample, envFile
    End If

    ' Crear acceso directo en el escritorio para proximas veces
    wsh.Run "powershell -ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden " & _
            "-File """ & raiz & "\mp_launcher\crear_acceso_directo.ps1""", 0, True

End If

' ── Lanzar aplicacion ─────────────────────────────────────────────────────
If Not fso.FileExists(pythonw) Then
    MsgBox "No se encontro pythonw.exe en el entorno virtual:" & vbCrLf & pythonw & vbCrLf & vbCrLf & _
           "Borra la carpeta .venv y vuelve a abrir este archivo.", _
           vbCritical, "MP - Licitaciones"
    WScript.Quit 1
End If

wsh.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & script & Chr(34), 0, False
