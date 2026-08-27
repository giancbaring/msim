#!/bin/bash
set -e

echo "============================================================"
echo "  MSIM Installer v1.0.2"
echo "============================================================"

# Step 1: Ensure submodule is present

echo "Step 1: Ensuring submodule is present..."
if [ ! -f "submodules/anythingllm-mcp/pyproject.toml" ]; then
echo "Submodule not found. Pulling..."
git submodule update --init --recursive || {
echo "Submodule pull failed. Cloning manually..."
rm -rf submodules/anythingllm-mcp
git clone [https://github.com/andreperez/anythingllm-mcp.git](https://github.com/andreperez/anythingllm-mcp.git) submodules/anythingllm-mcp
}
if [ ! -f "submodules/anythingllm-mcp/pyproject.toml" ]; then
echo "ERROR: Submodule still missing. Please run manually:"
echo "  git clone [https://github.com/andreperez/anythingllm-mcp.git](https://github.com/andreperez/anythingllm-mcp.git) submodules/anythingllm-mcp"
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

# Step 3: Install the wrapper manually (pip install)

echo "Step 3: Installing AnythingLLM wrapper..."
pip install ./submodules/anythingllm-mcp/

# Step 4: Install remaining Python dependencies

echo "Step 4: Installing remaining dependencies..."
uv sync

# Step 5: Validate MSIM.py

echo "Step 5: Validating MSIM.py..."
python -m py_compile MSIM.py || {
echo "MSIM.py appears corrupted. Downloading fresh copy..."
curl -o MSIM.py [https://raw.githubusercontent.com/giancbaring/msim/main/MSIM.py](https://raw.githubusercontent.com/giancbaring/msim/main/MSIM.py)
python -m py_compile MSIM.py || {
echo "ERROR: MSIM.py still invalid. Please check manually."
exit 1
}
}

# Step 6: Run interactive setup

echo "Step 6: Running interactive setup..."
python MSIM.py

echo "Installation complete."
echo "You can now run:"
echo "  python MSIM.py menu      - interactive menu"
echo "  python MSIM.py start     - start server in background"
echo "  python MSIM.py serve     - start server in foreground"