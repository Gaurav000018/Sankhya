"""Alembic environment.

The database URL comes from the application settings rather than alembic.ini, so
there is one place it is configured and migrations cannot quietly point at a
different database than the app.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db import Base

# Importing the model modules is what populates Base.metadata. Without this,
# autogenerate produces an empty migration and cheerfully drops every table.
from app import (  # noqa: F401
    models,
    models_content,
    models_interview,
    models_learning,
    models_quiz,
)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Leave pgvector's own objects alone."""
    if type_ == "table" and name in {"vector"}:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Catch column type changes, not just added and removed columns —
            # the class of change that silently corrupts data.
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
