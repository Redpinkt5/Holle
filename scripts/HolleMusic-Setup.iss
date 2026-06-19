; Holle Music Windows Installer
; Compile with Inno Setup: https://jrsoftware.org/isdl.php
; In CI, the HOLLE_VERSION environment variable is set from the release tag.

#define MyAppName "Holle Music"
#define MyAppVersion GetEnv('HOLLE_VERSION')
#define MyAppPublisher "Holle Music"
#define MyAppURL "https://github.com/Redpinkt5/Holle"

[Setup]
AppId={{HOLLE-MUSIC-2026-0619}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=no
LicenseFile=..\LICENSE.txt
OutputDir=..\dist
OutputBaseFilename=HolleMusic-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon_hollemusic"; Description: "{cm:CreateDesktopIcon} Holle Music"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "desktopicon_hollepet"; Description: "{cm:CreateDesktopIcon} Holle 桌面助手"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "开机自动启动 Holle 桌面助手"; GroupDescription: "其他"; Flags: unchecked

[Files]
Source: "..\dist\hollemusic.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\hollepet.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Holle Music"; Filename: "{app}\hollemusic.exe"
Name: "{group}\Holle 桌面助手"; Filename: "{app}\hollepet.exe"
Name: "{autodesktop}\Holle Music"; Filename: "{app}\hollemusic.exe"; Tasks: desktopicon_hollemusic
Name: "{autodesktop}\Holle 桌面助手"; Filename: "{app}\hollepet.exe"; Tasks: desktopicon_hollepet

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "HollePet"; ValueData: ""{app}\hollepet.exe""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\hollemusic.exe"; Description: "立即运行 Holle Music"; Flags: nowait postinstall skipifsilent
