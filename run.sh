#!/bin/bash

# Simple script to run the StockMann terminal application correctly

echo "======================================"
echo "    Starting StockMann Terminal       "
echo "======================================"

# Ensure script halts on errors
set -e

# Enter the application directory
cd "$(dirname "$0")"

# Activate Virtual Environment (Create if it doesn't exist)
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Ensuring all dependencies are installed..."
pip install -r requirements.txt > /dev/null

echo ""
echo "🚀 Booting FastAPI Server (http://127.0.0.1:8000)..."
python3 main.py