"""Tests del módulo de consultas médicas y control de acceso por roles — Módulo 7."""

from datetime import datetime, timezone

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
from app.services.consultas import crear_consulta
from app.schemas.consulta import ConsultaCreate


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
    """Crea consultorio, médico, asistente y paciente de prueba."""
    with Session(db_engine) as db:
        c = Consultorio(nombre="Clinica Test", tipo="MEDICO", direccion="Dir 1", telefono="123")
        db.add(c)
        db.flush()

        medico = Usuario(
            consultorio_id=c.id,
            email="medico@alta.com",
            password_hash=hash_password("clave123"),
            nombre="Dr. House",
            rol="MEDICO",
        )
        asistente = Usuario(
            consultorio_id=c.id,
            email="asistente@alta.com",
            password_hash=hash_password("clave123"),
            nombre="Enfermera Clara",
            rol="ASISTENTE",
        )
        db.add_all([medico, asistente])
        db.flush()

        cfg = Configuracion(consultorio_id=c.id)
        db.add(cfg)

        paciente = Paciente(
            consultorio_id=c.id,
            nombre="Paciente Clinico",
            cedula="V-112233",
            tipo="HUMANO",
        )
        db.add(paciente)
        db.commit()

        db.refresh(medico)
        db.refresh(asistente)
        db.refresh(paciente)
        db.refresh(c)

        token_medico = crear_token(medico)
        token_asistente = crear_token(asistente)

        return {
            "consultorio": c,
            "medico": medico,
            "asistente": asistente,
            "paciente": paciente,
            "token_medico": token_medico,
            "token_asistente": token_asistente,
        }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_crear_consulta_medico_ok(client, setup):
    """El médico puede crear una consulta médica con nota clínica e indicaciones."""
    resp = client.post(
        "/api/consultas",
        json={
            "paciente_id": setup["paciente"].id,
            "motivo": "Cefalea constante",
            "nota": "Paciente refiere dolor occipital de 3 días de evolución.",
            "indicaciones": "Ibuprofeno 400mg cada 8 horas.",
            "diagnostico": "Cefalea tensional",
        },
        headers=_auth(setup["token_medico"]),
    )
    assert resp.status_code == 201
    datos = resp.json()
    assert datos["motivo"] == "Cefalea constante"
    assert datos["nota"] == "Paciente refiere dolor occipital de 3 días de evolución."
    assert datos["indicaciones"] == "Ibuprofeno 400mg cada 8 horas."
    assert datos["diagnostico"] == "Cefalea tensional"
    assert datos["medico_nombre"] == setup["medico"].nombre


def test_crear_consulta_asistente_falla_403(client, setup):
    """El asistente no tiene permisos para crear una consulta médica (403 Forbidden)."""
    resp = client.post(
        "/api/consultas",
        json={
            "paciente_id": setup["paciente"].id,
            "motivo": "Revisión",
            "nota": "Intento de creación por asistente",
        },
        headers=_auth(setup["token_asistente"]),
    )
    assert resp.status_code == 403
    assert "permitida únicamente para médicos" in resp.json()["detail"]


def test_listar_consultas_medico_ok(client, setup, db_engine):
    """El médico puede listar consultas de un paciente y ve la información clínica completa."""
    with Session(db_engine) as db:
        crear_consulta(
            db=db,
            data=ConsultaCreate(
                paciente_id=setup["paciente"].id,
                motivo="Control",
                nota="Nota confidencial de prueba",
                indicaciones="Reposo relativo",
                diagnostico="Gripe común",
            ),
            usuario=setup["medico"],
        )

    resp = client.get(
        f"/api/pacientes/{setup['paciente'].id}/consultas",
        headers=_auth(setup["token_medico"]),
    )
    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos) == 1
    c = datos[0]
    assert c["motivo"] == "Control"
    assert c["nota"] == "Nota confidencial de prueba"
    assert c["indicaciones"] == "Reposo relativo"
    assert c["diagnostico"] == "Gripe común"


