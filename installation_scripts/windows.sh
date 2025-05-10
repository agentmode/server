#!/bin/bash

set -e # exit immediately on any errors

if ! command -v powershell &> /dev/null; then
  echo "Error: PowerShell is not installed.  Please install PowerShell to proceed." >&2
  exit 1
fi

# Install uv using PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install Python 3.13
uv python install 3.13

# Change to the target directory and initialize uv
uv init
uv add agentmode

echo "Installation completed successfully"