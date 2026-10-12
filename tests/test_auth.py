"""Tests de autenticación: registro, login y get_current_user."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401 — registra modelos antes de create_all
from app.database import get_session
from app.main import app

# ── Fixtures ─────────────────────────────────────────────────────────────────


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


# ── Datos de prueba ───────────────────────────────────────────────────────────

REGISTRO_PAYLOAD = {
    "nombre": "Consultorio Prueba",
    "email": "doctor@prueba.com",
    "password": "segura123",
    "especialidad": "Medicina General",
    "direccion": "Calle Falsa 123",
    "telefono": "555-0000",
    "horario_apertura": "08:00",
    "horario_cierre": "17:00",
    "duracion_cita": 30,
    "precio_consulta": 50.0,
}

# ── Tests ─────────────────────────────────────────────────────────────────────


def test_register_crea_consultorio_y_usuario(client):
    """Un registro exitoso devuelve HTTP 201 con access_token y datos del usuario."""
    resp = client.post("/api/auth/register", json=REGISTRO_PAYLOAD)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["usuario"]["email"] == REGISTRO_PAYLOAD["email"]
    assert data["usuario"]["rol"] == "MEDICO"


def test_register_email_duplicado_falla(client):
    """Registrar el mismo email dos veces devuelve HTTP 400."""
    client.post("/api/auth/register", json=REGISTRO_PAYLOAD)
    resp = client.post("/api/auth/register", json=REGISTRO_PAYLOAD)
    assert resp.status_code == 400
    assert "email" in resp.json()["detail"].lower()


def test_login_ok(client):
    """Login con credenciales válidas devuelve HTTP 200 con access_token."""
    client.post("/api/auth/register", json=REGISTRO_PAYLOAD)
    resp = client.post(
        "/api/auth/login",
        json={"email": REGISTRO_PAYLOAD["email"], "password": REGISTRO_PAYLOAD["password"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["usuario"]["email"] == REGISTRO_PAYLOAD["email"]


def test_login_password_incorrecto_falla(client):
    """Login con password incorrecto devuelve HTTP 401."""
    client.post("/api/auth/register", json=REGISTRO_PAYLOAD)
    resp = client.post(
        "/api/auth/login",
        json={"email": REGISTRO_PAYLOAD["email"], "password": "INCORRECTA"},
    )
    assert resp.status_code == 401


def test_get_current_user_con_token_valido(client):
    """Un endpoint protegido responde 200 con un Bearer token válido."""
    # Registrar y obtener token
    reg = client.post("/api/auth/register", json=REGISTRO_PAYLOAD)
    token = reg.json()["access_token"]

    # Usar el token en un endpoint protegido (verificamos /api/auth/me que creamos abajo)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == REGISTRO_PAYLOAD["email"]


def test_get_current_user_sin_token_falla(client):
    """Sin header Authorization el endpoint protegido devuelve 403."""
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)
