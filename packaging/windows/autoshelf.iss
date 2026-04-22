#define AppVersion "{{VERSION}}"

[Setup]
AppId={{3F5C21E4-32A4-4BC9-ACB2-60B7101D3A64}
AppName=autoshelf
AppVersion={#AppVersion}
AppPublisher=autoshelf
DefaultDirName={autopf}\autoshelf
DefaultGroupName=autoshelf
LicenseFile={{PROJECT_ROOT}}\LICENSE
OutputDir={{PROJECT_ROOT}}\dist
OutputBaseFilename=autoshelf-{#AppVersion}-win-x64-setup
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\autoshelf.exe
SetupLogging=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "addtopath"; Description: "autoshelf-cli.exe를 PATH에 추가"; GroupDescription: "추가 작업:"; Flags: checkedonce
Name: "removedata"; Description: "사용자 설정 및 다운로드한 모델도 삭제"; GroupDescription: "제거 옵션:"; Flags: unchecked

[Files]
Source: "{{PROJECT_ROOT}}\dist\autoshelf\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "{{PROJECT_ROOT}}\docs\USER_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{{PROJECT_ROOT}}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\autoshelf"; Filename: "{app}\autoshelf.exe"
Name: "{group}\autoshelf CLI"; Filename: "{app}\autoshelf-cli.exe"
Name: "{group}\문서 열기"; Filename: "{app}\docs\USER_GUIDE.md"

[Registry]
Root: HKCU; Subkey: "Software\Classes\.autoshelf-plan"; ValueType: string; ValueName: ""; ValueData: "autoshelf.plan"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\autoshelf.plan"; ValueType: string; ValueName: ""; ValueData: "autoshelf plan"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\autoshelf.plan\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\autoshelf.exe,0"
Root: HKCU; Subkey: "Software\Classes\autoshelf.plan\shell\open"; ValueType: string; ValueName: ""; ValueData: "autoshelf로 열기"
Root: HKCU; Subkey: "Software\Classes\autoshelf.plan\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\autoshelf-cli.exe"" apply --resume ""%1"""

[Code]
const
  EnvPathKey = 'Environment';

procedure AddToUserPath();
var
  CurrentPath: string;
  BinPath: string;
begin
  if not IsTaskSelected('addtopath') then
    exit;
  BinPath := ExpandConstant('{app}');
  if RegQueryStringValue(HKEY_CURRENT_USER, EnvPathKey, 'Path', CurrentPath) then begin
    if Pos(BinPath, CurrentPath) = 0 then
      RegWriteStringValue(HKEY_CURRENT_USER, EnvPathKey, 'Path', CurrentPath + ';' + BinPath);
  end else
    RegWriteStringValue(HKEY_CURRENT_USER, EnvPathKey, 'Path', BinPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    AddToUserPath();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath: string;
begin
  if CurUninstallStep = usPostUninstall then begin
    DataPath := ExpandConstant('{localappdata}\autoshelf');
    if IsTaskSelected('removedata') then
      DelTree(DataPath, True, True, True);
  end;
end;
