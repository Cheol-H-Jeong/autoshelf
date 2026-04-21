[Setup]
AppName=autoshelf
AppVersion=1.0.0
DefaultDirName={pf}\autoshelf
DefaultGroupName=autoshelf
OutputBaseFilename=autoshelf-1.0.0-win-x64-setup
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\autoshelf\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\autoshelf"; Filename: "{app}\autoshelf.exe"

[Registry]
Root: HKCR; Subkey: ".autoshelf-plan"; ValueType: string; ValueData: "autoshelf.plan"; Flags: uninsdeletevalue
