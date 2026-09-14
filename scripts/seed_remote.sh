#!/usr/bin/env bash
# Seed a deployed database with the demo corpus.
#
#   ./scripts/seed_remote.sh 'postgresql://user:pass@host/db?sslmode=require'
#
# Or, to avoid the connection string appearing in your shell history:
#
#   export DATABASE_URL='...'
#   ./scripts/seed_remote.sh
#
# DESTRUCTIVE. The seed drops every table and rebuilds it — that is what makes
# the corpus deterministic, and it is why this asks before running against
# anything that already holds rows.
set -euo pipefail

IMAGE="sankhya-api:prod"
URL="${1:-${DATABASE_URL:-}}"

if [ -z "$URL" ]; then
    cat <<'USAGE'
Usage: ./scripts/seed_remote.sh '<DATABASE_URL>'

Copy the connection string from either:
  - Render  → sankhya-api → Environment → DATABASE_URL
  - Neon    → your project → Connection string (use the POOLED one)

Paste it exactly as given; the app normalises the driver prefix itself.
USAGE
    exit 2
fi

# The credential is never echoed — only enough to confirm the right database.
host=$(printf '%s' "$URL" | sed -E 's#^[^@]*@##; s#[/?].*$##')
db=$(printf '%s' "$URL" | sed -E 's#^[^/]*//[^/]*/##; s#\?.*$##')
echo "  host     : ${host:-?}"
echo "  database : ${db:-?}"
echo ""

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "  Building $IMAGE (first run only)..."
    docker build -q -f backend/Dockerfile.prod -t "$IMAGE" backend >/dev/null
fi

# Count first. An empty database needs no warning; a populated one does, because
# this is about to delete whatever is in it.
echo "  Checking what is already there..."
existing=$(docker run --rm -e DATABASE_URL="$URL" --entrypoint python "$IMAGE" -c "
from sqlalchemy import create_engine, text
from app.config import settings
try:
    with create_engine(settings.database_url).connect() as c:
        print(c.execute(text('select count(*) from users')).scalar())
except Exception as exc:
    # No users table yet is the normal first-run case, not a failure.
    print('0' if 'does not exist' in str(exc) or 'UndefinedTable' in str(type(exc).__name__) else f'ERR {exc}'[:200])
" 2>/dev/null || echo "ERR could not connect")

case "$existing" in
    ERR*)
        echo ""
        echo "  Could not read the database: ${existing#ERR }"
        echo "  Check the URL, and that it ends with ?sslmode=require"
        exit 1
        ;;
    0)
        echo "  Empty — nothing to lose."
        ;;
    *)
        echo ""
        echo "  !! This database already holds $existing officer account(s)."
        echo "  !! Seeding DROPS EVERY TABLE and rebuilds from scratch."
        echo ""
        printf "  Type 'yes' to continue: "
        read -r reply
        [ "$reply" = "yes" ] || { echo "  Cancelled."; exit 1; }
        ;;
esac

echo ""
echo "  Seeding..."
# APP_ENV=dev so the production startup checks (CORS, JWT secret) do not apply —
# this is a one-off task, not a server, and it never serves a request.
docker run --rm -e APP_ENV=dev -e DATABASE_URL="$URL" "$IMAGE" python -m app.seed.seed

echo ""
echo "  Done. Sign in with venkatesan@sankhya.gov.in / Sankhya@2026"
