# PowerShell install script for Windows

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MSIM Installer" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Check for uv

uv=Get−Commanduv−ErrorActionSilentlyContinueif(−notuv = Get-Command uv -ErrorAction SilentlyContinue
if (-not uv=Get−Commanduv−ErrorActionSilentlyContinueif(−notuv) {
Write-Host "uv not found. Installing..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "[https://astral.sh/uv/install.ps1](https://astral.sh/uv/install.ps1)" -OutFile "uv-install.ps1"
.\uv-install.ps1
Remove-Item "uv-install.ps1"

# Reload PATH

$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
Write-Host "Failed to install uv. Please install manually:" -ForegroundColor Red
Write-Host "  powershell -c 'irm [https://astral.sh/uv/install.ps1](https://astral.sh/uv/install.ps1) | iex'"
exit 1
}
}

Write-Host "Installing Python dependencies..." -ForegroundColor Green
uv sync

Write-Host "Running interactive setup..." -ForegroundColor Green
python MSIM.py

Write-Host "Installation complete." -ForegroundColor Green
Write-Host "You can now run:"
Write-Host "  python MSIM.py menu      - interactive menu"
Write-Host "  python MSIM.py start     - start server in background"
Write-Host "  python MSIM.py serve     - start server in foreground"