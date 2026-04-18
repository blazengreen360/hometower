#!/usr/bin/env bash
set -e

TARGET=""
PAYLOAD=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --target) TARGET="$2"; shift ;;
        --payload) PAYLOAD="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$TARGET" ] || [ -z "$PAYLOAD" ]; then
    echo "Usage: $0 --target <url_path> --payload <blueprint.json>"
    exit 1
fi

python3 .github/skills/chaos-fuzz-deployer/scripts/attack.py "$TARGET" "$PAYLOAD"
