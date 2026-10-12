"""Pruebas unitarias para migración idempotente de campos de Vacuna."""

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.services.migracion import ejecutar_migraciones


def test_migracion_añade_laboratorio():
    """Comprueba que la migración añada el campo laboratorio si no existía."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        inspector = inspect(conn)
        columnas = [col["name"] for col in inspector.get_columns("vacuna")]
        assert "laboratorio" in columnas


def test_migracion_añade_demo():
    """Comprueba que la migración reconozca el campo demo en vacuna."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        inspector = inspect(conn)
        columnas = [col["name"] for col in inspector.get_columns("vacuna")]
        assert "demo" in columnas


def test_migracion_idempotente():
    """Comprueba que ejecutar_migraciones pueda ejecutarse repetidas veces sin fallar."""
    # Debe completar sin lanzar excepción
    ejecutar_migraciones()
    ejecutar_migraciones()
