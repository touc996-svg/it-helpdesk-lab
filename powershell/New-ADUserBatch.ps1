[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory)]
    [ValidateScript({ Test-Path $_ -PathType Leaf })]
    [string]$CsvPath,

    [Parameter(Mandatory)]
    [string]$OrganizationalUnit,

    [Parameter(Mandatory)]
    [securestring]$InitialPassword,

    [switch]$EnableAccounts
)

$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory -ErrorAction Stop

$requiredColumns = @("GivenName", "Surname", "SamAccountName", "UserPrincipalName")
$users = Import-Csv -Path $CsvPath
if (-not $users) {
    throw "The CSV file is empty."
}

$missing = $requiredColumns | Where-Object { $_ -notin $users[0].PSObject.Properties.Name }
if ($missing) {
    throw "CSV is missing required columns: $($missing -join ', ')"
}

$null = Get-ADOrganizationalUnit -Identity $OrganizationalUnit -ErrorAction Stop

foreach ($user in $users) {
    foreach ($field in $requiredColumns) {
        if ([string]::IsNullOrWhiteSpace($user.$field)) {
            throw "A row contains an empty $field value. No further users were processed."
        }
    }

    $existing = Get-ADUser -Filter "SamAccountName -eq '$($user.SamAccountName.Replace("'", "''"))'" -ErrorAction Stop
    if ($existing) {
        Write-Warning "Skipping existing account: $($user.SamAccountName)"
        continue
    }

    $displayName = "$($user.GivenName) $($user.Surname)"
    $parameters = @{
        Name                  = $displayName
        GivenName             = $user.GivenName
        Surname               = $user.Surname
        SamAccountName        = $user.SamAccountName
        UserPrincipalName     = $user.UserPrincipalName
        DisplayName           = $displayName
        Path                  = $OrganizationalUnit
        AccountPassword       = $InitialPassword
        Enabled               = [bool]$EnableAccounts
        ChangePasswordAtLogon = $true
    }

    if ($PSCmdlet.ShouldProcess($user.SamAccountName, "Create Active Directory account")) {
        New-ADUser @parameters
        Write-Host "Created account: $($user.SamAccountName)" -ForegroundColor Green
    }
}
