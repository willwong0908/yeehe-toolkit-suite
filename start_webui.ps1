$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$host.UI.RawUI.WindowTitle = "AI Term Extractor WebUI"

Write-Host "==============================================" -ForegroundColor DarkGray
Write-Host "AI Term Extractor WebUI" -ForegroundColor Cyan
Write-Host ""
Write-Host "URL: http://127.0.0.1:8765" -ForegroundColor Green
Write-Host "State: starting" -ForegroundColor Yellow
Write-Host ""
Write-Host "A browser window will open automatically." -ForegroundColor Gray
Write-Host "Keep this window open while the app is running." -ForegroundColor Gray
Write-Host "Close this window or press Ctrl+C to stop the app." -ForegroundColor Gray
Write-Host "==============================================" -ForegroundColor DarkGray
Write-Host ""

Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765'"

try {
    $packagedExe = Join-Path $PSScriptRoot "program\\AI_Term_Extractor_WebUI.exe"
    if (Test-Path -LiteralPath $packagedExe) {
        & $packagedExe
    }
    else {
        python term_extractor_app\web_app.py
    }
}
finally {
    Write-Host ""
    Write-Host "WebUI stopped." -ForegroundColor Yellow
    Write-Host "Press Enter to close this window..."
    [void](Read-Host)
}
