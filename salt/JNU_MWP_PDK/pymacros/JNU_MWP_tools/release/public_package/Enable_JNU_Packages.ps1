# 创建者: Junyi Zhang
# 时间: 2026-09
# 注册公共索引；保留官方和已有自定义来源，不涉及私有仓库凭据。
param([string]$KLayoutHome, [switch]$SessionOnly)
$ErrorActionPreference = 'Stop'
if (-not $KLayoutHome) { $KLayoutHome = $env:KLAYOUT_HOME }
if (-not $KLayoutHome) { $KLayoutHome = Join-Path $env:USERPROFILE 'KLayout' }
$homePath = [IO.Path]::GetFullPath($KLayoutHome)
[void][IO.Directory]::CreateDirectory($homePath)
$indexPath = Join-Path $homePath 'jnu-package-sources.xml'
$indexUrl = ([Uri]$indexPath).AbsoluteUri
$publicIndex = 'https://raw.githubusercontent.com/Jerry-behappy/JNU-MWP-SOI-PDK/main/packages/repository.xml'
$previous = [Environment]::GetEnvironmentVariable('KLAYOUT_SALT_MINE', 'User')
if ($env:KLAYOUT_SALT_MINE) { $previous = $env:KLAYOUT_SALT_MINE }
$sources = @($publicIndex)
if ($previous -eq $indexUrl -and (Test-Path -LiteralPath $indexPath)) {
    [xml]$old = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8
    $sources += @($old.'salt-mine'.include | ForEach-Object { [string]$_ })
} elseif ($previous) {
    $sources += $previous
}
$index = New-Object Xml.XmlDocument
$root = $index.CreateElement('salt-mine')
[void]$index.AppendChild($root)
foreach ($url in ($sources | Where-Object { $_ -and $_ -ne $indexUrl } | Select-Object -Unique)) {
    $node = $index.CreateElement('include')
    $node.InnerText = $url
    [void]$root.AppendChild($node)
}
if (Test-Path -LiteralPath $indexPath) {
    Copy-Item -LiteralPath $indexPath -Destination ($indexPath + '.bak') -Force
}
$index.Save($indexPath)
if (-not $SessionOnly) {
    [Environment]::SetEnvironmentVariable('KLAYOUT_SALT_MINE', $indexUrl, 'User')
}
$env:KLAYOUT_SALT_MINE = $indexUrl
Write-Output "JNU package sources: $indexUrl"
Write-Output 'Restart KLayout from the Windows Start menu.'
Write-Output 'Tools > Manage Packages > Install New Packages > JNU_MWP_PDK > Apply.'
Write-Output 'Future code updates: Tools > Manage Packages > Update Packages.'
Write-Output 'Private whitebox GDS is NOT included and requires separate authorization.'
