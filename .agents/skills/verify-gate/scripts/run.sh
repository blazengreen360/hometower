#!/usr/bin/env bash
# verify-gate: Hometower pre-push quality gate.
# Usage:
#   run.sh                      # full gate inside docker
#   run.sh --fast               # skip docker build
#   run.sh --tests <path>       # narrow pytest to one file
#   run.sh --no-docker          # run on host .venv instead of container

set -u
set -o pipefail

FAST=0
NO_DOCKER=0
TESTS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fast) FAST=1; shift ;;
    --no-docker) NO_DOCKER=1; shift ;;
    --tests) TESTS="$2"; shift 2 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

PYTEST_STATUS="SKIPPED"
MYPY_STATUS="SKIPPED"
ARCH_STATUS="SKIPPED"
BUILD_STATUS="SKIPPED"

run() {
  echo ""
  echo "+ $*"
  "$@"
}

if [[ $NO_DOCKER -eq 1 ]]; then
  EXEC=""
  PYTEST_BIN=".venv/bin/pytest"
  MYPY_BIN=".venv/bin/mypy"
else
  EXEC="docker compose exec -T api"
  PYTEST_BIN="pytest"
  MYPY_BIN="mypy"
fi

# --- pytest ------------------------------------------------------------
echo ""
echo "=== pytest ==="
if [[ -n "$TESTS" ]]; then
  run $EXEC $PYTEST_BIN "$TESTS" -v
else
  run $EXEC $PYTEST_BIN
fi
if [[ $? -eq 0 ]]; then PYTEST_STATUS="PASS"; else PYTEST_STATUS="FAIL"; fi

# --- mypy --------------------------------------------------------------
echo ""
echo "=== mypy ==="
run $EXEC $MYPY_BIN src/ --ignore-missing-imports
if [[ $? -eq 0 ]]; then MYPY_STATUS="PASS"; else MYPY_STATUS="FAIL"; fi

# --- arch-grep ---------------------------------------------------------
echo ""
echo "=== arch-grep ==="
ARCH_FAIL=0

echo "- domain purity (no sqlmodel/fastapi/loguru in src/domain/)"
hits=$(grep -rnE "from (sqlmodel|fastapi|loguru)" src/domain/ --include="*.py" || true)
if [[ -n "$hits" ]]; then
  echo "$hits"
  ARCH_FAIL=1
fi

echo "- UI layering (no src.repositories in src/ui/)"
hits=$(grep -rnE "from src\.repositories" src/ui/ --include="*.py" || true)
if [[ -n "$hits" ]]; then
  echo "$hits"
  ARCH_FAIL=1
fi

echo "- logger discipline (no print() in src/, excluding __pycache__ and tests)"
hits=$(grep -rnE "\bprint\(" src/ --include="*.py" | grep -v __pycache__ | grep -v "/tests/" || true)
if [[ -n "$hits" ]]; then
  echo "$hits"
  ARCH_FAIL=1
fi

if [[ $ARCH_FAIL -eq 0 ]]; then ARCH_STATUS="PASS"; else ARCH_STATUS="FAIL"; fi

# --- docker build ------------------------------------------------------
if [[ $FAST -eq 1 || $NO_DOCKER -eq 1 ]]; then
  BUILD_STATUS="SKIPPED"
else
  echo ""
  echo "=== docker compose build ==="
  run docker compose build
  if [[ $? -eq 0 ]]; then BUILD_STATUS="PASS"; else BUILD_STATUS="FAIL"; fi
fi

# --- summary -----------------------------------------------------------
echo ""
echo "======================================================"
echo "VERIFY-GATE RESULT:"
printf "  pytest:    %s\n" "$PYTEST_STATUS"
printf "  mypy:      %s\n" "$MYPY_STATUS"
printf "  arch-grep: %s\n" "$ARCH_STATUS"
printf "  build:     %s\n" "$BUILD_STATUS"

OVERALL="PASS"
for s in "$PYTEST_STATUS" "$MYPY_STATUS" "$ARCH_STATUS" "$BUILD_STATUS"; do
  if [[ "$s" == "FAIL" ]]; then OVERALL="FAIL"; fi
done

echo "  OVERALL:   $OVERALL"
echo "======================================================"

if [[ "$OVERALL" == "FAIL" ]]; then exit 1; fi
exit 0
