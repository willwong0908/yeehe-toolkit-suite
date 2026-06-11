param(
    [Parameter(Mandatory = $true)]
    [string]$Token
)

$ErrorActionPreference = "Stop"

$name = "YEEHE_WORKER_ADMIN_TOKEN"
$value = $Token.Trim()

if ([string]::IsNullOrWhiteSpace($value)) {
    throw "Token cannot be empty."
}

[System.Environment]::SetEnvironmentVariable($name, $value, "User")
Set-Item -Path ("Env:" + $name) -Value $value

Write-Host "$name has been saved to the current user's environment variables." -ForegroundColor Green
Write-Host "It is available in this window now and will also be available in new terminal windows." -ForegroundColor Green
