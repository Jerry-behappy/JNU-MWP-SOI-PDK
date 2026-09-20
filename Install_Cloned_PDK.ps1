# 创建者: Junyi Zhang
# 时间: 2026-09
# 将克隆目录联接到 KLayout；不复制源码，不覆盖现有安装或用户器件。
param([string]$KLayoutHome)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'salt\JNU_MWP_PDK'
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.git')) -or
    -not (Test-Path -LiteralPath (Join-Path $source 'JNU_MWP_PDK.lyt'))) {
    throw 'Run this script from a Git clone of JNU-MWP-SOI-PDK.'
}
$source = (Resolve-Path -LiteralPath $source).Path
if (-not $KLayoutHome) { $KLayoutHome = $env:KLAYOUT_HOME }
if (-not $KLayoutHome) { $KLayoutHome = Join-Path $env:USERPROFILE 'KLayout' }
$homePath = [IO.Path]::GetFullPath($KLayoutHome)
$salt = Join-Path $homePath 'salt'
$target = Join-Path $salt 'JNU_MWP_PDK'
if ($source.StartsWith($salt.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Keep the Git clone outside the KLayout salt directory to avoid duplicate loading.'
}
foreach ($legacy in @('tech\JNU_MWP_PDK', 'pymacros\JNU_MWP_PDK_loader.py', 'pymacros\JNU_MWP_PDK_blackbox_loader.py')) {
    if (Test-Path -LiteralPath (Join-Path $homePath $legacy)) {
        throw "Existing manual loader/technology found: $legacy. Close KLayout and back it up outside KLayout before retrying."
    }
}
$existing = Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
if ($existing) {
    $destinations = @($existing.Target)
    if ($existing.LinkType -eq 'Junction' -and $destinations.Count -eq 1 -and
        [IO.Path]::GetFullPath($destinations[0]).TrimEnd('\') -eq $source.TrimEnd('\')) {
        Write-Output "ALREADY_LINKED: $target -> $source"
        return
    }
    throw "Existing installation preserved: $target. Back it up outside KLayout; this installer never replaces existing data."
}
[void][IO.Directory]::CreateDirectory($salt)
New-Item -ItemType Junction -Path $target -Target $source | Out-Null
Write-Output "CLONE_INSTALLED: $target -> $source"
Write-Output 'Restart KLayout. No separate tech folder or package index is needed.'
Write-Output "Updates: git -C `"$PSScriptRoot`" pull --ff-only origin main"
Write-Output 'Then restart KLayout. Whitebox GDS remains separately authorized.'
