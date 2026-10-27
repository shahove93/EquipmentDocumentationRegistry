# Uses the Windows-provided x64 PowerShell before loading the Python runtime.
[CmdletBinding()]
param(
    [switch]$ProbeOnly,
    [switch]$NoBrowser,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$RuntimeArguments
)
$MicrosoftRuntimeUrl = 'https://learn.microsoft.com/en-US/cpp/windows/latest-supported-vc-redist?view=msvc-160'
function Test-EdrCrt {
    param([string]$Directory = "$env:WINDIR/System32")
    foreach ($name in @('msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll')) {
        $file = Join-Path $Directory $name
        if (!(Test-Path -LiteralPath $file -PathType Leaf)) { return $false }
        $version = (Get-Item -LiteralPath $file).VersionInfo
        if ($version.FileMajorPart -lt 14 -or ($version.FileMajorPart -eq 14 -and $version.FileMinorPart -lt 44)) {
            return $false
        }
    }
    return $true
}
function Get-EdrCrtMessage {
    return "EDR requires Microsoft Visual C++ Runtime x64 14.44 or newer. Install the x64 package from Microsoft's official page (Windows may request administrator approval), then run EDR again: $MicrosoftRuntimeUrl"
}
# Dot-sourcing exposes the probe for synthetic absent-runtime tests.
if ($MyInvocation.InvocationName -eq '.') { return }
if ($ProbeOnly) {
    @{ installed=(Test-EdrCrt); minimum='14.44'; url=$MicrosoftRuntimeUrl } | ConvertTo-Json
    if (Test-EdrCrt) { exit 0 } else { exit 1 }
}
if (!(Test-EdrCrt)) {
    $message = Get-EdrCrtMessage
    [Console]::Error.WriteLine($message)
    if (!$NoBrowser) {
        Start-Process $MicrosoftRuntimeUrl
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($message, 'EDR') | Out-Null
    }
    exit 1
}
if (!$RuntimeArguments) { $RuntimeArguments = @('start') }
if ($RuntimeArguments[0] -eq 'start') {
    # Windows argument quoting is delegated to the command line only for the
    # fixed GUI shortcut. Maintenance arguments use the console path below.
    if ($RuntimeArguments.Count -eq 1) {
        Start-Process -FilePath "$PSScriptRoot/python/pythonw.exe" -ArgumentList '-B -m app.windows_local start' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
        exit 0
    }
}
& "$PSScriptRoot/python/python.exe" -B -m app.windows_local @RuntimeArguments
exit $LASTEXITCODE
