[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory)]
    [string]$Identity,

    [string]$DisabledOrganizationalUnit
)

$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory -ErrorAction Stop

$user = Get-ADUser -Identity $Identity -Properties Enabled, Description -ErrorAction Stop
if (-not $user.Enabled) {
    Write-Warning "Account is already disabled: $($user.SamAccountName)"
    return
}

if ($DisabledOrganizationalUnit) {
    $targetOu = Get-ADOrganizationalUnit -Identity $DisabledOrganizationalUnit -ErrorAction Stop
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$newDescription = "Disabled by IT support on $timestamp. Previous description: $($user.Description)"

if ($PSCmdlet.ShouldProcess($user.SamAccountName, "Disable Active Directory account")) {
    Disable-ADAccount -Identity $user.DistinguishedName
    Set-ADUser -Identity $user.DistinguishedName -Description $newDescription

    if ($DisabledOrganizationalUnit) {
        Move-ADObject -Identity $user.DistinguishedName -TargetPath $targetOu.DistinguishedName
    }

    Write-Host "Account disabled: $($user.SamAccountName)" -ForegroundColor Green
}
