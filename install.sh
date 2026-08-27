#!/bin/bash
set -e

echo "============================================================"
echo "  MSIM Installer v1.0.10"
echo "============================================================"

# Step 1: Ensure submodule is present
echo "Step 1: Ensuring submodule is present..."
if [ ! -f "submodules/anythingllm-mcp/pyproject.toml" ]; then
    echo "Submodule not found. Pulling..."
    if ! git submodule update --init --recursive; then
        echo "ERROR: Submodule pull failed. Check Git access and try again."
        exit 1
    fi
    if [ ! -f "submodules/anythingllm-mcp/pyproject.toml" ]; then
        echo "ERROR: Submodule is still missing."
        exit 1
    fi
else
    echo "Submodule already present."
fi

# Step 2: Install uv if missing
echo "Step 2: Checking uv..."
if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv &> /dev/null; then
        echo "ERROR: Failed to install uv. Please install it manually."
        exit 1
    fi
fi

# Step 3: Install Python 3.12 through uv
echo "Step 3: Installing Python 3.12..."
uv python install 3.12

# Step 4: Remove old virtual environment (if present)
if [ -d ".venv" ]; then
    echo "Removing old virtual environment..."
    rm -rf .venv
fi

# Step 5: Install Python dependencies
echo "Step 4: Installing Python dependencies..."
uv sync --locked --python 3.12

# Step 6: Validate MSIM.py using uv run
echo "Step 5: Validating MSIM.py..."
if ! uv run python -m py_compile MSIM.py; then
    echo "ERROR: MSIM.py failed compilation. Check the local source manually."
    exit 1
fi

# Step 7: Run interactive setup using uv run
echo "Step 6: Running interactive setup..."
uv run python MSIM.py

echo "Installation complete."
echo "You can now run:"
echo "  uv run python MSIM.py menu      - interactive menu"
echo "  uv run python MSIM.py start     - start server in background"
echo "  uv run python MSIM.py serve     - start server in foreground"