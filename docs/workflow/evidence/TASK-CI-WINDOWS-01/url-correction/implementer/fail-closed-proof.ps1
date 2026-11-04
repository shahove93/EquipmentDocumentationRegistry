# Fail-closed harness: reproduces the workflow's Inno installer hash/signature
# verification logic. Never installs or executes the target file.
param(
    [Parameter(Mandatory = $true)][string]$Setup,
    [Parameter(Mandatory = $true)][ValidateSet('correct', 'wrong-hash')][string]$Mode
)

$ErrorActionPreference = 'Stop'

$expectedHash = if ($Mode -eq 'wrong-hash') {
    '0000000000000000000000000000000000000000000000000000000000000000'
} else {
    '9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732'
}

Write-Output "mode: $Mode"
Write-Output "setup: $Setup"
$actualHash = (Get-FileHash -LiteralPath $Setup -Algorithm SHA256).Hash
Write-Output "actual SHA256: $actualHash"
Write-Output "expected SHA256: $expectedHash"
if ($actualHash -ne $expectedHash) {
    throw "SHA-256 mismatch for $($Setup): expected $expectedHash, got $actualHash"
}

$signature = Get-AuthenticodeSignature -LiteralPath $Setup
Write-Output "Authenticode status: $($signature.Status)"
Write-Output "Authenticode signer: $($signature.SignerCertificate.Subject)"
if ($signature.Status -ne 'Valid') {
    throw "Inno Setup installer signature status is not Valid: $($signature.Status)"
}
if ($signature.SignerCertificate.Subject -notmatch 'CN=Pyrsys B\.V\.') {
    throw "Inno Setup installer signer is not Pyrsys B.V.: $($signature.SignerCertificate.Subject)"
}

Write-Output 'VERIFICATION_OK'
