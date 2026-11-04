# Runs only elevated from Inno's private extraction directory or protected runtime.
# Never execute installed application code with the installer's elevated token.
[CmdletBinding()]
param([ValidateSet('prepare','stop')][string]$Action = 'prepare',
      [ValidateSet('EDR','EDR-Smoke')][string]$Product = 'EDR',
      [string]$DiagnosticPath)
$ErrorActionPreference = 'Stop'
$createdMaintenance = $false
$phase = 'interactive-identity'
try {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class EdrShellIdentity {
    [DllImport("user32.dll")] static extern IntPtr GetShellWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr w, out uint pid);
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool OpenProcessToken(IntPtr p, uint access, out IntPtr token);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("shell32.dll")] static extern int SHGetKnownFolderPath(ref Guid folder, uint flags, IntPtr token, out IntPtr path);
    public static string[] Read() {
        var window = GetShellWindow();
        if (window == IntPtr.Zero) throw new Exception("No interactive shell; installation refused");
        uint pid;
        GetWindowThreadProcessId(window, out pid);
        if (System.Diagnostics.Process.GetProcessById((int)pid).SessionId != System.Diagnostics.Process.GetCurrentProcess().SessionId)
            throw new Exception("Interactive session mismatch");
        IntPtr process = OpenProcess(0x1000, false, pid);
        if (process == IntPtr.Zero) throw new System.ComponentModel.Win32Exception();
        try {
            IntPtr token;
            if (!OpenProcessToken(process, 0xA, out token)) throw new System.ComponentModel.Win32Exception();
            try {
                using (var identity = new WindowsIdentity(token)) {
                    Guid folder = new Guid("F1B32785-6FBA-4FCF-9D55-7B8E7F157091");
                    IntPtr path;
                    Marshal.ThrowExceptionForHR(SHGetKnownFolderPath(ref folder, 0, token, out path));
                    try { return new string[] {identity.User.Value, Marshal.PtrToStringUni(path)}; }
                    finally { Marshal.FreeCoTaskMem(path); }
                }
            } finally { CloseHandle(token); }
        } finally { CloseHandle(process); }
    }
}
'@
    $identity = [EdrShellIdentity]::Read()
    $ownerSid = $identity[0]
    $legacy = Join-Path $identity[1] 'EDR/data'
    $root = Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) $Product
    if ($root -match '[^\x00-\x7F]') { throw 'ProgramData must have an ASCII path' }
    $systemSid = 'S-1-5-18'
    $adminSid = 'S-1-5-32-544'
    function Assert-NoLink([string]$Path) {
        for ($part = $Path; $part; $part = [IO.Path]::GetDirectoryName($part)) {
            if ((Test-Path -LiteralPath $part) -and ((Get-Item -Force -LiteralPath $part).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw "Reparse point refused: $part"
            }
        }
    }
    function New-PrivateDirectory([string]$Path, [bool]$Writable) {
        Assert-NoLink $Path
        $acl = New-Object Security.AccessControl.DirectorySecurity
        $acl.SetAccessRuleProtection($true, $false)
        # Alternate-admin elevation cannot assign an unrelated user as owner
        # without SeRestorePrivilege. Ownership grants no data read/write ACE.
        $directoryOwner = $adminSid
        $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier($directoryOwner)))
        $principals = if ($Writable) { @($systemSid, $ownerSid) } else { @($systemSid, $adminSid, $ownerSid) }
        foreach ($sid in $principals) {
            $rights = if (($sid -eq $ownerSid) -and !$Writable) { 'ReadAndExecute' } else { 'FullControl' }
            $rule = New-Object Security.AccessControl.FileSystemAccessRule(
                (New-Object Security.Principal.SecurityIdentifier($sid)), $rights, 'ContainerInherit,ObjectInherit', 'None', 'Allow')
            $acl.AddAccessRule($rule)
        }
        if (!(Test-Path -LiteralPath $Path)) { [IO.Directory]::CreateDirectory($Path, $acl) | Out-Null }
        else { throw "Refusing to adopt an existing unverified directory: $Path" }
    }
    function Assert-ProtectedRoot {
        Assert-NoLink $root
        $acl = Get-Acl -LiteralPath $root
        if (!$acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @($adminSid,$systemSid)) {
            throw 'ProgramData root is not installer-owned and protected'
        }
        foreach ($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
            if ($rule.AccessControlType -ne 'Allow') { throw 'Unexpected root ACL' }
            if ($rule.IdentityReference.Value -in @($adminSid,$systemSid)) { continue }
            if ($rule.IdentityReference.Value -ne $ownerSid -or ($rule.FileSystemRights -band 0xD0156)) {
                throw 'Unexpected writable principal in ProgramData root ACL'
            }
        }
    }
    function Assert-ExactEmptyInstallerDirectory([string]$Path, [bool]$AllowRuntime) {
        Assert-NoLink $Path
        if (!(Test-Path -LiteralPath $Path -PathType Container)) { throw 'Partial bootstrap is not a directory' }
        $actual = Get-Acl -LiteralPath $Path
        $expected = New-Object Security.AccessControl.DirectorySecurity
        $expected.SetAccessRuleProtection($true, $false)
        foreach ($sid in @($systemSid,$adminSid,$ownerSid)) {
            $rights = if ($sid -eq $ownerSid) { 'ReadAndExecute' } else { 'FullControl' }
            $expected.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
                (New-Object Security.Principal.SecurityIdentifier($sid)), $rights, 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
        }
        $section = [Security.AccessControl.AccessControlSections]::Access
        if ($actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $adminSid -or
            $actual.GetSecurityDescriptorSddlForm($section) -cne $expected.GetSecurityDescriptorSddlForm($section)) {
            throw 'Partial bootstrap owner/DACL mismatch; preserved without changes'
        }
        # Enumerate only installer-owned metadata; never enter state or unknown children.
        foreach ($child in @(Get-ChildItem -Force -LiteralPath $Path)) {
            if (!$AllowRuntime -or $child.Name -cne 'runtime') { throw 'Nonempty or unknown partial bootstrap; preserved without changes' }
            Assert-ExactEmptyInstallerDirectory $child.FullName $false
        }
    }
    $phase = 'validate-bootstrap'
    Assert-NoLink $root
    $initialize = $false
    if (Test-Path -LiteralPath $root) {
        Assert-ProtectedRoot
        $recordPath = Join-Path $root 'owner.json'
        Assert-NoLink $recordPath
        if (Test-Path -LiteralPath $recordPath) {
            $record = Get-Content -Raw -LiteralPath $recordPath | ConvertFrom-Json
            if ($record.sid -ne $ownerSid -or $record.legacy -ne $legacy) { throw 'Different intended EDR account; operation refused' }
        } else {
            Assert-ExactEmptyInstallerDirectory $root $true
            if ($Action -eq 'stop') { exit 0 }
            $initialize = $true
        }
    } elseif ($Action -eq 'stop') { exit 0 }
    else {
        $phase = 'create-root'
        New-PrivateDirectory $root $false
        Assert-ProtectedRoot
        $initialize = $true
    }
    if ($initialize) {
        $phase = 'create-runtime'
        if (!(Test-Path -LiteralPath (Join-Path $root 'runtime'))) {
            New-PrivateDirectory (Join-Path $root 'runtime') $false
        }
        $phase = 'create-state'
        New-PrivateDirectory (Join-Path $root 'state') $true
        $phase = 'create-control'
        New-PrivateDirectory (Join-Path $root 'control') $false
        [IO.File]::WriteAllText((Join-Path $root 'control/gate'), '')
        $phase = 'write-owner-record'
        @{ format=1; sid=$ownerSid; legacy=$legacy } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'owner.json') -Encoding UTF8
    }
    $phase = 'maintenance-gate'
    # Refuse pre-gate installations rather than inspect/change user ACLs or
    # guess whether an alternate root is running. No user data is read here.
    $gate = Join-Path $root 'control/gate'
    Assert-NoLink $gate
    if (!(Test-Path -LiteralPath $gate)) { throw 'Pre-gate installation: maintenance refused; preserve data and use a controlled migration' }
    # Runtime holds shared READ access for its entire command. Exclusive open
    # fails immediately for any root/start/backup/restore; retry after stopping.
    $gateStream = [IO.File]::Open($gate, 'Open', 'ReadWrite', 'None')
    $maintenance = Join-Path $root 'maintenance'
    $maintenanceStream = [IO.File]::Open($maintenance, 'CreateNew', 'Write', 'None')
    $maintenanceStream.Dispose()
    $createdMaintenance = $true
    $gateStream.Dispose()
    $gateStream = $null
    # Legacy must be stopped by its owning account before upgrade. Never execute
    # legacy Python or reset legacy ACLs under an alternate administrator token.
    if ((Test-Path -LiteralPath $legacy) -and (Test-Path -LiteralPath (Join-Path $legacy 'running.json'))) {
        throw 'Stop the legacy EDR under its original account before installing'
    }
    exit 0
} catch {
    if ($gateStream) { $gateStream.Dispose() }
    if ($createdMaintenance) { [IO.File]::Delete($maintenance) }
    # Emit only phase/type/HResult: exception text may contain user paths/content.
    $diagnostic = 'EDR provision failed: phase={0}; type={1}; HRESULT=0x{2:X8}. Data preserved; retain setup log for support.' -f $phase, $_.Exception.GetType().Name, $_.Exception.HResult
    [Console]::Error.WriteLine($diagnostic)
    if ($DiagnosticPath) { [IO.File]::WriteAllText($DiagnosticPath, $diagnostic) }
    exit 1
}
