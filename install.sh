#!/bin/bash
set -e

echo "============================================================"
echo "  MSIM Installer v1.0.1"
echo "============================================================"

# Step 1: Pull submodule if needed

echo "Step 1: Ensuring submodule is present..."
if [ ! -f "submodules/anythingllm-mcp/pyproject.toml" ]; then
echo "Submodule not found. Pulling..."
git submodule update --init --recursive
if [ ! -f "submodules/anythingllm-mcp/pyproject.toml" ]; then
echo "ERROR: Submodule still missing. Please run manually:"
echo "  git submodule update --init --recursive"
exit 1
fi
else
echo "Submodule already present."
fi

# Step 2: Install uv if missing

echo "Step 2: Checking uv..."
if ! command -v uv &> /dev/null; then
echo "uv not found. Installing..."
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
export PATH="HOME/.cargo/bin:HOME/.cargo/bin:HOME/.cargo/bin:PATH"
if ! command -v uv &> /dev/null; then
echo "ERROR: Failed to install uv. Please install manually:"
echo "  curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh"
exit 1
fi
fi

# Step 3: Install Python dependencies

echo "Step 3: Installing Python dependencies..."
uv sync

# Step 4: Validate MSIM.py

echo "Step 4: Validating MSIM.py..."
python -m py_compile MSIM.py || {
echo "MSIM.py appears corrupted. Downloading fresh copy..."
curl -o MSIM.py [https://raw.githubusercontent.com/giancbaring/msim/main/MSIM.py](https://raw.githubusercontent.com/giancbaring/msim/main/MSIM.py)
python -m py_compile MSIM.py || {
echo "ERROR: MSIM.py still invalid. Please check manually."
exit 1
}
}

# Step 5: Run interactive setup

echo "Step 5: Running interactive setup..."
python MSIM.py

echo "Installation complete."
echo "You can now run:"
echo "  python MSIM.py menu      - interactive menu"
echo "  python MSIM.py start     - start server in background"
echo "  python MSIM.py serve     - start server in foreground"