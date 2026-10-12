"""Tests para las vistas GET /consultas y GET /configuracion (Módulo 13)."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401 — registra todas las tablas
from app.database import get_session
from app.main import app
from app.models.configuracion import Configuracion
from app.models.consulta import Consulta
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password


# ── Fixtures ───────────────────────────────────────────────────────────────────

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
    """TestClient con la sesión en memoria inyectada."""
    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app, follow_redirects=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="medico")
def medico_fixture(db_engine):
    """Crea un consultorio, su configuración y un usuario médico."""
    with Session(db_engine) as session:
        cons = Consultorio(
            nombre="Clínica Test",
            tipo="MEDICO",
            direccion="Calle 1",
            telefono="04140000001",
        )
        session.add(cons)
        session.flush()

        config = Configuracion(
            consultorio_id=cons.id,
            horario_apertura="08:00",
            horario_cierre="17:00",
            duracion_cita_default=30,
            precio_consulta_default=0.0,
            moneda_default="USD",
        )
        session.add(config)
        session.flush()

        usr = Usuario(
            consultorio_id=cons.id,
            email="medico@test.com",
            password_hash=hash_password("clave123"),
            nombre="Dr. Médico",
            rol="MEDICO",
        )
        session.add(usr)
        session.commit()
        session.refresh(usr)
        return {"usuario": usr, "token": crear_token(usr), "consultorio_id": cons.id}


@pytest.fixture(name="asistente")
def asistente_fixture(db_engine, medico):
    """Crea un usuario asistente en el mismo consultorio."""
    with Session(db_engine) as session:
        usr = Usuario(
            consultorio_id=medico["consultorio_id"],
            email="asistente@test.com",
            password_hash=hash_password("clave123"),
            nombre="Asistente Test",
            rol="ASISTENTE",
        )
        session.add(usr)
        session.commit()
        session.refresh(usr)
        return {"usuario": usr, "token": crear_token(usr)}


@pytest.fixture(name="consulta_existente")
def consulta_existente_fixture(db_engine, medico):
    """Crea un paciente y una consulta en el consultorio de prueba."""
    with Session(db_engine) as session:
        pac = Paciente(
            consultorio_id=medico["consultorio_id"],
            nombre="Juan Pérez",
            demo=False,
        )
        session.add(pac)
        session.flush()

        con = Consulta(
            consultorio_id=medico["consultorio_id"],
            paciente_id=pac.id,
            profesional_id=medico["usuario"].id,
            fecha=datetime.now(timezone.utc),
            motivo="Dolor de cabeza",
            nota="Nota clínica privada",
            indicaciones="Tomar ibuprofeno",
            diagnostico="Migraña leve",
            demo=False,
        )
        session.add(con)
        session.commit()
        session.refresh(con)
        return {"consulta": con, "paciente": pac}


# ── Tests /consultas ───────────────────────────────────────────────────────────

def test_listar_consultas_medico(client, medico, consulta_existente):
    """GET /consultas devuelve 200 con HTML y muestra la consulta para el médico."""
    client.cookies.set("alta_token", medico["token"])
    res = client.get("/consultas")
    assert res.status_code == 200
    assert "Consultas" in res.text
    assert "Juan Pérez" in res.text
    assert "Dolor de cabeza" in res.text


def test_listar_consultas_asistente_sin_nota(client, asistente, consulta_existente):
    """GET /consultas para ASISTENTE: ve fecha y motivo, pero NO diagnóstico ni columna clínica."""
    client.cookies.set("alta_token", asistente["token"])
    res = client.get("/consultas")
    assert res.status_code == 200
    # Motivo sí debe aparecer
    assert "Dolor de cabeza" in res.text
    # Diagnóstico y nota clínica NO deben aparecer en la vista de asistente
    assert "Migraña leve" not in res.text
    assert "Nota clínica privada" not in res.text
    # La columna Diagnóstico no debe renderizarse
    assert "Diagnóstico" not in res.text


def test_listar_consultas_sin_datos(client, medico):
    """GET /consultas sin consultas muestra el mensaje 'No hay consultas registradas'."""
    client.cookies.set("alta_token", medico["token"])
    res = client.get("/consultas")
    assert res.status_code == 200
    assert "No hay consultas registradas" in res.text


def test_listar_consultas_requiere_autenticacion(client):
    """GET /consultas sin token redirige a /login."""
    res = client.get("/consultas")
    assert res.status_code in (302, 303, 401)


# ── Tests /configuracion ──────────────────────────────────────────────────────

def test_configuracion_carga_para_medico(client, medico):
    """GET /configuracion devuelve 200 con todas las secciones para médico."""
    client.cookies.set("alta_token", medico["token"])
    res = client.get("/configuracion")
    assert res.status_code == 200
    assert "Configuración" in res.text
    # Secciones visibles para médico
    assert "Datos del consultorio" in res.text
    assert "Preferencias" in res.text
    assert "Copias de seguridad" in res.text
    assert "Sesión" in res.text
    # Datos del consultorio
    assert "Clínica Test" in res.text


def test_configuracion_carga_para_asistente(client, asistente, medico):
    """GET /configuracion para ASISTENTE: no muestra sección de backup ni usuarios."""
    client.cookies.set("alta_token", asistente["token"])
    res = client.get("/configuracion")
    assert res.status_code == 200
    assert "Configuración" in res.text
    # Backup NO debe aparecer
    assert "Copias de seguridad" not in res.text
    assert "btn-descargar-backup" not in res.text
    # Sección usuarios tampoco
    assert "btn-invitar-asistente" not in res.text
