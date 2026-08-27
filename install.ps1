# PowerShell install script for Windows

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MSIM Installer v1.0.1" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Step 1: Check submodule

Write-Host "Step 1: Ensuring submodule is present..." -ForegroundColor Cyan
if (-not (Test-Path "submodules/anythingllm-mcp/pyproject.toml")) {
Write-Host "Submodule not found. Pulling..." -ForegroundColor Yellow
git submodule update --init --recursive
if (-not (Test-Path "submodules/anythingllm-mcp/pyproject.toml")) {
Write-Host "ERROR: Submodule still missing. Please run manually:" -ForegroundColor Red
Write-Host "  git submodule update --init --recursive"
exit 1
}
} else {
Write-Host "Submodule already present." -ForegroundColor Green
}

# Step 2: Check uv

Write-Host "Step 2: Checking uv..." -ForegroundColor Cyan
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

# Step 3: Install Python dependencies

Write-Host "Step 3: Installing Python dependencies..." -ForegroundColor Cyan
uv sync

# Step 4: Validate MSIM.py

Write-Host "Step 4: Validating MSIM.py..." -ForegroundColor Cyan
python -m py_compile MSIM.py
if (LASTEXITCODE -ne 0) {
Write-Host "ERROR: MSIM.py still invalid. Please check manually." -ForegroundColor Red
exit 1
}
}

# Step 5: Run interactive setup

Write-Host "Step 5: Running interactive setup..." -ForegroundColor Cyan
python MSIM.py

Write-Host "Installation complete." -ForegroundColor Green
Write-Host "You can now run:"
Write-Host "  python MSIM.py menu      - interactive menu"
Write-Host "  python MSIM.py start     - start server in background"
Write-Host "  python MSIM.py serve     - start server in foreground"