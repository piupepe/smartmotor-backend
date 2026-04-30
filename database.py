from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./smartmotor.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Re-exporta Base para main.py: from database import Base, engine
# Sem circular import — models.py não importa de database.py
from models import Base  # noqa: E402

__all__ = ["engine", "SessionLocal", "Base"]