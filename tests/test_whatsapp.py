"""Tests para el servicio y endpoints de recordatorios de WhatsApp (wa.me)."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.cita import Cita
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password
from app.services.whatsapp import generar_enlace_whatsapp, generar_mensaje_recordatorio


# ── Tests Unitarios del Servicio ──────────────────────────────────────────────

def test_generar_enlace_whatsapp_ok():
    """Genera un enlace válido wa.me con teléfono internacional y mensaje codificado."""
    enlace = generar_enlace_whatsapp("+584121234567", "Hola, su cita es mañana.")
    assert enlace.startswith("https://wa.me/584121234567?text=")
    assert "Hola%2C%20su%20cita%20es%20ma%C3%B1ana." in enlace


def test_limpia_telefono_con_espacios_y_guiones():
    """Elimina espacios, guiones y paréntesis del número."""
    enlace = generar_enlace_whatsapp("+58 (412) 123-4567", "Prueba")
    assert enlace.startswith("https://wa.me/584121234567?text=Prueba")


def test_agrega_codigo_pais_si_falta():
    """Si el teléfono empieza con 0, agrega 58 en lugar del 0."""
    enlace = generar_enlace_whatsapp("04121234567", "Prueba")
    assert enlace.startswith("https://wa.me/584121234567?text=Prueba")

    # Si tiene 10 dígitos sin 0
    enlace2 = generar_enlace_whatsapp("4121234567", "Prueba")
    assert enlace2.startswith("https://wa.me/584121234567?text=Prueba")


def test_codifica_acentos_y_simbolos():
    """Codifica correctamente caracteres especiales, emojis y tildes."""
    mensaje = "¡Hola María! Confirmación 📅: 10:00"
    enlace = generar_enlace_whatsapp("+584121234567", mensaje)
    assert "%C2%A1Hola%20Mar%C3%ADa%21" in enlace
    assert "%F0%9F%93%85" in enlace  # emoji calendario


def test_telefono_invalido_lanza_error():
    """Teléfonos vacíos o con pocos dígitos deben lanzar ValueError."""
    with pytest.raises(ValueError):
        generar_enlace_whatsapp("", "Mensaje")

    with pytest.raises(ValueError):
        generar_enlace_whatsapp("123", "Mensaje")


def test_generar_mensaje_recordatorio_ok():
    """El mensaje incluye nombre del paciente, fecha, hora, lugar y consultorio."""
    class Obj:
        pass

    paciente = Obj()
    paciente.nombre = "Carlos Perez"

    cita = Obj()
    cita.fecha_hora = datetime(2026, 10, 15, 14, 30)
    cita.motivo = "Chequeo anual"

    consultorio = Obj()
    consultorio.nombre = "Clínica Sanitas"
    consultorio.direccion = "Av. Libertador Edif. Centro"

    msg = generar_mensaje_recordatorio(paciente, cita, consultorio)
    assert "Hola Carlos Perez" in msg
    assert "15/10/2026" in msg
    assert "14:30" in msg
    assert "Av. Libertador Edif. Centro" in msg
    assert "Chequeo anual" in msg
    assert "Clínica Sanitas" in msg


# ── Fixtures para Endpoint ───────────────────────────────────────────────────

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
    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="setup_citas")
def setup_citas_fixture(db_engine):
    with Session(db_engine) as db:
        # Consultorio 1
        c1 = Consultorio(nombre="Consultorio 1", direccion="Calle 1", telefono="555-1")
        db.add(c1)
        db.flush()

        u1 = Usuario(
            consultorio_id=c1.id,
            email="medico1@clinica.com",
            password_hash=hash_password("pass123"),
            nombre="Dr. Uno",
            rol="MEDICO",
        )
        db.add(u1)

        p1 = Paciente(
            consultorio_id=c1.id,
            nombre="Paciente Valido",
            telefono="+58 412 1234567",
        )
        p_sin_tel = Paciente(
            consultorio_id=c1.id,
            nombre="Sin Telefono",
            telefono="",
        )
        db.add(p1)
        db.add(p_sin_tel)
        db.flush()

        cita1 = Cita(
            consultorio_id=c1.id,
            paciente_id=p1.id,
            profesional_id=u1.id,
            fecha_hora=datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc),
            duracion_min=30,
            motivo="Control",
            creada_por=u1.id,
        )
        cita_sin_tel = Cita(
            consultorio_id=c1.id,
            paciente_id=p_sin_tel.id,
            profesional_id=u1.id,
            fecha_hora=datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc),
            duracion_min=30,
            motivo="Revisión",
            creada_por=u1.id,
        )
        db.add(cita1)
        db.add(cita_sin_tel)

        # Consultorio 2 (para probar aislamiento de tenant)
        c2 = Consultorio(nombre="Consultorio 2", direccion="Calle 2", telefono="555-2")
        db.add(c2)
        db.flush()

        u2 = Usuario(
            consultorio_id=c2.id,
            email="medico2@clinica.com",
            password_hash=hash_password("pass123"),
            nombre="Dr. Dos",
            rol="MEDICO",
        )
        db.add(u2)

        p2 = Paciente(
            consultorio_id=c2.id,
            nombre="Paciente Dos",
            telefono="+58 414 7654321",
        )
        db.add(p2)
        db.flush()

        cita2 = Cita(
            consultorio_id=c2.id,
            paciente_id=p2.id,
            profesional_id=u2.id,
            fecha_hora=datetime(2026, 10, 10, 11, 0, tzinfo=timezone.utc),
            duracion_min=30,
            motivo="Otra clínica",
            creada_por=u2.id,
        )
        db.add(cita2)
        db.commit()

        token1 = crear_token(u1)
        token2 = crear_token(u2)

        return {
            "token1": token1,
            "token2": token2,
            "cita1_id": cita1.id,
            "cita_sin_tel_id": cita_sin_tel.id,
            "cita2_id": cita2.id,
        }


# ── Tests de Endpoints ────────────────────────────────────────────────────────

def test_endpoint_recordatorio_devuelve_enlace(client, setup_citas):
    """GET /api/citas/{id}/recordatorio devuelve el enlace https://wa.me/ con los datos."""
    res = client.get(
        f"/api/citas/{setup_citas['cita1_id']}/recordatorio",
        headers={"Authorization": f"Bearer {setup_citas['token1']}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "enlace" in data
    assert data["enlace"].startswith("https://wa.me/584121234567?text=")
    assert "Paciente%20Valido" in data["enlace"]


def test_endpoint_recordatorio_requiere_auth(client, setup_citas):
    """Llamar al endpoint sin token devuelve 401/403."""
    res = client.get(f"/api/citas/{setup_citas['cita1_id']}/recordatorio")
    assert res.status_code in (401, 403)


def test_endpoint_recordatorio_filtra_por_consultorio(client, setup_citas):
    """Un usuario del consultorio 1 no puede ver ni generar recordatorio para citas del consultorio 2."""
    res = client.get(
        f"/api/citas/{setup_citas['cita2_id']}/recordatorio",
        headers={"Authorization": f"Bearer {setup_citas['token1']}"},
    )
    assert res.status_code == 404


def test_endpoint_recordatorio_sin_telefono_devuelve_400(client, setup_citas):
    """Si el paciente no tiene teléfono registrado devuelve 400 Bad Request."""
    res = client.get(
        f"/api/citas/{setup_citas['cita_sin_tel_id']}/recordatorio",
        headers={"Authorization": f"Bearer {setup_citas['token1']}"},
    )
    assert res.status_code == 400
    assert "teléfono" in res.json()["detail"].lower()
