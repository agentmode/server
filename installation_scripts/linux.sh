#!/bin/bash

set -e # exit immediately on any errors

# Install uv
# Check if curl is installed, if not use wget, else return an error
if command -v curl >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
elif command -v wget >/dev/null 2>&1; then
  wget -qO- https://astral.sh/uv/install.sh | sh
else
  echo "Error: Neither curl nor wget is installed. Please install one of them to proceed." >&2
  exit 1
fi

# Install Python 3.13
uv python install 3.13

# Change to the target directory and initialize uv
uv init
uv add agentmode

echo "Installation completed successfully"