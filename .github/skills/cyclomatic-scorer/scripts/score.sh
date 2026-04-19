#!/usr/bin/env bash
set -e

TARGET="${1:-src/}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

echo "📊 Running McCabe Cyclomatic Complexity sweep on $TARGET..."

if [ -x "$VENV_PYTHON" ]; then
    PYTHON_BIN="$VENV_PYTHON"
else
    PYTHON_BIN="$(command -v python3)"
fi

if [ -z "${PYTHON_BIN:-}" ]; then
    echo "🔴 Python runtime not found."
    exit 2
fi

# Ensure radon is available without mutating the system Python.
if ! "$PYTHON_BIN" -m radon --help > /dev/null 2>&1; then
    if [ "$PYTHON_BIN" = "$VENV_PYTHON" ]; then
        echo "Installing radon into repo .venv..."
        "$PYTHON_BIN" -m pip install radon
    else
        echo "🔴 radon is unavailable and no repo .venv is present."
        echo "Create/update .venv and install dependencies before running the scorer."
        exit 2
    fi
fi

# We run radon cc. We want to fail if any block has complexity > 10 (which is rank C).
# -nc means "only show C and worse" (which is exactly > 10)
# -s shows the raw score
echo "Looking for functions with Complexity > 10 (Rank C or worse)..."

RESULTS=$("$PYTHON_BIN" -m radon cc -nc -s "$TARGET")

if [ -n "$RESULTS" ]; then
    echo "🔴 COMPLEXITY VIOLATION: Functions found exceeding threshold (10):"
    echo "$RESULTS"
    echo "Fix required. Strangler fig or extract domain functions."
    exit 1
else
    echo "✅ PASS: All analyzed functions are within complexity bounds (≤ 10)."
fi
