from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(connection, _record) -> None:
    # SQLite ignores ON DELETE CASCADE unless asked per connection: without this, deleting a project left its
    # images, videos, proposals and sources behind (PostgreSQL always enforces it).
    if type(connection).__module__.startswith("sqlite3"):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session]:
    with SessionLocal() as session:
        yield session

