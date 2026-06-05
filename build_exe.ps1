$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$buildDir = ".\\build_clean"
$distDir = ".\\dist_clean"
$releaseDir = ".\\release_bundle"
$releaseProgramDir = Join-Path $releaseDir "program"

Write-Host "Cleaning previous build artifacts..."
Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $distDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $releaseDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Building WebUI package with PyInstaller..."
pyinstaller ".\\yeehe_toolkit_suite.spec" --noconfirm --clean --workpath $buildDir --distpath $distDir

Write-Host "Copying packaged program into release bundle..."
New-Item -ItemType Directory -Path $releaseProgramDir -Force | Out-Null
Get-ChildItem -Path (Join-Path $distDir "Yeehe_Toolkit_Suite") -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $releaseProgramDir -Recurse -Force
}

Copy-Item -LiteralPath ".\\start_webui.bat" -Destination $releaseDir -Force
Copy-Item -LiteralPath ".\\stop_webui.bat" -Destination $releaseDir -Force

Write-Host "Build completed."
