"""Tests para endpoints HTTP y vistas de Licencia."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.consultorio import Consultorio
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password
from app.services.licencia import iniciar_si_no_existe


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(db_engine):
    def override():
        with Session(db_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(name="medico_auth")
def medico_auth_fixture(db_engine):
    with Session(db_engine) as s:
        iniciar_si_no_existe(s)
        c = Consultorio(nombre="Clinica Test", tipo="MEDICO", direccion="Av. Principal", telefono="04141234567")
        s.add(c)
        s.commit()
        s.refresh(c)

        u = Usuario(
            email="dr@clinica.com",
            password_hash=hash_password("clave123"),
            nombre="Dr. Test",
            rol="MEDICO",
            consultorio_id=c.id,
            activo=True,
        )
        s.add(u)
        s.commit()
        s.refresh(u)

        token = crear_token(u)
        return {"headers": {"Authorization": f"Bearer {token}"}, "usuario": u}


def test_get_vista_licencia(client, medico_auth):
    resp = client.get("/licencia", headers=medico_auth["headers"])
    assert resp.status_code == 200
    assert "Licencia" in resp.text
    assert "Hardware ID" in resp.text


def test_api_estado_licencia(client, medico_auth):
    resp = client.get("/api/licencia/estado", headers=medico_auth["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "estado" in data
    assert data["estado"] == "trial"
    assert "hardware_id" in data


def test_api_activar_licencia(client, medico_auth):
    resp = client.post(
        "/api/licencia/activar",
        headers=medico_auth["headers"],
        json={"clave": "ALTA-ABCD-EFGH-JKLM-NPQR"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["estado"] == "activa"
