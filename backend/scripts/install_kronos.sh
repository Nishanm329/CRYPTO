#!/usr/bin/env bash
# Installs the optional Kronos forecaster (github.com/shiyu-coder/Kronos, MIT).
# Usage: ./scripts/install_kronos.sh [--cpu]
set -euo pipefail
cd "$(dirname "$0")/.."

KRONOS_DIR="vendor/Kronos"
KRONOS_REF="${KRONOS_REF:-master}"

if [ -d "$KRONOS_DIR/.git" ]; then
  echo "Updating $KRONOS_DIR"
  git -C "$KRONOS_DIR" fetch --depth 1 origin "$KRONOS_REF"
  git -C "$KRONOS_DIR" checkout -q FETCH_HEAD
else
  mkdir -p vendor
  git clone --depth 1 --branch "$KRONOS_REF" https://github.com/shiyu-coder/Kronos "$KRONOS_DIR"
fi

if [ "${1:-}" = "--cpu" ]; then
  pip install torch --index-url https://download.pytorch.org/whl/cpu
fi
pip install -r requirements-kronos.txt

echo "Kronos installed. Weights (${KRONOS_MODEL:-NeoQuasar/Kronos-small}) download from Hugging Face on first request."
