"""Tests para la auditoría inmutable mediante hash-chain — Módulo 9."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.auditoria import Auditoria
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.services.auditoria import registrar, verificar_cadena
from app.services.auth import crear_token, hash_password


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
    with Session(db_engine) as db:
        c = Consultorio(nombre="Clinica Auditoria", tipo="MEDICO", direccion="Dir", telefono="123")
        db.add(c)
        db.flush()

        medico = Usuario(
            consultorio_id=c.id,
            email="auditor.medico@alta.com",
            password_hash=hash_password("clave123"),
            nombre="Dr. Auditor",
            rol="MEDICO",
        )
        asistente = Usuario(
            consultorio_id=c.id,
            email="auditor.asist@alta.com",
            password_hash=hash_password("clave123"),
            nombre="Asistente Auditor",
            rol="ASISTENTE",
        )
        db.add_all([medico, asistente])
        db.flush()

        paciente = Paciente(
            consultorio_id=c.id,
            nombre="Paciente Auditado",
            tipo="HUMANO",
        )
        db.add(paciente)
        db.commit()

        db.refresh(medico)
        db.refresh(asistente)
        db.refresh(paciente)

        return {
            "consultorio": c,
            "medico": medico,
            "asistente": asistente,
            "paciente": paciente,
            "token_medico": crear_token(medico),
            "token_asistente": crear_token(asistente),
        }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_registrar_auditoria(db_engine, setup):
    """Verifica que registrar una acción genera un bloque con hash anterior y hash actual válidos."""
    with Session(db_engine) as db:
        r1 = registrar(db, setup["medico"].id, "CREATE", "paciente", 1)
        assert r1.id is not None
        assert r1.hash_anterior == "GENESIS"
        assert len(r1.hash_actual) == 64

        r2 = registrar(db, setup["medico"].id, "UPDATE", "paciente", 1)
        assert r2.hash_anterior == r1.hash_actual
        assert len(r2.hash_actual) == 64


def test_cadena_hash_valida(db_engine, setup):
    """Verifica que múltiples registros consecutivos mantienen la cadena íntegra."""
    with Session(db_engine) as db:
        registrar(db, setup["medico"].id, "CREATE", "paciente", 1)
        registrar(db, setup["medico"].id, "CREATE", "consulta", 1)
        registrar(db, setup["medico"].id, "VIEW", "consulta", 1)
        registrar(db, setup["medico"].id, "CREATE", "pago", 1)

        assert verificar_cadena(db) is True


def test_cadena_hash_invalida_si_se_manipula(db_engine, setup):
    """Verifica que alterar cualquier registro o su hash rompe la integridad de la cadena."""
    with Session(db_engine) as db:
        r1 = registrar(db, setup["medico"].id, "CREATE", "paciente", 1)
        r2 = registrar(db, setup["medico"].id, "CREATE", "consulta", 1)

        # Manipulación maliciosa de datos
        r1.accion = "DELETE"
        db.add(r1)
        db.commit()

        assert verificar_cadena(db) is False


def test_verificar_cadena_endpoint(client, setup, db_engine):
    """Verifica los endpoints GET /api/auditoria y GET /api/auditoria/verificar."""
    # 1. Realizar una acción que dispare auditoría (ej: crear paciente)
    resp_pac = client.post(
        "/api/pacientes",
        json={"nombre": "Auditado Auto", "tipo": "HUMANO"},
        headers=_auth(setup["token_medico"]),
    )
    assert resp_pac.status_code == 201

    # 2. Listar auditoría
    resp_list = client.get("/api/auditoria", headers=_auth(setup["token_medico"]))
    assert resp_list.status_code == 200
    registros = resp_list.json()
    assert len(registros) >= 1
    assert registros[0]["entidad"] == "paciente"

    # 3. Verificar cadena
    resp_ver = client.get("/api/auditoria/verificar", headers=_auth(setup["token_medico"]))
    assert resp_ver.status_code == 200
    assert resp_ver.json()["cadena_valida"] is True

    # 4. Asistente no debe tener acceso a la auditoría (403 Forbidden)
    resp_asist = client.get("/api/auditoria", headers=_auth(setup["token_asistente"]))
    assert resp_asist.status_code == 403
