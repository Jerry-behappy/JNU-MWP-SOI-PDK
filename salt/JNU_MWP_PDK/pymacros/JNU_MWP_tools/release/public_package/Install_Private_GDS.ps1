# 创建者: Junyi Zhang
# 时间: 2026-09
# 用接收者自己的 GitHub 授权取得白盒 GDS；数据存放在 Salt 更新范围之外。
param([string]$Source, [string]$KLayoutHome)
$ErrorActionPreference = 'Stop'
if (-not $KLayoutHome) { $KLayoutHome = $env:KLAYOUT_HOME }
if (-not $KLayoutHome) { $KLayoutHome = Join-Path $env:USERPROFILE 'KLayout' }
$homePath = [IO.Path]::GetFullPath($KLayoutHome)
$dataRoot = Join-Path $homePath 'jnu_private'
$target = Join-Path $dataRoot 'JNU_MWP_gds'
$id = [Guid]::NewGuid().ToString('N')
$stage = Join-Path $dataRoot ('.staging-' + $id)
$backup = Join-Path $dataRoot ('JNU_MWP_gds.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $id)
$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$download = Join-Path $tempBase ('jnu-private-' + $id)
$lock = $null
$lockPath = Join-Path $dataRoot '.install.lock'
$backedUp = $false

# 所有移动和清理都限制在明确的私有数据目录和本次临时目录内。
foreach ($path in @($target, $stage, $backup, $lockPath)) {
    if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($path)) -ne $dataRoot) {
        throw 'Invalid private data destination.'
    }
}
try {
    [void][IO.Directory]::CreateDirectory($dataRoot)
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    if (-not $Source) {
        $gh = Get-Command gh -ErrorAction SilentlyContinue
        if (-not $gh) {
            throw 'Install GitHub CLI and Git, run gh auth login, or pass -Source with an authorized, extracted JNU_MWP_gds folder.'
        }
        & $gh.Source auth status --hostname github.com 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Run gh auth login first, using your own authorized GitHub account.' }
        & $gh.Source repo clone Jerry-behappy/JNU-MWP-SOI-Library $download -- --depth 1 --branch main
        if ($LASTEXITCODE -ne 0) { throw 'Private repository download failed. Ask the owner for access; existing GDS was not changed.' }
        $Source = Join-Path $download 'JNU_MWP_gds'
    }
    $Source = (Resolve-Path -LiteralPath $Source).Path
    if ([IO.Path]::GetFileName($Source) -ne 'JNU_MWP_gds' -and
        (Test-Path -LiteralPath (Join-Path $Source 'JNU_MWP_gds'))) {
        $Source = Join-Path $Source 'JNU_MWP_gds'
    }
    $files = @(Get-ChildItem -LiteralPath $Source -File -Filter '*.gds')
    if ($files.Count -eq 0) { throw 'No GDS files found. Pass the extracted JNU_MWP_gds directory.' }
    [void][IO.Directory]::CreateDirectory($stage)
    foreach ($file in $files) {
        if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked GDS files are not supported.' }
        $destination = Join-Path $stage $file.Name
        Copy-Item -LiteralPath $file.FullName -Destination $destination
        # 先检查基本 GDS 头尾，拒绝空文件或误下载的 HTML，再替换现有数据。
        $stream = [IO.File]::OpenRead($destination)
        try {
            if ($stream.Length -lt 10) { throw "Invalid GDS: $($file.Name)" }
            $head = New-Object byte[] 4
            $tail = New-Object byte[] 4
            [void]$stream.Read($head, 0, 4)
            [void]$stream.Seek(-4, [IO.SeekOrigin]::End)
            [void]$stream.Read($tail, 0, 4)
            if (($head -join ',') -ne '0,6,0,2' -or ($tail -join ',') -ne '0,4,4,0') {
                throw "Invalid GDS header or ENDLIB: $($file.Name)"
            }
        } finally { $stream.Dispose() }
    }
    if (Test-Path -LiteralPath $target) {
        [IO.Directory]::Move($target, $backup)
        $backedUp = $true
    }
    try { [IO.Directory]::Move($stage, $target) }
    catch {
        if ($backedUp -and -not (Test-Path -LiteralPath $target)) {
            [IO.Directory]::Move($backup, $target)
        }
        throw
    }
    Write-Output "PRIVATE_GDS_INSTALLED: $($files.Count) files in $target"
    if ($backedUp) { Write-Output "Previous GDS preserved: $backup" }
    Write-Output 'Restart KLayout or use JNU_MWP_PDK > Reload JNU PDK.'
    Write-Output 'Run this same script again to update private GDS separately from public code.'
} finally {
    if ($lock) {
        $lock.Dispose()
        Remove-Item -LiteralPath $lockPath -Force
    }
    if ((Test-Path -LiteralPath $stage) -and
        [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($stage)) -eq $dataRoot) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    if ((Test-Path -LiteralPath $download) -and
        [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($download)) -eq $tempBase.TrimEnd('\') -and
        [IO.Path]::GetFileName($download) -eq ('jnu-private-' + $id)) {
        Remove-Item -LiteralPath $download -Recurse -Force
    }
}
