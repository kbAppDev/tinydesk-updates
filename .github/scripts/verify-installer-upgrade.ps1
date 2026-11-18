# Runs on the disposable Windows release runner before publication.
$ErrorActionPreference = 'Stop'
$nextVersion = (Get-Content -LiteralPath release-request.txt -Raw).Trim()
$previousVersion = '2.0.1'
if ($nextVersion -ne '2.1.0') {
    Write-Host "The 2.0.1 to 2.1.0 settings migration check does not apply to $nextVersion."
    exit 0
}

$checkRoot = Join-Path $env:RUNNER_TEMP 'Flare installer upgrade'
$installDirectory = Join-Path $checkRoot 'Image Compressor'
$installedExe = Join-Path $installDirectory 'FlareImageCompressor.exe'
$previousName = "Flare-Image-Compressor-Setup-$previousVersion.exe"
$nextName = "Flare-Image-Compressor-Setup-$nextVersion.exe"
New-Item -ItemType Directory -Path $checkRoot -Force | Out-Null

gh release download "v$previousVersion" --repo kbAppDev/tinydesk-updates --pattern $previousName --pattern SHA256SUMS.txt --dir $checkRoot
if ($LASTEXITCODE -ne 0) { throw 'Could not download the previous official installer and checksum.' }
$previousInstaller = Join-Path $checkRoot $previousName
$sumPattern = '^([0-9a-fA-F]{64})\s+\*?' + [regex]::Escape($previousName) + '$'
$sumLines = @(Get-Content -LiteralPath (Join-Path $checkRoot 'SHA256SUMS.txt') | Select-String -Pattern $sumPattern)
if ($sumLines.Count -ne 1) { throw "Expected one checksum for $previousName." }
$expectedHash = $sumLines[0].Matches[0].Groups[1].Value
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $previousInstaller).Hash -ne $expectedHash) {
    throw "Checksum verification failed for $previousName."
}

function Install-AndVerify([string] $installer, [string] $expectedVersion) {
    # Both installers mark their post-install launch skipifsilent.
    $arguments = @('/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', ('/DIR="{0}"' -f $installDirectory))
    $setup = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
    if ($setup.ExitCode -ne 0) { throw "Installer $expectedVersion exited with $($setup.ExitCode)." }
    $versionInfo = (Get-Item -LiteralPath $installedExe).VersionInfo
    if ($versionInfo.ProductVersion -ne $expectedVersion -or $versionInfo.FileVersion -ne "$expectedVersion.0") {
        throw "Expected installed version $expectedVersion. Found $($versionInfo.ProductVersion) / $($versionInfo.FileVersion)."
    }
}

Install-AndVerify $previousInstaller $previousVersion
$preferences = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Flare Tools\Image Compressor'
New-Item -ItemType Directory -Path $preferences -Force | Out-Null
$settingsPath = Join-Path $preferences 'settings.json'
$seed = @{ preset = 'Smallest'; format = 'WebP'; resize = '1280 px'; output = (Join-Path $checkRoot 'Saved copies') }
$seed | ConvertTo-Json | Set-Content -LiteralPath $settingsPath -Encoding utf8NoBOM
$settingsHash = (Get-FileHash -LiteralPath $settingsPath).Hash

Install-AndVerify (Resolve-Path -LiteralPath "release/$nextName").Path $nextVersion
if ((Get-FileHash -LiteralPath $settingsPath).Hash -ne $settingsHash) { throw 'Upgrade changed the existing settings.' }
$report = Join-Path $checkRoot 'installed-check.json'
$check = Start-Process -FilePath $installedExe -ArgumentList '--self-check', ('"{0}"' -f $report) -WindowStyle Hidden -PassThru -Wait
if ($check.ExitCode -ne 0) { throw "Installed app self-check exited with $($check.ExitCode)." }
$result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if ($result.result -ne 'passed' -or $result.version -ne $nextVersion -or -not $result.preset_export) {
    throw 'Installed app failed its preset export self-check.'
}
Write-Host "Verified in-place upgrade from $previousVersion to $nextVersion, settings retention and installed preset export."
