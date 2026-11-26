# Upgrades a real RemedyPDF 1.5.0 install with the new Setup, run the way 1.x's updater runs it.
# For a throwaway machine only: it installs over, and then removes, whatever RemedyPDF is there.
#   pwsh pack/upgrade_from_1x.ps1 -Old <1.5.0 setup> -New <2.x setup> -Version 2.0.0
param([Parameter(Mandatory)][string]$Old, [Parameter(Mandatory)][string]$New, [Parameter(Mandatory)][string]$Version)
$ErrorActionPreference = 'Stop'
if (-not $env:CI) { throw 'Only for a throwaway machine: set CI=1 to run it.' }
$flags = '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/CURRENTUSER'
$dir = Join-Path $env:LOCALAPPDATA 'Programs\RemedyPDF'
$exe = Join-Path $dir 'RemedyPDF.exe'

function Assert($ok, $what) { if (-not $ok) { throw "FAILED: $what" }; "ok   $what" }
function Get-Ours { @(Get-Process RemedyPDF -ErrorAction SilentlyContinue | Where-Object Path -eq $exe) }
function Get-Entries {
    @(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
        Where-Object { $_.PSObject.Properties['DisplayName'] -and $_.DisplayName -like 'RemedyPDF*' })
}
function Invoke-Setup($setup) {
    $p = Start-Process $setup -ArgumentList $flags -PassThru
    if (-not $p.WaitForExit(240000)) { throw "$setup did not finish" }
    if ($p.ExitCode -ne 0) { throw "$setup exited $($p.ExitCode)" }
}

Invoke-Setup $Old
Start-Sleep 5
Assert (Test-Path $exe) '1.5.0 installed'
Assert (Test-Path (Join-Path $dir '_internal')) '1.5.0 has its Python files'
Get-Ours | Stop-Process -Force

# 1.x downloads Setup, starts it with these flags and quits.
Invoke-Setup $New
Start-Sleep 10
Assert (Test-Path $exe) 'the program is in the same folder'
Assert ((Get-Item $exe).VersionInfo.ProductVersion.Trim().StartsWith($Version)) "the program is $Version"
Assert (Test-Path (Join-Path $dir 'pdfium.dll')) 'PDFium is beside it'
Assert (-not (Test-Path (Join-Path $dir '_internal'))) 'the old Python files are gone'
Assert (-not (Test-Path (Join-Path $dir 'resources'))) 'the old resources are gone'
$entries = Get-Entries
Assert ($entries.Count -eq 1) "one entry in Installed apps (found $($entries.Count))"
Assert ($entries[0].DisplayVersion -eq $Version) "it says $Version"
$running = Get-Ours
Assert ($running.Count -eq 1) 'the new app was reopened'
Start-Sleep 10
Assert ((Get-Ours).Count -eq 1) 'and stays running'
Get-Ours | Stop-Process -Force
Start-Sleep 2
$remove = $entries[0].UninstallString.Trim('"')
Start-Process $remove -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait
Start-Sleep 5
Assert (-not (Test-Path $exe)) 'uninstall removes it'
