"""Tests para el Módulo Extra A: Bifurcación AltaMed / AltaPet."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.consultorio import Consultorio


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    """Motor SQLite en memoria, aislado por test."""
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
    """TestClient con la sesión sobreescrita para usar la DB en memoria."""

    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


PAYLOAD_BASE = {
    "nombre": "Centro de Salud",
    "email": "dr@salud.com",
    "password": "Password123!",
    "especialidad": "General",
    "direccion": "Av. Central 123",
    "telefono": "555-1234",
    "horario_apertura": "08:00",
    "horario_cierre": "18:00",
    "duracion_cita": 30,
    "precio_consulta": 40.0,
}


def test_registro_medico_crea_consultorio_medico(client, db_engine):
    """Registrar con tipo=MEDICO crea el consultorio como MEDICO."""
    payload = {**PAYLOAD_BASE, "email": "medico@clinica.com", "tipo": "MEDICO"}
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["tipo_consultorio"] == "MEDICO"
    assert data["usuario"]["tipo_consultorio"] == "MEDICO"

    with Session(db_engine) as session:
        cons = session.exec(select(Consultorio)).first()
        assert cons is not None
        assert cons.tipo == "MEDICO"


def test_registro_veterinario_crea_consultorio_veterinario(client, db_engine):
    """Registrar con tipo=VETERINARIO crea el consultorio como VETERINARIO."""
    payload = {**PAYLOAD_BASE, "email": "vet@pet.com", "tipo": "VETERINARIO"}
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["tipo_consultorio"] == "VETERINARIO"
    assert data["usuario"]["tipo_consultorio"] == "VETERINARIO"

    with Session(db_engine) as session:
        cons = session.exec(select(Consultorio)).first()
        assert cons is not None
        assert cons.tipo == "VETERINARIO"


def test_registro_sin_tipo_default_medico(client, db_engine):
    """Si no se especifica tipo en el payload, el default debe ser MEDICO."""
    payload = {**PAYLOAD_BASE, "email": "default@clinica.com"}
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["tipo_consultorio"] == "MEDICO"

    with Session(db_engine) as session:
        cons = session.exec(select(Consultorio)).first()
        assert cons is not None
        assert cons.tipo == "MEDICO"


def test_registro_tipo_invalido_falla(client):
    """Enviar un tipo diferente de MEDICO o VETERINARIO debe fallar con 400."""
    payload = {**PAYLOAD_BASE, "email": "invalido@clinica.com", "tipo": "ESPACIAL"}
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 400
    assert "tipo" in res.json()["detail"].lower()


def test_entrada_muestra_dos_opciones(client):
    """La vista /entrada responde 200 y muestra AltaMed y AltaPet con sus enlaces."""
    res = client.get("/entrada")
    assert res.status_code == 200
    html = res.text
    assert "AltaMed" in html
    assert "AltaPet" in html
    assert "/registro?tipo=MEDICO" in html
    assert "/registro?tipo=VETERINARIO" in html


def test_root_redirige_a_entrada_sin_sesion(client):
    """GET / redirige a /entrada si no hay sesión."""
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/entrada"


def test_me_devuelve_tipo_consultorio(client):
    """El endpoint /api/auth/me devuelve tipo_consultorio."""
    payload = {**PAYLOAD_BASE, "email": "vet_me@pet.com", "tipo": "VETERINARIO"}
    reg = client.post("/api/auth/register", json=payload)
    assert reg.status_code == 201
    token = reg.json()["access_token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["tipo_consultorio"] == "VETERINARIO"
