"""Tests para el servicio de cifrado de notas y diagnósticos — Módulo 9."""

import os
from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.configuracion import Configuracion
from app.models.consultorio import Consultorio
from app.models.consulta import Consulta
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password
from app.services.cifrado import CLAVE_PATH, cifrar, descifrar, get_fernet


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
        c = Consultorio(nombre="Clinica Cifrada", tipo="MEDICO", direccion="Dir", telefono="123")
        db.add(c)
        db.flush()

        medico = Usuario(
            consultorio_id=c.id,
            email="dr.cifrado@alta.com",
            password_hash=hash_password("clave123"),
            nombre="Dr. Cifrado",
            rol="MEDICO",
        )
        asistente = Usuario(
            consultorio_id=c.id,
            email="asist.cifrado@alta.com",
            password_hash=hash_password("clave123"),
            nombre="Asistente Cifrado",
            rol="ASISTENTE",
        )
        db.add_all([medico, asistente])
        db.flush()

        paciente = Paciente(
            consultorio_id=c.id,
            nombre="Paciente Secreto",
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

def test_cifrar_descifrar_roundtrip():
    """Verifica que el ciclo cifrar -> descifrar conserva exactamente el texto original."""
    texto_original = "Paciente presenta dolor lumbar agudo. Se receta Paracetamol 500mg. Ñandú y acentos áéíóú."
    cifrado = cifrar(texto_original)
    assert cifrado.startswith("gAAAAA")
    assert cifrado != texto_original

    descifrado = descifrar(cifrado)
    assert descifrado == texto_original


def test_clave_se_genera_si_no_existe():
    """Verifica que si la clave no existe, get_fernet() la genera y crea el archivo en disco."""
    assert CLAVE_PATH.exists()
    assert len(CLAVE_PATH.read_bytes()) == 44  # Longitud estándar de Fernet key en base64


def test_consulta_se_guarda_cifrada(client, setup, db_engine):
    """Verifica que en la base de datos la nota se guarda con el prefijo Fernet 'gAAAAA'."""
    resp = client.post(
        "/api/consultas",
        json={
            "paciente_id": setup["paciente"].id,
            "motivo": "Examen de rutina",
            "nota": "Nota altamente confidencial sobre salud mental.",
            "indicaciones": "Terapia psicológica.",
            "diagnostico": "Estrés crónico",
        },
        headers=_auth(setup["token_medico"]),
    )
    assert resp.status_code == 201
    consulta_id = resp.json()["id"]

    # Comprobar directamente en la base de datos (nivel físico)
    with Session(db_engine) as db:
        consulta_db = db.get(Consulta, consulta_id)
        assert consulta_db is not None
        assert consulta_db.nota.startswith("gAAAAA")
        assert "Nota altamente confidencial" not in consulta_db.nota
        assert consulta_db.indicaciones.startswith("gAAAAA")
        assert consulta_db.diagnostico.startswith("gAAAAA")


def test_consulta_se_lee_descifrada(client, setup, db_engine):
    """Verifica que el médico al leer la consulta recibe la nota completamente descifrada."""
    nota_esperada = "Hallazgo clínico detallado para lectura médica."
    resp_crear = client.post(
        "/api/consultas",
        json={
            "paciente_id": setup["paciente"].id,
            "motivo": "Revisión",
            "nota": nota_esperada,
        },
        headers=_auth(setup["token_medico"]),
    )
    assert resp_crear.status_code == 201
    c_id = resp_crear.json()["id"]

    resp_get = client.get(f"/api/consultas/{c_id}", headers=_auth(setup["token_medico"]))
    assert resp_get.status_code == 200
    assert resp_get.json()["nota"] == nota_esperada


def test_asistente_no_puede_descifrar(client, setup):
    """Verifica que el asistente no recibe los campos clínicos cifrados ni descifrados (recibe None)."""
    resp_crear = client.post(
        "/api/consultas",
        json={
            "paciente_id": setup["paciente"].id,
            "motivo": "Control",
            "nota": "Nota súper confidencial.",
            "indicaciones": "Reposo absoluto.",
            "diagnostico": "Gripe fuerte",
        },
        headers=_auth(setup["token_medico"]),
    )
    assert resp_crear.status_code == 201

    # Asistente lista consultas del paciente
    resp_asist = client.get(
        f"/api/pacientes/{setup['paciente'].id}/consultas",
        headers=_auth(setup["token_asistente"]),
    )
    assert resp_asist.status_code == 200
    consultas = resp_asist.json()
    assert len(consultas) >= 1
    for c in consultas:
        assert c["nota"] is None
        assert c["indicaciones"] is None
        assert c["diagnostico"] is None
