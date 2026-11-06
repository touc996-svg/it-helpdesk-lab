[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [Parameter(Mandatory)]
    [string]$Identity,

    [Parameter(Mandatory)]
    [ValidateLength(3, 80)]
    [string]$IncidentReference,

    [string]$AuditPath = "$PSScriptRoot/../logs/ad-account-actions.jsonl"
)

$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory -ErrorAction Stop

$user = Get-ADUser -Identity $Identity -Properties LockedOut, Enabled

if (-not $user.Enabled) {
    throw "Account is disabled. Unlock was not attempted."
}

if (-not $user.LockedOut) {
    Write-Host "Account is not locked: $($user.SamAccountName)"
    return
}

if ($PSCmdlet.ShouldProcess($user.SamAccountName, "Unlock account for $IncidentReference")) {
    Unlock-ADAccount -Identity $user.DistinguishedName -ErrorAction Stop

    $verified = Get-ADUser -Identity $user.DistinguishedName -Properties LockedOut
    if ($verified.LockedOut) {
        throw "Account remains locked after the unlock operation."
    }

    $record = [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        action = "unlock_account"
        account = $user.SamAccountName
        incident_reference = $IncidentReference
        operator = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        result = "success"
    }

    $parent = Split-Path -Parent $AuditPath
    if ($parent -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    ($record | ConvertTo-Json -Compress) |
        Add-Content -Path $AuditPath -Encoding UTF8

    Write-Host "Account unlocked and verified: $($user.SamAccountName)"
}
