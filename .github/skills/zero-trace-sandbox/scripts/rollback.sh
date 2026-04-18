#!/usr/bin/env bash
set -e

echo "🛑 EXECUTING ZERO-TRACE TEARDOWN PROTOCOL"

# Wipe the schema down to base
echo "Rolling back database to base..."
docker compose exec -T api alembic downgrade base

# Bring it back up pristine
echo "Rebuilding database schema to head..."
docker compose exec -T api alembic upgrade head

echo "✨ Zero-Trace Teardown Complete! Database is pristine."
