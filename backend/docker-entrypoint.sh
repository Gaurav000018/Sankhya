#!/bin/sh
# Run migrations, then hand off to the server.
#
# `set -e` matters more than usual here: if the migration fails, the container
# must die rather than start an API against a schema it does not match. A
# crash loop is visible in every orchestrator; a running API throwing
# UndefinedColumn on one endpoint is not.
set -e

echo "==> alembic upgrade head"
alembic upgrade head

echo "==> starting: $*"
exec "$@"
