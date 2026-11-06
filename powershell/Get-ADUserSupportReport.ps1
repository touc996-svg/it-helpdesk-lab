[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Identity,
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory -ErrorAction Stop

$user = Get-ADUser -Identity $Identity -Properties `
    Enabled, LockedOut, LastLogonDate, PasswordLastSet, `
    PasswordExpired, PasswordNeverExpires, Department, Title, MemberOf

$groups = @(
    foreach ($dn in $user.MemberOf) {
        Get-ADGroup -Identity $dn | Select-Object -ExpandProperty Name
    }
)

$report = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    username = $user.SamAccountName
    display_name = $user.Name
    enabled = [bool]$user.Enabled
    locked_out = [bool]$user.LockedOut
    last_logon = $user.LastLogonDate
    password_last_set = $user.PasswordLastSet
    password_expired = [bool]$user.PasswordExpired
    password_never_expires = [bool]$user.PasswordNeverExpires
    department = $user.Department
    title = $user.Title
    groups = $groups
}

$json = $report | ConvertTo-Json -Depth 5
$json

if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $json | Set-Content -Path $OutputPath -Encoding UTF8
}
