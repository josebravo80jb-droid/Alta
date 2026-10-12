"""Pruebas unitarias para calendario de vacunas y recordatorios veterinarios."""

from datetime import date, timedelta
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.consultorio import Consultorio
from app.models.dueno import Dueno
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.models.vacuna import Vacuna
from app.services.auth import crear_token
from app.services.veterinaria.recordatorios import (
    generar_mensaje_recordatorio,
    vacunas_proximas_7_dias,
    vacunas_vencidas,
)
from app.services.veterinaria.vacunas import (
    calcular_calendario,
    proxima_dosis,
    vacunas_pendientes,
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


def test_calcular_calendario_perro():
    """Comprueba cálculo de calendario de cachorro con vacunas y refuerzos."""
    fn = date(2026, 1, 1)
    cal = calcular_calendario("perro", fn)
    assert len(cal) > 0
    vacunas_nombres = [item["vacuna"] for item in cal]
    assert "moquillo" in vacunas_nombres
    assert "rabia" in vacunas_nombres


def test_calcular_calendario_gato():
    """Comprueba cálculo de calendario de felino."""
    fn = date(2026, 1, 1)
    cal = calcular_calendario("gato", fn)
    assert len(cal) > 0
    vacunas_nombres = [item["vacuna"] for item in cal]
    assert "triple felina" in vacunas_nombres


def test_calcular_calendario_sin_vacunas():
    """Comprueba que especies sin vacunas obligatorias (ej. ave) devuelvan lista vacía."""
    fn = date(2026, 1, 1)
    cal = calcular_calendario("ave", fn)
    assert cal == []


def test_vacunas_pendientes():
    """Comprueba detección de vacunas pendientes vs aplicadas."""
    fn = date(2026, 1, 1)
    paciente = Paciente(
        consultorio_id=1,
        nombre="Firulais",
        especie="perro",
        fecha_nacimiento=fn,
    )
    vacunas_aplicadas = [
        {"tipo": "moquillo", "fecha_aplicacion": date(2026, 2, 15)}
    ]
    pendientes = vacunas_pendientes(paciente, vacunas_aplicadas)
    # Debe haber pendientes para rabia, parvovirus, etc.
    assert len(pendientes) > 0


def test_vacunas_proximas_7_dias(db_session):
    """Comprueba detección de vacunas en ventana de 7 días."""
    consultorio = Consultorio(nombre="Vet", tipo="VETERINARIO", direccion="Dir", telefono="123")
    db_session.add(consultorio)
    db_session.commit()

    dueno = Dueno(consultorio_id=consultorio.id, nombre="Juan", telefono="+584121112233")
    db_session.add(dueno)
    db_session.commit()

    paciente = Paciente(consultorio_id=consultorio.id, nombre="Max", tipo="MASCOTA", dueno_id=dueno.id)
    db_session.add(paciente)
    db_session.commit()

    hoy = date.today()
    vacuna = Vacuna(
        consultorio_id=consultorio.id,
        paciente_id=paciente.id,
        tipo="rabia",
        fecha_aplicacion=hoy - timedelta(days=360),
        proxima_dosis=hoy + timedelta(days=3),
        aplicada_por=1,
    )
    db_session.add(vacuna)
    db_session.commit()

    proximas = vacunas_proximas_7_dias(db_session, consultorio.id)
    assert len(proximas) == 1
    assert proximas[0]["mascota_nombre"] == "Max"
    assert proximas[0]["dias_restantes"] == 3


def test_vacunas_vencidas(db_session):
    """Comprueba detección de vacunas cuya fecha de dosis ya expiró."""
    consultorio = Consultorio(nombre="Vet", tipo="VETERINARIO", direccion="Dir", telefono="123")
    db_session.add(consultorio)
    db_session.commit()

    paciente = Paciente(consultorio_id=consultorio.id, nombre="Luna", tipo="MASCOTA")
    db_session.add(paciente)
    db_session.commit()

    hoy = date.today()
    vacuna = Vacuna(
        consultorio_id=consultorio.id,
        paciente_id=paciente.id,
        tipo="triple felina",
        fecha_aplicacion=hoy - timedelta(days=400),
        proxima_dosis=hoy - timedelta(days=10),
        aplicada_por=1,
    )
    db_session.add(vacuna)
    db_session.commit()

    vencidas = vacunas_vencidas(db_session, consultorio.id)
    assert len(vencidas) == 1
    assert vencidas[0]["mascota_nombre"] == "Luna"
    assert vencidas[0]["dias_vencida"] == 10


def test_generar_mensaje_recordatorio():
    """Comprueba formato del mensaje de recordatorio."""
    paciente = Paciente(nombre="Max", consultorio_id=1)
    dueno = Dueno(nombre="Carlos", telefono="123", consultorio_id=1)
    vac = {"tipo": "rabia", "proxima_dosis": date(2026, 10, 15)}

    msg = generar_mensaje_recordatorio(paciente, dueno, vac)
    assert "Carlos" in msg
    assert "Max" in msg
    assert "rabia" in msg


def test_registrar_vacuna(client, db_session):
    """Comprueba endpoint POST /api/veterinaria/vacunas."""
    consultorio = Consultorio(nombre="Vet", tipo="VETERINARIO", direccion="Dir", telefono="123")
    db_session.add(consultorio)
    db_session.commit()

    usuario = Usuario(consultorio_id=consultorio.id, nombre="Vet", email="vet_reg@test.com", password_hash="h", rol="MEDICO")
    db_session.add(usuario)
    db_session.commit()

    paciente = Paciente(consultorio_id=consultorio.id, nombre="Rocky", tipo="MASCOTA")
    db_session.add(paciente)
    db_session.commit()

    token = crear_token(usuario)
    payload = {
        "paciente_id": paciente.id,
        "tipo": "rabia",
        "fecha_aplicacion": str(date.today()),
        "lote": "LOT-123",
        "laboratorio": "Zoetis",
    }
    resp = client.post("/api/veterinaria/vacunas", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["tipo"] == "rabia"
    assert data["laboratorio"] == "Zoetis"
    assert data["proxima_dosis"] is not None


def test_proxima_dosis_calculada():
    """Comprueba cálculo de fecha de refuerzo sugerida."""
    hoy = date(2026, 5, 1)
    prox = proxima_dosis({"tipo": "rabia", "fecha_aplicacion": hoy})
    assert prox == hoy + timedelta(days=52 * 7)
