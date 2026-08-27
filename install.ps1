# PowerShell install script for Windows
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MSIM Installer v1.0.3" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Step 1: Ensure submodule is present
Write-Host "Step 1: Ensuring submodule is present..." -ForegroundColor Cyan
if (-not (Test-Path "submodules/anythingllm-mcp/pyproject.toml")) {
    Write-Host "Submodule not found. Pulling..." -ForegroundColor Yellow
    git submodule update --init --recursive
    if (-not (Test-Path "submodules/anythingllm-mcp/pyproject.toml")) {
        Write-Host "Submodule still missing. Trying manual clone..." -ForegroundColor Yellow
        git clone https://github.com/andreperez/anythingllm-mcp.git submodules/anythingllm-mcp
        if (-not (Test-Path "submodules/anythingllm-mcp/pyproject.toml")) {
            Write-Host "ERROR: Submodule still missing. Please run manually:" -ForegroundColor Red
            Write-Host "  git clone https://github.com/andreperez/anythingllm-mcp.git submodules/anythingllm-mcp"
            exit 1
        }
    }
} else {
    Write-Host "Submodule already present." -ForegroundColor Green
}

# Step 2: Check uv
Write-Host "Step 2: Checking uv..." -ForegroundColor Cyan
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "uv not found. Installing..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -OutFile "uv-install.ps1"
    .\uv-install.ps1
    Remove-Item "uv-install.ps1"
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "Failed to install uv. Please install manually:" -ForegroundColor Red
        Write-Host "  powershell -c 'irm https://astral.sh/uv/install.ps1 | iex'"
        exit 1
    }
}

# Step 3: Remove old virtual environment (if present) to avoid conflicts
if (Test-Path ".venv") {
    Write-Host "Removing old virtual environment..." -ForegroundColor Yellow
    rm -r .venv -Force
}

# Step 4: Install Python dependencies
Write-Host "Step 4: Installing Python dependencies..." -ForegroundColor Cyan
uv sync

# Step 5: Install the wrapper manually (using uv pip)
Write-Host "Step 5: Installing AnythingLLM wrapper..." -ForegroundColor Cyan
uv pip install ./submodules/anythingllm-mcp/

# Step 6: Validate MSIM.py
Write-Host "Step 6: Validating MSIM.py..." -ForegroundColor Cyan
python -m py_compile MSIM.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "MSIM.py appears corrupted. Downloading fresh copy..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/giancbaring/msim/main/MSIM.py" -OutFile "MSIM.py"
    python -m py_compile MSIM.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: MSIM.py still invalid. Please check manually." -ForegroundColor Red
        exit 1
    }
}

# Step 7: Run interactive setup
Write-Host "Step 7: Running interactive setup..." -ForegroundColor Cyan
python MSIM.py

Write-Host "Installation complete." -ForegroundColor Green
Write-Host "You can now run:"
Write-Host "  python MSIM.py menu      - interactive menu"
Write-Host "  python MSIM.py start     - start server in background"
Write-Host "  python MSIM.py serve     - start server in foreground"