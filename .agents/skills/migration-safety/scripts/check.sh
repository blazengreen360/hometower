#!/usr/bin/env bash
# migration-safety: static audit of an Alembic migration file.
# Usage: check.sh alembic/versions/<file>.py

set -u
set -o pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <migration-file>" >&2
  exit 2
fi

FILE="$1"
if [[ ! -f "$FILE" ]]; then
  echo "not a file: $FILE" >&2
  exit 2
fi

HIGH=0
MED=0
LOW=0

say() {
  echo "[$1] $2"
  case "$1" in
    HIGH) HIGH=$((HIGH+1)) ;;
    MED)  MED=$((MED+1)) ;;
    LOW)  LOW=$((LOW+1)) ;;
  esac
}

grep_line() {
  grep -nE "$1" "$FILE" || true
}

echo "=== migration-safety: $FILE ==="

# HIGH ------------------------------------------------------------------
hits=$(grep_line 'add_column\([^)]*nullable\s*=\s*False')
if [[ -n "$hits" ]]; then
  while IFS= read -r line; do
    if ! echo "$line" | grep -q 'server_default'; then
      say HIGH "add_column NOT NULL without server_default (full-table rewrite): $line"
    fi
  done <<< "$hits"
fi

hits=$(grep_line 'alter_column\(')
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  if echo "$line" | grep -qE 'type_\s*='; then
    say HIGH "alter_column type change may require table rewrite: $line"
  fi
done <<< "$hits"

# downgrade sanity: if upgrade has drop_*, downgrade must not be empty/pass
if grep -qE 'drop_column|drop_table' "$FILE"; then
  down_body=$(awk '/^def downgrade/{flag=1;next}/^def /{flag=0}flag' "$FILE")
  if [[ -z "$(echo "$down_body" | grep -vE '^\s*(pass|#|$)')" ]]; then
    say HIGH "upgrade() drops schema but downgrade() is empty/pass — irreversible"
  fi
fi

# concurrent-index heuristic on hot tables
hits=$(grep_line 'create_index\(')
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  if ! echo "$line" | grep -q 'postgresql_concurrently\s*=\s*True'; then
    if echo "$line" | grep -qE "devices|connections|diagram_layouts"; then
      say HIGH "create_index on hot table without postgresql_concurrently=True: $line"
    fi
  fi
done <<< "$hits"

# op.execute UPDATE heuristic
hits=$(grep_line "op.execute\(.*UPDATE")
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  say HIGH "op.execute UPDATE — ensure batching/locking comment is present: $line"
done <<< "$hits"

# MEDIUM ----------------------------------------------------------------
hits=$(grep_line 'ForeignKey\(')
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  if ! echo "$line" | grep -q 'ondelete'; then
    say MED "ForeignKey without ondelete= (defaults to RESTRICT): $line"
  fi
done <<< "$hits"

hits=$(grep_line 'UniqueConstraint\(')
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  say MED "UniqueConstraint added — confirm existing data satisfies it: $line"
done <<< "$hits"

hits=$(grep_line 'sa\.Enum\(')
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  say MED "sa.Enum inline — prefer importing from src/models/types.py: $line"
done <<< "$hits"

# LOW -------------------------------------------------------------------
doc=$(awk '/"""/{c++;next}c==1{print}c==2{exit}' "$FILE" | tr -d '\n' | awk '{print NF}')
if [[ -n "${doc:-}" && "$doc" -lt 4 ]]; then
  say LOW "revision docstring is short (<4 words) — be more descriptive"
fi

# summary ---------------------------------------------------------------
echo ""
echo "MIGRATION-SAFETY SUMMARY:"
echo "  HIGH:   $HIGH"
echo "  MEDIUM: $MED"
echo "  LOW:    $LOW"

if [[ $HIGH -gt 0 ]]; then
  echo "VERDICT: BLOCK — resolve HIGH findings before merge."
  exit 1
fi
if [[ $MED -gt 0 ]]; then
  echo "VERDICT: WARN — add justification comments for MEDIUM findings."
  exit 0
fi
echo "VERDICT: CLEAN"
exit 0
