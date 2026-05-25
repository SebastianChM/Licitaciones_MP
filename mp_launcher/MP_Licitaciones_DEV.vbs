' ============================================================
'  MP_Licitaciones — Entrada para DESARROLLADORES / USO TÉCNICO
' ============================================================
'
'  USO NORMAL (usuarios finales):
'    Doble clic en  MP_Licitaciones.lnk  en la raíz del proyecto.
'    Tiene ícono propio y no requiere conocimientos técnicos.
'
'  USO TÉCNICO (este archivo):
'    Útil cuando el acceso directo .lnk está roto porque se movió
'    la carpeta del proyecto.  Al ser un VBS, recalcula las rutas
'    en cada ejecución de forma automática.
'    Para recrear el acceso directo ejecuta:
'      mp_launcher\crear_acceso_directo.ps1
'
'  REQUISITO: el entorno virtual debe estar instalado.
'    Si no lo está, ejecuta instalar.bat en la raíz primero.
' ============================================================
Option Explicit

Dim fso, wsh, carpeta, raiz, venvBase, pythonw, python, script, reqFile, envFile, envExample, ret

Set fso = CreateObject("Scripting.FileSystemObject")
Set wsh = CreateObject("WScript.Shell")
carpeta    = fso.GetParentFolderName(WScript.ScriptFullName)  ' .../mp_launcher/
raiz       = fso.GetParentFolderName(carpeta)                  ' .../raiz del proyecto/
venvBase   = wsh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\MP\Licitaciones_MP"
pythonw    = venvBase & "\.venv\Scripts\pythonw.exe"
python     = venvBase & "\.venv\Scripts\python.exe"
script     = carpeta & "\MP_Licitaciones.py"
reqFile    = raiz & "\requirements.txt"
envFile    = raiz & "\.env"
envExample = raiz & "\.env.example"

' ── Auto-instalar si el entorno no existe ─────────────────────────────────
If Not fso.FileExists(python) Then

    ret = wsh.Run("cmd /c python --version >nul 2>&1", 0, True)
    If ret <> 0 Then
        MsgBox "Python no esta instalado o no esta en el PATH." & vbCrLf & vbCrLf & _
               "Descargalo desde https://www.python.org/downloads/" & vbCrLf & _
               "Marca ""Add Python to PATH"" al instalar y vuelve a intentarlo.", _
               vbCritical, "MP - Licitaciones"
        WScript.Quit 1
    End If

    Dim mpDir
    mpDir = wsh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\MP"
    If Not fso.FolderExists(mpDir) Then fso.CreateFolder mpDir
    If Not fso.FolderExists(venvBase) Then fso.CreateFolder venvBase

    ret = wsh.Run("cmd /c title MP - Preparando entorno... & python -m venv """ & venvBase & "\.venv""", 1, True)
    If ret <> 0 Then
        MsgBox "No se pudo crear el entorno virtual.", vbCritical, "MP - Licitaciones"
        WScript.Quit 1
    End If

    wsh.Run "cmd /c """ & python & """ -m pip install --upgrade pip --quiet", 0, True

    ret = wsh.Run("cmd /c title MP - Instalando dependencias... & """ & python & """ -m pip install -r """ & reqFile & """", 1, True)
    If ret <> 0 Then
        MsgBox "No se pudieron instalar las dependencias." & vbCrLf & _
               "Revisa tu conexion a Internet e intenta de nuevo.", _
               vbCritical, "MP - Licitaciones"
        WScript.Quit 1
    End If

    If Not fso.FileExists(envFile) And fso.FileExists(envExample) Then
        fso.CopyFile envExample, envFile
    End If

End If

' ── Lanzar aplicacion ─────────────────────────────────────────────────────
If Not fso.FileExists(pythonw) Then
    MsgBox "No se encontro pythonw.exe en:" & vbCrLf & pythonw & vbCrLf & vbCrLf & _
           "Borra la carpeta .venv y vuelve a abrir este archivo.", _
           vbCritical, "MP - Licitaciones"
    WScript.Quit 1
End If

wsh.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & script & Chr(34), 0, False
