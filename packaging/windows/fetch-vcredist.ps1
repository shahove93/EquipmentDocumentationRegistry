param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$url = 'https://aka.ms/vc14/vc_redist.x64.exe'
if (Test-Path -LiteralPath $Destination) { throw 'Redistributable destination must be new' }
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $Destination
$signature = Get-AuthenticodeSignature -LiteralPath $Destination
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|, )O=Microsoft Corporation(,|$)') {
    throw 'Redistributable must have a valid Microsoft Corporation Authenticode signature'
}
$info = [Diagnostics.FileVersionInfo]::GetVersionInfo($Destination)
# The Burn bootstrapper PE itself can be x86: its signed product metadata
# identifies the target runtime architecture, rather than the bootstrapper CPU.
if ($info.FileDescription -notmatch '\(x64\)' -or $info.ProductName -notmatch 'Microsoft Visual C\+\+') {
    throw 'Expected Microsoft Visual C++ x64 redistributable product metadata'
}
$version = [version]('{0}.{1}.{2}.{3}' -f $info.FileMajorPart,$info.FileMinorPart,$info.FileBuildPart,$info.FilePrivatePart)
if ($version.Major -ne 14 -or $version -lt [version]'14.44.0.0') { throw "Unsupported runtime version: $version" }
@{ source=$url; version=$version.ToString(); sha256=(Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash;
   architecture='x64'; minimumVersion='14.44.0.0'; signer=$signature.SignerCertificate.Subject;
   signatureStatus=$signature.Status.ToString(); fileDescription=$info.FileDescription }
