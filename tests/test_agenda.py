"""Tests del módulo de agenda y citas."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.configuracion import Configuracion
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password

# ── Fixtures ──────────────────────────────────────────────────────────────────


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


@pytest.fixture(name="setup")
def setup_fixture(db_engine):
    """Crea consultorio, usuario, configuracion y paciente de prueba."""
    with Session(db_engine) as db:
        c = Consultorio(nombre="Test", tipo="MEDICO", direccion="X", telefono="0")
        db.add(c)
        db.flush()

        u = Usuario(
            consultorio_id=c.id,
            email="doc@t.com",
            password_hash=hash_password("pwd"),
            nombre="Dr",
            rol="MEDICO",
        )
        db.add(u)
        db.flush()
        db.add(Configuracion(consultorio_id=c.id))

        p = Paciente(consultorio_id=c.id, nombre="Ana García", tipo="HUMANO")
        db.add(p)
        db.commit()

        cid, uid, pid = c.id, u.id, p.id
        token = crear_token(u)

    return {"token": token, "consultorio_id": cid, "usuario_id": uid, "paciente_id": pid}


def _auth(setup):
    return {"Authorization": f"Bearer {setup['token']}"}


def _fecha_futura(horas=2):
    """Datetime UTC futuro en N horas, como string ISO."""
    return (datetime.now(timezone.utc) + timedelta(hours=horas)).isoformat()


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_crear_cita_ok(client, setup):
    """Crear cita con paciente válido devuelve 201."""
    resp = client.post("/api/citas", json={
        "paciente_id": setup["paciente_id"],
        "fecha_hora": _fecha_futura(3),
        "duracion_min": 30,
        "motivo": "Control",
    }, headers=_auth(setup))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["paciente_nombre"] == "Ana García"
    assert data["estado"] == "pendiente"


def test_crear_cita_paciente_inexistente_falla(client, setup):
    """Cita con paciente_id inexistente devuelve 404."""
    resp = client.post("/api/citas", json={
        "paciente_id": 9999,
        "fecha_hora": _fecha_futura(4),
        "duracion_min": 30,
    }, headers=_auth(setup))
    assert resp.status_code == 404


def test_crear_cita_paciente_otro_consultorio_falla(client, setup, db_engine):
    """Cita con paciente de otro consultorio devuelve 404."""
    with Session(db_engine) as db:
        otro = Consultorio(nombre="Otro", tipo="MEDICO", direccion="Y", telefono="1")
        db.add(otro)
        db.flush()
        p_otro = Paciente(consultorio_id=otro.id, nombre="Foráneo", tipo="HUMANO")
        db.add(p_otro)
        db.commit()
        pid_otro = p_otro.id

    resp = client.post("/api/citas", json={
        "paciente_id": pid_otro,
        "fecha_hora": _fecha_futura(5),
        "duracion_min": 30,
    }, headers=_auth(setup))
    assert resp.status_code == 404


def test_listar_citas_semana(client, setup):
    """GET /api/agenda/semana devuelve las citas de la semana."""
    # Crear cita para hoy
    client.post("/api/citas", json={
        "paciente_id": setup["paciente_id"],
        "fecha_hora": _fecha_futura(1),
        "duracion_min": 30,
    }, headers=_auth(setup))

    lunes = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())).strftime("%Y-%m-%d")
    resp = client.get(f"/api/agenda/semana?fecha_inicio={lunes}", headers=_auth(setup))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_editar_cita(client, setup):
    """PATCH /api/citas/{id} actualiza el motivo."""
    cita = client.post("/api/citas", json={
        "paciente_id": setup["paciente_id"],
        "fecha_hora": _fecha_futura(6),
        "duracion_min": 30,
        "motivo": "Original",
    }, headers=_auth(setup)).json()

    resp = client.patch(f"/api/citas/{cita['id']}", json={"motivo": "Actualizado"},
                        headers=_auth(setup))
    assert resp.status_code == 200
    assert resp.json()["motivo"] == "Actualizado"


def test_cambiar_estado_cita(client, setup):
    """PATCH /api/citas/{id}/estado cambia el estado correctamente."""
    cita = client.post("/api/citas", json={
        "paciente_id": setup["paciente_id"],
        "fecha_hora": _fecha_futura(7),
        "duracion_min": 30,
    }, headers=_auth(setup)).json()

    resp = client.patch(f"/api/citas/{cita['id']}/estado",
                        json={"estado": "confirmada"},
                        headers=_auth(setup))
    assert resp.status_code == 200
    assert resp.json()["estado"] == "confirmada"


def test_eliminar_cita(client, setup):
    """DELETE /api/citas/{id} elimina la cita (204)."""
    cita = client.post("/api/citas", json={
        "paciente_id": setup["paciente_id"],
        "fecha_hora": _fecha_futura(8),
        "duracion_min": 30,
    }, headers=_auth(setup)).json()

    resp = client.delete(f"/api/citas/{cita['id']}", headers=_auth(setup))
    assert resp.status_code == 204

    # Verificar que ya no existe
    resp2 = client.patch(f"/api/citas/{cita['id']}", json={"motivo": "x"},
                         headers=_auth(setup))
    assert resp2.status_code == 404


def test_no_choque_de_horarios(client, setup):
    """Crear dos citas solapadas devuelve 409 en la segunda."""
    hora = _fecha_futura(10)

    client.post("/api/citas", json={
        "paciente_id": setup["paciente_id"],
        "fecha_hora": hora,
        "duracion_min": 60,
    }, headers=_auth(setup))

    # Segunda cita 30 min después (dentro del bloque de la primera)
    hora_solapada = (datetime.now(timezone.utc) + timedelta(hours=10, minutes=30)).isoformat()
    resp = client.post("/api/citas", json={
        "paciente_id": setup["paciente_id"],
        "fecha_hora": hora_solapada,
        "duracion_min": 30,
    }, headers=_auth(setup))
    assert resp.status_code == 409
