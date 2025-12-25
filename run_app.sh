#!/bin/bash
# L4MOLE - Local AI Search Application Launcher
# Ensure we are in the script's directory
cd "$(dirname "$0")"

echo "=========================================="
echo "  L4MOLE - Local AI Search"
echo "=========================================="
echo ""

# Check for virtual environment
if [ ! -f ".venv/bin/python3" ] && [ ! -f ".venv/bin/python" ]; then
    echo "Error: Virtual environment not found."
    echo ""
    echo "Please run one of the following first:"
    echo "  python3 setup_app.py"
    echo "  python3 launcher.py"
    echo ""
    exit 1
fi

# Use python3 if available, otherwise python
if [ -f ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
else
    PYTHON=".venv/bin/python"
fi

echo "Starting application..."
$PYTHON main.py
