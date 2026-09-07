from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create the pgvector extension and any missing tables.

    Convenience for local development only. `create_all` creates missing
    *tables*; it does not alter existing ones, so adding a column to a table
    that already exists has no effect here and the API then fails with
    `UndefinedColumn` at query time.

    Alembic owns the schema now:

        alembic revision --autogenerate -m "what changed"
        alembic upgrade head

    CI fails if the models and migrations have drifted apart.
    """
    from app import (  # noqa: F401  (registers mappers)
        models,
        models_content,
        models_interview,
        models_learning,
        models_quiz,
    )

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)


def reset_schema() -> None:
    """Drop and recreate every table.

    Destructive by design and used only by the seed script, which replaces all
    data anyway. This is what makes a model change take effect without a
    migration tool.
    """
    from app import (  # noqa: F401
        models,
        models_content,
        models_interview,
        models_learning,
        models_quiz,
    )

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
