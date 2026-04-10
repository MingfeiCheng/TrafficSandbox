#!/usr/bin/env bash
# Install TrafficSandbox dependencies using uv (preferred) or pip (fallback).
set -e

if command -v uv &> /dev/null; then
    echo "[install] Using uv"
    uv pip install -r pyproject.toml
else
    echo "[install] uv not found, falling back to pip"
    echo "[install] Tip: install uv for faster installs: curl -LsSf https://astral.sh/uv/install.sh | sh"
    pip install -r requirements.txt
fi
