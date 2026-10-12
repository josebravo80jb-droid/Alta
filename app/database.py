from sqlmodel import SQLModel, create_engine, Session
from app.config import DATABASE_URL

_db_url = DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif _db_url.startswith("postgresql://") and not _db_url.startswith("postgresql+"):
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)

if _db_url.startswith("sqlite"):
    engine = create_engine(_db_url, echo=False, connect_args={"check_same_thread": False})
else:
    engine = create_engine(_db_url, echo=False, pool_pre_ping=True)


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
