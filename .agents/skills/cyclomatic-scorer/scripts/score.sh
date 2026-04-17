#!/usr/bin/env bash
set -e

TARGET="${1:-src/}"

echo "📊 Running McCabe Cyclomatic Complexity sweep on $TARGET..."

# Ensure radon is installed
if ! python3 -m pip show radon > /dev/null 2>&1; then
    echo "Installing radon..."
    python3 -m pip install radon
fi

# We run radon cc. We want to fail if any block has complexity > 10 (which is rank C).
# -nc means "only show C and worse" (which is exactly > 10)
# -s shows the raw score
echo "Looking for functions with Complexity > 10 (Rank C or worse)..."

RESULTS=$(python3 -m radon cc -nc -s "$TARGET")

if [ -n "$RESULTS" ]; then
    echo "🔴 COMPLEXITY VIOLATION: Functions found exceeding threshold (10):"
    echo "$RESULTS"
    echo "Fix required. Strangler fig or extract domain functions."
    exit 1
else
    echo "✅ PASS: All analyzed functions are within complexity bounds (≤ 10)."
fi
