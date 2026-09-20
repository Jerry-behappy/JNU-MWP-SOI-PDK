# 创建者: Junyi Zhang
# 时间: 2026-09
# 为当前 KLayout 进程提供实验室包索引，不改写系统环境变量。
param(
    [string]$KLayoutExe,
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
$releaseRoot = $PSScriptRoot
$packageRoot = Join-Path $releaseRoot 'JNU_MWP_PDK'
$grainPath = Join-Path $packageRoot 'grain.xml'
if (-not (Test-Path -LiteralPath $grainPath)) {
    throw 'Extract the entire laboratory ZIP before running this script.'
}

# 由接收方的解压位置生成 file URL，兼容空格、中文目录与共享目录。
$packageUrl = ([System.Uri]([System.IO.Path]::GetFullPath($packageRoot) + [System.IO.Path]::DirectorySeparatorChar)).AbsoluteUri
[xml]$grain = Get-Content -LiteralPath $grainPath -Raw -Encoding UTF8
$grain.'salt-grain'.url = $packageUrl
$grain.Save($grainPath)

$index = New-Object System.Xml.XmlDocument
$rootNode = $index.CreateElement('salt-mine')
[void]$index.AppendChild($rootNode)
[void]$rootNode.AppendChild($index.ImportNode($grain.DocumentElement, $true))
$indexPath = Join-Path $releaseRoot 'repository.local.xml'
$index.Save($indexPath)
$indexUrl = ([System.Uri]([System.IO.Path]::GetFullPath($indexPath))).AbsoluteUri
Write-Output "Laboratory package index: $indexUrl"
if ($PrepareOnly) { return }

if (-not $KLayoutExe) {
    $candidates = @()
    $command = Get-Command klayout_app.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    foreach ($parent in @($env:ProgramFiles, $env:LOCALAPPDATA, $env:APPDATA, $env:USERPROFILE)) {
        if ($parent) {
            $candidates += Join-Path $parent 'KLayout\klayout_app.exe'
            $candidates += Join-Path $parent 'Programs\KLayout\klayout_app.exe'
        }
    }
    $KLayoutExe = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $KLayoutExe -or -not (Test-Path -LiteralPath $KLayoutExe)) {
    throw 'Run again with -KLayoutExe "D:\KLayout\klayout_app.exe" using your actual installation path.'
}

# 环境变量只由此次启动的子进程继承；通过此入口再次启动即可检查实验室更新。
$previousIndex = $env:KLAYOUT_SALT_MINE
try {
    $env:KLAYOUT_SALT_MINE = $indexUrl
    Start-Process -FilePath $KLayoutExe -ArgumentList '-e'
    Write-Output 'In KLayout: Tools > Manage Packages > Install New Packages > JNU_MWP_PDK > Apply.'
    Write-Output 'After installation, close and restart KLayout. Updates use the same launcher.'
}
finally {
    $env:KLAYOUT_SALT_MINE = $previousIndex
}
