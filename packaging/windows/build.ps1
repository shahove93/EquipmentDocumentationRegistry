# Build on Windows x64 with Python 3.12, Inno Setup 6.7.3 and a prebuilt React UI.
# Runtime users do not need any of these build tools.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PythonArchive,
    [Parameter(Mandatory=$true)][string]$PostgresArchive,
    [Parameter(Mandatory=$true)][string]$UiDirectory,
    [Parameter(Mandatory=$true)][string]$WorkDirectory,
    [Parameter(Mandatory=$true)][string]$Iscc,
    [switch]$SmokeBuild,
    [string]$BuilderPython = 'python',
    [string]$Version = '0.2.0'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot/../..").Path
$work = [IO.Path]::GetFullPath($WorkDirectory)
if (Test-Path -LiteralPath $work) { throw 'WorkDirectory must be new; build never deletes existing trees' }
if (!(Test-Path -LiteralPath "$UiDirectory/index.html")) { throw 'Build React UI first' }
if (& $BuilderPython -c "import sys; print('.'.join(map(str,sys.version_info[:2])))" | Where-Object { $_ -ne '3.12' }) {
    throw 'Use a Windows x64 CPython 3.12 builder'
}
New-Item -ItemType Directory -Path $work | Out-Null
$payload = New-Item -ItemType Directory -Path "$work/payload"
& $BuilderPython "$PSScriptRoot/prepare.py" $PythonArchive $PostgresArchive $payload
if ($LASTEXITCODE) { throw 'Runtime archive extraction failed' }
if (!(Test-Path -LiteralPath "$payload/postgresql/bin/postgres.exe")) { throw 'Invalid EDB PostgreSQL archive' }
# User-approved prerequisite flow: do not redistribute Microsoft CRT, including
# the two CRT files supplied in the upstream embedded Python archive.
Get-ChildItem -LiteralPath "$payload/python" -File -Filter 'vcruntime*.dll' | Remove-Item
Copy-Item -LiteralPath "$repo/app" -Destination $payload -Recurse
Copy-Item -LiteralPath "$repo/alembic" -Destination $payload -Recurse
Copy-Item -LiteralPath "$repo/alembic.ini" -Destination $payload
Copy-Item -LiteralPath $UiDirectory -Destination "$payload/ui" -Recurse
Copy-Item -LiteralPath "$repo/docs/installation/windows.md" -Destination "$payload/Windows-guide.md"
New-Item -ItemType Directory -Path "$payload/licenses/frontend" -Force | Out-Null
foreach ($library in @('react','react-dom','react-router','react-router-dom','scheduler','cookie','set-cookie-parser')) {
    $license = "$repo/frontend/node_modules/$library/LICENSE"
    if (!(Test-Path -LiteralPath $license)) { $license += '.md' }
    if (!(Test-Path -LiteralPath $license)) { throw "Missing frontend license: $library (run npm ci on build host)" }
    Copy-Item -LiteralPath $license -Destination "$payload/licenses/frontend/$library.txt"
}
# The embedded interpreter searches only its own stdlib and the bundled payload.
Set-Content -LiteralPath "$payload/python/python312._pth" -Encoding ascii -Value @(
    'python312.zip', '.', '..', '../packages', 'import site'
)
New-Item -ItemType Directory -Path "$payload/packages" | Out-Null
$runtimeRequirements = "$work/runtime-requirements.txt"
Copy-Item -LiteralPath "$PSScriptRoot/requirements.lock" -Destination $runtimeRequirements
& $BuilderPython -m venv "$work/build-tools"
if ($LASTEXITCODE) { throw 'Builder virtual environment failed' }
$pipPython = "$work/build-tools/Scripts/python.exe"
# Windows PowerShell 5 treats even successful native stderr notices as errors
# when redirected. Use the actual exit status for the native build step.
try {
    $ErrorActionPreference = 'Continue'
    & $pipPython -m pip --disable-pip-version-check install --only-binary=:all: --target "$payload/packages" -r $runtimeRequirements
    $pipExit = $LASTEXITCODE
} finally { $ErrorActionPreference = 'Stop' }
if ($pipExit) { throw "pip failed: $pipExit" }
& "$payload/python/python.exe" -c "import fastapi,uvicorn,psycopg,alembic; import sys; assert sys.version_info[:3] == (3,12,10)"
if ($LASTEXITCODE) { throw 'Embedded runtime/import check failed' }
$pgVersion = & "$payload/postgresql/bin/postgres.exe" --version
if ($LASTEXITCODE -or $pgVersion -ne 'postgres (PostgreSQL) 18.6') { throw "Wrong PostgreSQL: $pgVersion" }
# Offline maintenance uses the same interpreter as the launcher.
Copy-Item -LiteralPath "$PSScriptRoot/EDR.cmd" -Destination $payload
Copy-Item -LiteralPath "$PSScriptRoot/launcher.ps1" -Destination $payload
$inputs = @($PythonArchive, $PostgresArchive)
$hashes = @{}
foreach ($inputPath in $inputs) { $hashes[[IO.Path]::GetFileName($inputPath)] = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash }
$packages = & $pipPython -m pip --disable-pip-version-check list --path "$payload/packages" --format=json
@{ version=$Version; python='3.12.10'; postgresql='18.6-5'; inno='6.7.3'; archives=$hashes;
   selfContained=$false; smokeBuild=[bool]$SmokeBuild; prerequisite='Microsoft Visual C++ x64 >=14.44 (not bundled)';
   packages=@($packages | ConvertFrom-Json); builtUtc=[DateTime]::UtcNow.ToString('o') } |
    ConvertTo-Json -Depth 10 | Set-Content -LiteralPath "$payload/build-manifest.json" -Encoding utf8
$prototypeArg = @()
if ($SmokeBuild) { $prototypeArg += '/DSmokeBuild' }
& $Iscc @prototypeArg "/DPayload=$payload" "/DOutput=$work" "/DAppVersion=$Version" "$PSScriptRoot/edr.iss"
if ($LASTEXITCODE) { throw "Inno Setup failed: $LASTEXITCODE" }
Write-Output "Installer directory: $work"
