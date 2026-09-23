; MultiLink Windows Installer Script (Inno Setup)
; Run with Inno Setup Compiler (ISCC.exe) to produce MultiLink_Setup.exe

#define MyAppName "MultiLink Download Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MultiLink Team"
#define MyAppURL "https://github.com"
#define MyAppExeName "MultiLink.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
AppId={{5A9F0D9C-4D2A-4D78-9B9B-C578A48DF745}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\MultiLink
DisableProgramGroupPage=yes
LicenseFile=
SetupIconFile=icon.ico
OutputDir=..\dist_installer
OutputBaseFilename=MultiLink_Setup_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\MultiLink\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
