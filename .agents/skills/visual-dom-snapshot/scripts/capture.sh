#!/usr/bin/env bash
set -e

URL=""
OUT="artifact.png"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --url) URL="$2"; shift ;;
        --out) OUT="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$URL" ]; then
    echo "Usage: $0 --url <path> [--out <filename.png>]"
    exit 1
fi

echo "📸 Starting headless capture sequence for http://localhost:8080$URL..."

# Install playwright if missing safely
if ! python3 -m pip show playwright > /dev/null 2>&1; then
    python3 -m pip install playwright
    python3 -m playwright install chromium
fi

python3 .agents/skills/visual-dom-snapshot/scripts/capture.py "$URL" "$OUT"
