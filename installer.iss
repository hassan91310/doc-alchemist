; Inno Setup script for the Doc Alchemist Windows installer.
; Built in CI with: iscc /DMyAppVersion=x.y.z installer.iss
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{7E2F30A1-9C4B-4D2B-B7E5-DOC4LCH3M1ST}
AppName=Doc Alchemist
AppVersion={#MyAppVersion}
AppPublisher=Hassan Ali
DefaultDirName={autopf}\Doc Alchemist
DefaultGroupName=Doc Alchemist
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=DocAlchemist-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\DocAlchemist.exe
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "dist\DocAlchemist.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\icon.ico"; DestDir: "{app}"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"
Name: "pandoc"; Description: "Install pandoc (required — document engine)"
Name: "libreoffice"; Description: "Install LibreOffice (needed for PDF export)"; Flags: unchecked

[Icons]
Name: "{autoprograms}\Doc Alchemist"; Filename: "{app}\DocAlchemist.exe"
Name: "{autodesktop}\Doc Alchemist"; Filename: "{app}\DocAlchemist.exe"; Tasks: desktopicon

[Run]
Filename: "cmd.exe"; Parameters: "/c winget install --id JohnMacFarlane.Pandoc -e --accept-source-agreements --accept-package-agreements"; StatusMsg: "Installing pandoc (this can take a minute)..."; Tasks: pandoc; Flags: runasoriginaluser
Filename: "cmd.exe"; Parameters: "/c winget install --id TheDocumentFoundation.LibreOffice -e --accept-source-agreements --accept-package-agreements"; StatusMsg: "Installing LibreOffice (this can take several minutes)..."; Tasks: libreoffice; Flags: runasoriginaluser
Filename: "{app}\DocAlchemist.exe"; Description: "Launch Doc Alchemist"; Flags: nowait postinstall skipifsilent
