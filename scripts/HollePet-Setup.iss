; Holle Pet Desktop Installer
; Compile with Inno Setup: https://jrsoftware.org/isdl.php

#define MyAppName "Holle Pet"
#define MyAppVersion "0.1.1"
#define MyAppPublisher "Holle Music"
#define MyAppURL "https://github.com/Redpinkt5/Holle"
#define MyAppExeName "HollePet.exe"

[Setup]
AppId={{HOLLE-PET-2026-0611}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\HollePet
DisableProgramGroupPage=yes
LicenseFile=E:\DDDESKKKK\holle_music\LICENSE.txt
OutputDir=E:\DDDESKKKK\holle_music\dist\installer
OutputBaseFilename=HollePet-Setup
; SetupIconFile=E:\DDDESKKKK\holle_music\scripts\icon.ico  ; optional: add your own .ico file
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "{cm:AutoStartProgram,{#MyAppName}}"; GroupDescription: "{cm:AutoStartProgramGroupDescription}"; Flags: unchecked

[Files]
Source: "E:\DDDESKKKK\holle_music\dist\pet\HollePet.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "E:\DDDESKKKK\holle_music\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "E:\DDDESKKKK\holle_music\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "HollePet"; ValueData: ""{app}\{#MyAppExeName}""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