def test_listar_consultas_asistente_sin_nota(client, setup, db_engine):
    """El asistente puede listar consultas del paciente pero NO recibe nota, indicaciones ni diagnostico."""
    with Session(db_engine) as db:
        crear_consulta(
            db=db,
            data=ConsultaCreate(
                paciente_id=setup["paciente"].id,
                motivo="Control postoperatorio",
                nota="Evolución favorable de la herida quirúrgica",
                indicaciones="Curación diaria con gasa estéril",
                diagnostico="Post-apendicectomía",
            ),
            usuario=setup["medico"],
        )

    resp = client.get(
        f"/api/pacientes/{setup['paciente'].id}/consultas",
        headers=_auth(setup["token_asistente"]),
    )
    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos) == 1
    c = datos[0]
    assert c["motivo"] == "Control postoperatorio"
    # Filtrado estricto: deben ser None
    assert c["nota"] is None
    assert c["indicaciones"] is None
    assert c["diagnostico"] is None


def test_obtener_consulta_medico_ok(client, setup, db_engine):
    """El médico puede consultar directamente el detalle de una consulta clínica."""
    with Session(db_engine) as db:
        c_obj = crear_consulta(
            db=db,
            data=ConsultaCreate(
                paciente_id=setup["paciente"].id,
                motivo="Evaluación",
                nota="Detalle extenso de nota clínica",
            ),
            usuario=setup["medico"],
        )
        c_id = c_obj.id

    resp = client.get(f"/api/consultas/{c_id}", headers=_auth(setup["token_medico"]))
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["nota"] == "Detalle extenso de nota clínica"
    assert datos["paciente_nombre"] == setup["paciente"].nombre


def test_obtener_consulta_asistente_falla_403(client, setup, db_engine):
    """El asistente no tiene autorización para acceder al endpoint individual de la consulta médica."""
    with Session(db_engine) as db:
        c_obj = crear_consulta(
            db=db,
            data=ConsultaCreate(
                paciente_id=setup["paciente"].id,
                motivo="Revisión",
                nota="Nota privada",
            ),
            usuario=setup["medico"],
        )
        c_id = c_obj.id

    resp = client.get(f"/api/consultas/{c_id}", headers=_auth(setup["token_asistente"]))
    assert resp.status_code == 403


def test_actualizar_consulta(client, setup, db_engine):
    """El médico puede actualizar campos de una consulta clínica."""
    with Session(db_engine) as db:
        c_obj = crear_consulta(
            db=db,
            data=ConsultaCreate(
                paciente_id=setup["paciente"].id,
                motivo="Inicial",
                nota="Nota previa",
            ),
            usuario=setup["medico"],
        )
        c_id = c_obj.id

    resp = client.put(
        f"/api/consultas/{c_id}",
        json={"motivo": "Actualizado", "nota": "Nota modificada"},
        headers=_auth(setup["token_medico"]),
    )
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["motivo"] == "Actualizado"
    assert datos["nota"] == "Nota modificada"


def test_consulta_aparece_en_historial_paciente(client, setup, db_engine):
    """Al crear una consulta médica, queda registrada en el historial del paciente."""
    with Session(db_engine) as db:
        crear_consulta(
            db=db,
            data=ConsultaCreate(
                paciente_id=setup["paciente"].id,
                motivo="Chequeo preventivo",
                nota="Todo normal",
                diagnostico="Sano",
            ),
            usuario=setup["medico"],
        )

    # 1. Médico ve historial completo
    resp_med = client.get(f"/api/pacientes/{setup['paciente'].id}/historial", headers=_auth(setup["token_medico"]))
    assert resp_med.status_code == 200
    hist_med = resp_med.json()["historial"]
    assert len(hist_med["consultas"]) == 1
    assert hist_med["consultas"][0]["motivo"] == "Chequeo preventivo"
    assert hist_med["consultas"][0]["nota"] == "Todo normal"

    # 2. Asistente ve historial pero la nota/diagnóstico viene protegida
    resp_asist = client.get(f"/api/pacientes/{setup['paciente'].id}/historial", headers=_auth(setup["token_asistente"]))
    assert resp_asist.status_code == 200
    hist_asist = resp_asist.json()["historial"]
    assert len(hist_asist["consultas"]) == 1
    assert hist_asist["consultas"][0]["motivo"] == "Chequeo preventivo"
    assert hist_asist["consultas"][0]["nota"] is None
    assert hist_asist["consultas"][0]["diagnostico"] is None
