#!/bin/bash
set -e

echo "============================================================"
echo "  MSIM Installer"
echo "============================================================"

# Check for uv

if ! command -v uv &> /dev/null; then
echo "uv not found. Installing..."
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

# Reload PATH

export PATH="HOME/.cargo/bin:HOME/.cargo/bin:HOME/.cargo/bin:PATH"
if ! command -v uv &> /dev/null; then
echo "Failed to install uv. Please install manually:"
echo "  curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh"
exit 1
fi
fi

echo "Installing Python dependencies..."
uv sync

echo "Running interactive setup..."
python MSIM.py

echo "Installation complete."
echo "You can now run:"
echo "  python MSIM.py menu      - interactive menu"
echo "  python MSIM.py start     - start server in background"
echo "  python MSIM.py serve     - start server in foreground"