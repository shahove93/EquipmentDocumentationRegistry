#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
[Setup]
#ifdef SmokeBuild
AppId={{F9E86E04-F461-4CE5-94CF-A4C91E932A8E}
#else
AppId={{9E6BCA3D-7531-4A33-9A38-E44241D72A81}
#endif
AppName=Equipment Documentation Registry
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\EDR
#ifdef SmokeBuild
DefaultGroupName=EDR Smoke Test
#else
DefaultGroupName=EDR
#endif
DisableProgramGroupPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputDir={#Output}
OutputBaseFilename=EDR-{#AppVersion}-windows-x64
Compression=lzma2
SolidCompression=yes
CloseApplications=no
RestartApplications=no
UninstallDisplayName=Equipment Documentation Registry
SetupLogging=yes

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\EDR"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launcher.ps1"" start"; WorkingDir: "{app}"
Name: "{userdesktop}\EDR"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launcher.ps1"" start"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Stop EDR"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launcher.ps1"" stop"; WorkingDir: "{app}"
Name: "{group}\Windows guide"; Filename: "{app}\Windows-guide.md"

[Tasks]
Name: desktopicon; Description: "Create EDR desktop shortcut"

[Code]
const
  MicrosoftRuntimeUrl = 'https://learn.microsoft.com/en-US/cpp/windows/latest-supported-vc-redist?view=msvc-160';

function HasCrtFile(Name: String): Boolean;
var
  MS, LS: Cardinal;
begin
  Result := GetVersionNumbers(ExpandConstant('{sys}\' + Name), MS, LS);
  if Result then
    Result := MS >= ((14 shl 16) or 44);
end;

function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Result := HasCrtFile('msvcp140.dll') and HasCrtFile('vcruntime140.dll') and HasCrtFile('vcruntime140_1.dll');
#ifdef SmokeBuild
  // Test-only switch: verifies the absent-runtime path without touching Windows DLLs.
  if ExpandConstant('{param:EDRTestMissingCRT|0}') = '1' then Result := False;
#endif
  if not Result then begin
    if not WizardSilent then begin
      MsgBox('EDR: требуется Microsoft Visual C++ Runtime x64 14.44 или новее. Откроется официальная страница Microsoft. Установите пакет x64 (Windows может запросить права администратора), затем повторите установку EDR.', mbInformation, MB_OK);
      ShellExec('open', MicrosoftRuntimeUrl, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
    Log('Missing Microsoft Visual C++ x64 >=14.44. Install prerequisite: ' + MicrosoftRuntimeUrl);
  end;
end;

function StopEDR(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if FileExists(ExpandConstant('{app}\python\python.exe')) then
    Result := Exec(ExpandConstant('{app}\python\python.exe'), '-B -m app.windows_local stop',
      ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not StopEDR() then
    Result := 'EDR could not stop safely. Close maintenance operations and retry. Data has been preserved.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := StopEDR();
  if not Result then
    MsgBox('EDR could not stop safely. Uninstall cancelled; data preserved.', mbError, MB_OK);
end;

// No UninstallDelete and no data-directory entries: user data is never removed.
