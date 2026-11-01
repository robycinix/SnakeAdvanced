; Script Inno Setup per Snake Advanced.
; Viene compilato da build.py dopo aver creato dist\SnakeAdvanced.exe.
; Installa per l'utente corrente (nessun permesso di amministratore richiesto).

#define AppName "Snake Advanced"
#define AppVersion "1.0.0"
#define AppExe "SnakeAdvanced.exe"

[Setup]
AppId={{7E3C2B1A-5D4F-4A8E-9C61-2F0B7A9D4E51}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Roby
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SnakeAdvanced-Setup
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
