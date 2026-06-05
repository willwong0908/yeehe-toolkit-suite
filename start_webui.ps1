$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$host.UI.RawUI.WindowTitle = "Yeehe Toolkit Suite"

try {
    $packagedExe = Join-Path $PSScriptRoot "program\\Yeehe_Toolkit_Suite.exe"
    if (Test-Path -LiteralPath $packagedExe) {
        & $packagedExe
    }
    else {
        python webui_launcher.py
    }
}
finally {
    exit $LASTEXITCODE
}
