@echo off
REM Doc Alchemist installer for Windows 10/11.
REM Installs pandoc + LibreOffice (via winget), sets up markitdown,
REM and puts a shortcut on the Desktop.
setlocal
cd /d "%~dp0"

echo ==^> Checking Python...
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3 is required. Install it from https://python.org
    echo IMPORTANT: tick "Add Python to PATH" during setup, then re-run this.
    pause
    exit /b 1
)

echo ==^> Installing pandoc...
where pandoc >nul 2>&1 || winget install --id JohnMacFarlane.Pandoc -e --accept-source-agreements --accept-package-agreements

echo ==^> Installing LibreOffice (used for PDF export)...
if not exist "%ProgramFiles%\LibreOffice\program\soffice.exe" (
    winget install --id TheDocumentFoundation.LibreOffice -e --accept-source-agreements --accept-package-agreements
)

echo ==^> Setting up Python packages (markitdown, drag ^& drop)...
if not exist venv\Scripts\pip.exe py -3 -m venv venv
venv\Scripts\pip install --quiet --upgrade pip
venv\Scripts\pip install --quiet "markitdown[pdf,docx]" tkinterdnd2 fpdf2 markdown docx2pdf

echo ==^> Creating Desktop shortcut...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Doc Alchemist.lnk');" ^
  "$lnk.TargetPath = '%CD%\venv\Scripts\pythonw.exe';" ^
  "$lnk.Arguments = '\"%CD%\app-windows.pyw\"';" ^
  "$lnk.WorkingDirectory = '%CD%';" ^
  "$lnk.IconLocation = '%CD%\assets\icon.ico';" ^
  "$lnk.Save()"

echo.
echo Done! Launch "Doc Alchemist" from your Desktop.
echo (If pandoc was just installed, sign out/in once so it's on PATH.)
pause
