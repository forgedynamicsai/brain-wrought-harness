#!/usr/bin/env bash
# =============================================================================
# supabase_migrate.sh — apply Brain-Wrought initial schema to a Supabase project
#
# Usage:
#   ./migrations/supabase_migrate.sh <project-ref> <db-password>
#
# Arguments:
#   project-ref   Supabase project reference ID (e.g. dtvdkuhteckxiwdjiikf)
#   db-password   Database password for the project
#
# Requirements:
#   - Supabase CLI installed and in PATH  (https://supabase.com/docs/guides/cli)
#   - psql available in PATH
#
# The script runs 0001_initial.sql against the given Supabase project's
# Postgres instance using the Supabase CLI db push mechanism.  It is
# idempotent: re-running it on an already-migrated project is safe.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <project-ref> <db-password>" >&2
    exit 1
fi

PROJECT_REF="$1"
DB_PASSWORD="$2"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATION_FILE="${SCRIPT_DIR}/0001_initial.sql"

if [[ ! -f "${MIGRATION_FILE}" ]]; then
    echo "ERROR: migration file not found: ${MIGRATION_FILE}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
if ! command -v supabase &>/dev/null; then
    echo "ERROR: supabase CLI not found in PATH." >&2
    echo "       Install it: https://supabase.com/docs/guides/cli" >&2
    exit 1
fi

if ! command -v psql &>/dev/null; then
    echo "ERROR: psql not found in PATH.  Install postgresql-client." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Derive connection string
# Supabase hosted Postgres connection format:
#   postgresql://postgres.<project-ref>:<password>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
# Use the direct (non-pooler) port 5432 for DDL migrations.
# ---------------------------------------------------------------------------
DB_HOST="db.${PROJECT_REF}.supabase.co"
DB_PORT="5432"
DB_USER="postgres"
DB_NAME="postgres"
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo "==> Applying migration to project: ${PROJECT_REF}"
echo "    Host:       ${DB_HOST}:${DB_PORT}"
echo "    Migration:  ${MIGRATION_FILE}"
echo ""

# ---------------------------------------------------------------------------
# Run migration
# ---------------------------------------------------------------------------
psql "${DATABASE_URL}" \
    --single-transaction \
    --set ON_ERROR_STOP=on \
    --file "${MIGRATION_FILE}"

echo ""
echo "==> Migration applied successfully."
