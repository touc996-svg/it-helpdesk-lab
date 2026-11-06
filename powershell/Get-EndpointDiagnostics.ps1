[CmdletBinding()]
param(
    [string]$TargetHost = "www.microsoft.com",
    [int]$TargetPort = 443,
    [string]$OutputPath
)

$ErrorActionPreference = "Continue"

Write-Host "ATLAS IT Help Desk - Endpoint Diagnostics" -ForegroundColor Cyan
Write-Host "Computer: $env:COMPUTERNAME | User: $env:USERNAME"
Write-Host "Timestamp: $(Get-Date -Format o)"

$ipConfig = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
    Where-Object { $_.NetAdapter.Status -eq "Up" }

$dnsResult = $null
try {
    $dnsResult = Resolve-DnsName -Name $TargetHost -ErrorAction Stop |
        Select-Object -First 3 Name, Type, IPAddress
} catch {
    $dnsResult = [pscustomobject]@{ Name = $TargetHost; Error = $_.Exception.Message }
}

$connectivity = Test-NetConnection -ComputerName $TargetHost -Port $TargetPort `
    -WarningAction SilentlyContinue -InformationLevel Quiet

$systemDrive = $env:SystemDrive
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$systemDrive'" `
    -ErrorAction SilentlyContinue

$serviceNames = @("Dnscache", "Dhcp", "Winmgmt", "wuauserv")
$services = foreach ($name in $serviceNames) {
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($service) {
        [pscustomobject]@{ Name = $service.Name; Status = [string]$service.Status; StartType = [string]$service.StartType }
    }
}

$report = [pscustomobject]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    computer_name = $env:COMPUTERNAME
    current_user = "$env:USERDOMAIN\$env:USERNAME"
    operating_system = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption
    active_network_adapters = @($ipConfig | ForEach-Object {
        [pscustomobject]@{
            interface = $_.InterfaceAlias
            ipv4 = @($_.IPv4Address | ForEach-Object IPAddress)
            gateway = @($_.IPv4DefaultGateway | ForEach-Object NextHop)
            dns_servers = @($_.DNSServer.ServerAddresses)
        }
    })
    dns_lookup = @($dnsResult)
    tcp_connectivity = [pscustomobject]@{
        target = $TargetHost
        port = $TargetPort
        reachable = [bool]$connectivity
    }
    system_drive = if ($disk) {
        [pscustomobject]@{
            drive = $disk.DeviceID
            free_gb = [math]::Round($disk.FreeSpace / 1GB, 2)
            size_gb = [math]::Round($disk.Size / 1GB, 2)
        }
    } else { $null }
    core_services = @($services)
}

$report | ConvertTo-Json -Depth 6

if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $report | ConvertTo-Json -Depth 6 | Set-Content -Path $OutputPath -Encoding UTF8
    Write-Host "Report saved to $OutputPath" -ForegroundColor Green
}
