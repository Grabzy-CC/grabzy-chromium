# Installs or updates Grabzy.CC on Windows from Grabzy-CC's releases.
#
#   powershell -ExecutionPolicy Bypass -File grabzy-update.ps1            install or update now
#   powershell -ExecutionPolicy Bypass -File grabzy-update.ps1 -Schedule  also check every day at logon
#   powershell -ExecutionPolicy Bypass -File grabzy-update.ps1 -Unschedule
#
# The installer is checked against the SHA-256 GitHub records for it. It can
# run while the browser is open; the new version starts on the next launch.

param([switch]$Schedule, [switch]$Unschedule)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = 'Grabzy-CC/grabzy-chromium-windows'
$Home_ = Join-Path $env:LOCALAPPDATA 'Grabzy.CC'
$Stamp = Join-Path $Home_ 'installed-release.txt'
$Task = 'Grabzy.CC update'
New-Item -ItemType Directory -Force $Home_ | Out-Null

function Log($msg) {
    $line = '{0:u} {1}' -f (Get-Date), $msg
    Write-Host $line
    Add-Content -Path (Join-Path $Home_ 'update.log') -Value $line
}

if ($Unschedule) {
    Unregister-ScheduledTask -TaskName $Task -Confirm:$false -ErrorAction SilentlyContinue
    Log 'daily check removed'
    exit 0
}

if ($Schedule) {
    $self = Join-Path $Home_ 'grabzy-update.ps1'
    if ($PSCommandPath -ne $self) { Copy-Item $PSCommandPath $self -Force }
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$self`""
    $triggers = @((New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME), (New-ScheduledTaskTrigger -Daily -At 12pm))
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    Register-ScheduledTask -TaskName $Task -Action $action -Trigger $triggers -Settings $settings -Force | Out-Null
    Log 'daily check scheduled'
}

$release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'grabzy-update' }
$current = if (Test-Path $Stamp) { (Get-Content $Stamp -Raw).Trim() } else { '' }
if ($release.tag_name -eq $current) {
    Log "up to date ($current)"
    exit 0
}

$asset = $release.assets | Where-Object { $_.name -like 'grabzy-chromium_*_installer_x64.exe' } | Select-Object -First 1
if (-not $asset) { throw "release $($release.tag_name) has no x64 installer" }
$file = Join-Path $env:TEMP $asset.name
Log "downloading $($asset.name)"
Invoke-WebRequest $asset.browser_download_url -OutFile $file -UseBasicParsing

if ($asset.digest -match '^sha256:(.+)$') {
    $hash = (Get-FileHash $file -Algorithm SHA256).Hash
    if ($hash -ne $Matches[1].ToUpper()) {
        Remove-Item $file
        throw "checksum mismatch for $($asset.name), not installing"
    }
} else {
    Log 'warning: GitHub gave no checksum for this file'
}

Log "installing $($release.tag_name)"
$p = Start-Process $file -Wait -PassThru
Remove-Item $file -ErrorAction SilentlyContinue
if ($p.ExitCode -ne 0) { throw "installer exited with $($p.ExitCode)" }
Set-Content -Path $Stamp -Value $release.tag_name
Log "installed $($release.tag_name)"
