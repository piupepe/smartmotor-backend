"""
dependencies.py — Dependências compartilhadas do FastAPI

Centraliza get_db() para evitar duplicação entre routes/.
Importe assim nos routers:

    from dependencies import get_db
"""

from typing import Generator
from sqlalchemy.orm import Session
from database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão de banco de dados por requisição e garante fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
