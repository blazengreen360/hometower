#!/usr/bin/env bash
set -e

FILE=""
SINK=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --file) FILE="$2"; shift ;;
        --sink) SINK="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$FILE" ] || [ -z "$SINK" ]; then
    echo "Usage: $0 --file <src/path/to/target.py> --sink <function_name>"
    exit 1
fi

python3 .github/skills/ast-taint-tracer/scripts/tracer.py "$FILE" "$SINK"
