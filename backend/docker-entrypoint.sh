#!/bin/sh
# Run migrations, then hand off to the server.
#
# The container must die if migrations fail, rather than start an API against a
# schema it does not match. A crash loop is visible in every orchestrator; a
# running API throwing UndefinedColumn on one endpoint is not.
#
# What it prints on failure matters as much as the exit code. A failed deploy
# on a managed host shows the last few lines of the log and nothing else, and
# SQLAlchemy's own errors name a driver or a socket rather than the setting
# that is actually wrong.
set -e

fail() {
    echo ""
    echo "=================================================================="
    echo "  MIGRATIONS FAILED — the API will not start."
    echo "=================================================================="
    echo ""
    echo "  Almost always DATABASE_URL. Check, in this order:"
    echo ""
    echo "  1. Is it set at all? Currently: ${DATABASE_URL:-<empty>}"
    echo ""
    echo "  2. Managed providers hand out a URL this app rewrites for you"
    echo "     (postgresql:// and postgres:// both become postgresql+psycopg://),"
    echo "     so the prefix should not be the problem. If you see"
    echo "     'No module named psycopg2', this image is older than that fix."
    echo ""
    echo "  3. Neon, Supabase and most managed Postgres require TLS. The URL"
    echo "     needs ?sslmode=require on the end."
    echo ""
    echo "  4. Use the POOLED connection string where the provider offers one."
    echo "     A direct connection can refuse a container that scales."
    echo ""
    echo "  5. pgvector must be available. Neon supports it; the first"
    echo "     migration runs CREATE EXTENSION vector itself."
    echo ""
    echo "  The real error is immediately above this block."
    echo ""
    exit 1
}

echo "==> alembic upgrade head"
alembic upgrade head || fail

echo "==> starting: $*"
exec "$@"
