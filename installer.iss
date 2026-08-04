#define MyAppName "Libre Desktop Overlay"
#define MyAppVersion "1.0.4"
#define MyAppPublisher "Libre Desktop Overlay"
#define MyAppExeName "LibreDesktopOverlay.exe"

[Setup]
AppId={{B5E6A0D4-6C1F-4F35-8D73-7D06E1E6B1A2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\LibreDesktopOverlay
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=standalone
OutputBaseFilename=LibreDesktopOverlay-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "standalone\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
