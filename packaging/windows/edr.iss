#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
#ifdef SmokeBuild
  #define ProductRoot "EDR-Smoke"
#else
  #define ProductRoot "EDR"
#endif
[Setup]
#ifdef SmokeBuild
AppId={{F9E86E04-F461-4CE5-94CF-A4C91E932A8E}
#else
AppId={{9E6BCA3D-7531-4A33-9A38-E44241D72A81}
#endif
AppName=Equipment Documentation Registry
AppVersion={#AppVersion}
DefaultDirName={autopf}\EDR
#ifdef SmokeBuild
DefaultGroupName=EDR Smoke Test
#else
DefaultGroupName=EDR
#endif
DisableProgramGroupPage=no
PrivilegesRequired=admin
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
Source: "{#Redist}"; DestName: "vc_redist.x64.exe"; Flags: dontcopy
Source: "{#Payload}\*"; Excludes: "postgresql\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; The broad exclude above also matches the nested SQLAlchemy dialect directory;
; copy it explicitly so dialects\postgresql\__init__.py and base.py are installed.
Source: "{#Payload}\packages\sqlalchemy\dialects\postgresql\*"; DestDir: "{app}\packages\sqlalchemy\dialects\postgresql"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Payload}\postgresql\*"; DestDir: "{commonappdata}\{#ProductRoot}\runtime\postgresql"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "provision.ps1"; Flags: dontcopy
Source: "provision.ps1"; DestDir: "{commonappdata}\{#ProductRoot}\runtime"; Flags: ignoreversion

[UninstallDelete]
Type: files; Name: "{app}\windows-product.txt"

[Icons]
Name: "{group}\EDR"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launcher.ps1"" start"; WorkingDir: "{app}"
Name: "{commondesktop}\EDR"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launcher.ps1"" start"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Stop EDR"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launcher.ps1"" stop"; WorkingDir: "{app}"
Name: "{group}\Windows guide"; Filename: "{app}\Windows-guide.md"

[Tasks]
Name: desktopicon; Description: "Create EDR desktop shortcut"

[Code]
var
  OwnsMaintenance: Boolean;

function HasRequiredCrt(): Boolean;
var
  Installed, Major, Minor: Cardinal;
  Key: String;
begin
  Key := 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  Result := RegQueryDWordValue(HKLM64, Key, 'Installed', Installed) and
    RegQueryDWordValue(HKLM64, Key, 'Major', Major) and
    RegQueryDWordValue(HKLM64, Key, 'Minor', Minor);
  if Result then Result := (Installed = 1) and
    ((Major > 14) or ((Major = 14) and (Minor >= 44)));
end;

function PrepareCrt(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Result := '';
  if HasRequiredCrt() then begin
    Log('EDR CRT: sufficient installed x64 runtime; skipping prerequisite');
    exit;
  end;
  Log('EDR CRT: installing embedded Microsoft x64 prerequisite before provisioning');
  ExtractTemporaryFile('vc_redist.x64.exe');
  if not Exec(ExpandConstant('{tmp}\vc_redist.x64.exe'),
    '/install /quiet /norestart /log "' + ExpandConstant('{tmp}\EDR-vcredist.log') + '"',
    ExpandConstant('{tmp}'), SW_HIDE, ewWaitUntilTerminated, Code) then begin
    Result := 'EDR: cannot start embedded Microsoft Visual C++ x64 prerequisite. EDR installation stopped.';
    exit;
  end;
  Log('EDR CRT exit code: ' + IntToStr(Code));
  if (Code = 3010) or (Code = 1641) then begin
    NeedsRestart := True;
    Result := 'EDR: Microsoft Visual C++ requires a Windows restart. Restart Windows and run EDR setup again; EDR has not been installed.';
  end else if Code <> 0 then
    Result := 'EDR: Microsoft Visual C++ prerequisite failed (code ' + IntToStr(Code) + '). EDR installation stopped. See EDR-vcredist.log in setup temporary directory.'
  else if not HasRequiredCrt() then
    Result := 'EDR: Microsoft Visual C++ x64 runtime validation failed after installation. EDR installation stopped.';
end;

function RunControl(Script, Action: String): Boolean;
var
  ResultCode: Integer;
  Diagnostic: AnsiString;
  DiagnosticPath: String;
begin
  DiagnosticPath := ExpandConstant('{tmp}\EDR-provision-error.txt');
  DeleteFile(DiagnosticPath);
  Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -ExecutionPolicy Bypass -File "' + Script + '" -Action ' + Action + ' -Product {#ProductRoot} -DiagnosticPath "' + DiagnosticPath + '"',
    ExpandConstant('{tmp}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
  if not Result then begin
    if LoadStringFromFile(DiagnosticPath, Diagnostic) then Log(String(Diagnostic));
    Log('EDR provision process exit: ' + IntToStr(ResultCode));
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := PrepareCrt(NeedsRestart);
  if Result <> '' then begin
    Log(Result);
    exit;
  end;
  ExtractTemporaryFile('provision.ps1');
  if not RunControl(ExpandConstant('{tmp}\provision.ps1'), 'prepare') then
    Result := 'EDR could not validate the interactive account, protected ProgramData or stop safely. Data preserved; see EDR provision phase and HRESULT in setup log.'
  else OwnsMaintenance := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if not SaveStringToFile(ExpandConstant('{app}\windows-product.txt'), '{#ProductRoot}', False) then
      RaiseException('Cannot save EDR product identity');
end;

function InitializeUninstall(): Boolean;
begin
  Result := RunControl(ExpandConstant('{commonappdata}\{#ProductRoot}\runtime\provision.ps1'), 'stop');
  OwnsMaintenance := Result;
  if not Result then
    MsgBox('EDR could not stop safely. Uninstall cancelled; data preserved.', mbError, MB_OK);
end;

procedure DeinitializeSetup();
begin
  if OwnsMaintenance then DeleteFile(ExpandConstant('{commonappdata}\{#ProductRoot}\maintenance'));
end;

procedure DeinitializeUninstall();
begin
  if OwnsMaintenance then DeleteFile(ExpandConstant('{commonappdata}\{#ProductRoot}\maintenance'));
end;

// UninstallDelete covers only the generated product marker, never persistent state.
