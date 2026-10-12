"""Pruebas unitarias para cálculo orientativo de dosis veterinarias."""

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.consultorio import Consultorio
from app.models.usuario import Usuario
from app.services.auth import crear_token
from app.services.veterinaria.dosis import (
    calcular_dosis,
    calcular_dosis_con_concentracion,
    listar_medicamentos,
)


@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def test_calcular_dosis_amoxicilina():
    """Comprueba cálculo de amoxicilina: 15 kg * 10 mg/kg = 150 mg."""
    res = calcular_dosis("amoxicilina", 15.0)
    assert res["medicamento"] == "amoxicilina"
    assert res["peso_kg"] == 15.0
    assert res["dosis_mg"] == 150.0
    assert res["via"] == "oral"
    assert res["frecuencia"] == "cada 12h"


def test_calcular_dosis_con_peso_cero_falla():
    """Comprueba que peso cero o negativo lance excepción."""
    with pytest.raises(ValueError):
        calcular_dosis("amoxicilina", 0.0)

    with pytest.raises(ValueError):
        calcular_dosis("amoxicilina", -5.0)


def test_calcular_dosis_medicamento_inexistente_falla():
    """Comprueba que un medicamento desconocido lance ValueError."""
    with pytest.raises(ValueError):
        calcular_dosis("farmaco_inexistente", 10.0)


def test_calcular_dosis_con_concentracion():
    """Comprueba cálculo con concentración: 150 mg / 50 mg/ml = 3.0 ml."""
    res = calcular_dosis_con_concentracion("amoxicilina", 15.0, 50.0)
    assert res["dosis_mg"] == 150.0
    assert res["concentracion_mg_ml"] == 50.0
    assert res["volumen_ml"] == 3.0


def test_listar_medicamentos():
    """Comprueba que devuelva la lista de medicamentos disponibles."""
    meds = listar_medicamentos()
    assert len(meds) >= 12
    assert "amoxicilina" in meds
    assert "meloxicam" in meds
    assert "tramadol" in meds


def test_endpoint_dosis(client, db_session):
    """Comprueba endpoint POST /api/veterinaria/dosis."""
    consultorio = Consultorio(nombre="Vet", tipo="VETERINARIO", direccion="Dir", telefono="123")
    db_session.add(consultorio)
    db_session.commit()
    usuario = Usuario(consultorio_id=consultorio.id, nombre="Vet", email="vet_dosis@test.com", password_hash="h", rol="MEDICO")
    db_session.add(usuario)
    db_session.commit()

    token = crear_token(usuario)
    payload = {
        "medicamento": "amoxicilina",
        "peso_kg": 15.0,
        "concentracion_mg_ml": 50.0,
    }
    resp = client.post("/api/veterinaria/dosis", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["dosis_mg"] == 150.0
    assert data["volumen_ml"] == 3.0


def test_dosis_advertencia_presente():
    """Comprueba que la advertencia legal esté presente en el resultado de dosis."""
    res = calcular_dosis("tramadol", 10.0)
    assert "advertencia" in res
    assert "orientativo" in res["advertencia"].lower()
