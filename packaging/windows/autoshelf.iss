[Setup]
AppName=autoshelf
AppVersion=2.0.0
DefaultDirName={pf}\autoshelf
DefaultGroupName=autoshelf
OutputBaseFilename=autoshelf-2.0.0-win-x64-setup
ArchitecturesInstallIn64BitMode=x64
; llama-cpp-python uses prebuilt CPU wheels. The first-run GGUF download is not bundled.

[Files]
Source: "dist\autoshelf\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\autoshelf"; Filename: "{app}\autoshelf.exe"

[Registry]
Root: HKCR; Subkey: ".autoshelf-plan"; ValueType: string; ValueData: "autoshelf.plan"; Flags: uninsdeletevalue
