"""Tests del endpoint GET /api/dashboard/resumen."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.cita import Cita
from app.models.configuracion import Configuracion
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    """Motor SQLite en memoria aislado por test."""
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
    """TestClient con DB en memoria."""
    def override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(name="setup")
def setup_fixture(db_engine):
    """Crea consultorio + usuario + configuracion y devuelve el token JWT."""
    with Session(db_engine) as db:
        consultorio = Consultorio(
            nombre="Test", tipo="MEDICO", direccion="Calle 1", telefono="555"
        )
        db.add(consultorio)
        db.flush()

        usuario = Usuario(
            consultorio_id=consultorio.id,
            email="doc@test.com",
            password_hash=hash_password("pwd"),
            nombre="Dr. Test",
            rol="MEDICO",
        )
        db.add(usuario)
        db.flush()

        config = Configuracion(consultorio_id=consultorio.id)
        db.add(config)
        db.commit()
        db.refresh(usuario)

        # Capturar IDs como enteros antes de que la sesión cierre y expire los objetos
        consultorio_id = consultorio.id
        usuario_id = usuario.id
        token = crear_token(usuario)

    return {"token": token, "consultorio_id": consultorio_id, "usuario_id": usuario_id}


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_dashboard_sin_auth_falla(client):
    """Sin token el endpoint devuelve 401 o 403."""
    resp = client.get("/api/dashboard/resumen")
    assert resp.status_code in (401, 403)


def test_dashboard_con_auth_ok(client, setup):
    """Con token válido el endpoint devuelve 200 y la estructura correcta."""
    resp = client.get(
        "/api/dashboard/resumen",
        headers={"Authorization": f"Bearer {setup['token']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "citas_hoy" in data
    assert "ingresos_hoy" in data
    assert "proximas_citas" in data
    assert isinstance(data["proximas_citas"], list)


def test_dashboard_con_citas_cuenta_correcto(client, setup, db_engine):
    """El contador de citas_hoy refleja solo las citas de hoy."""
    ahora = datetime.now(timezone.utc)
    with Session(db_engine) as db:
        # Crear paciente
        paciente = Paciente(
            consultorio_id=setup["consultorio_id"],
            nombre="Paciente Test",
            tipo="HUMANO",
        )
        db.add(paciente)
        db.flush()

        # 2 citas hoy (pendiente y completada)
        for estado in ["pendiente", "completada"]:
            db.add(Cita(
                consultorio_id=setup["consultorio_id"],
                paciente_id=paciente.id,
                profesional_id=setup["usuario_id"],
                fecha_hora=ahora,
                creada_por=setup["usuario_id"],
                estado=estado,
            ))
        db.commit()

    resp = client.get(
        "/api/dashboard/resumen",
        headers={"Authorization": f"Bearer {setup['token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["citas_hoy"] == 2
    assert data["citas_pendientes"] == 1
    assert data["citas_completadas"] == 1


def test_dashboard_ingresos_hoy_correcto(client, setup, db_engine):
    """Los ingresos_hoy suman solo los pagos de hoy con estado 'pagado'."""
    ahora = datetime.now(timezone.utc)
    with Session(db_engine) as db:
        paciente = Paciente(
            consultorio_id=setup["consultorio_id"],
            nombre="Paciente Pago",
            tipo="HUMANO",
        )
        db.add(paciente)
        db.flush()

        # Pago pagado hoy: 100
        db.add(Pago(
            consultorio_id=setup["consultorio_id"],
            paciente_id=paciente.id,
            monto=100.0,
            estado="pagado",
            fecha=ahora,
            registrado_por=setup["usuario_id"],
        ))
        # Pago pendiente hoy: NO debe sumar
        db.add(Pago(
            consultorio_id=setup["consultorio_id"],
            paciente_id=paciente.id,
            monto=50.0,
            estado="pendiente",
            fecha=ahora,
            registrado_por=setup["usuario_id"],
        ))
        db.commit()

    resp = client.get(
        "/api/dashboard/resumen",
        headers={"Authorization": f"Bearer {setup['token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingresos_hoy"] == 100.0
