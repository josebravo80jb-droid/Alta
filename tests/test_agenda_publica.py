"""Tests completos para el Módulo de Agenda Pública (sin autenticación y configuración)."""

from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.cita import Cita
from app.models.configuracion import Configuracion
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.services.agenda_publica import (
    generar_slug_unico,
    limpiar_rate_limit,
    obtener_slots_disponibles,
    reservar_cita_publica,
    slugify,
    solicitar_horario_libre,
    verificar_rate_limit,
)
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
    """Crea consultorio con agenda pública activa, configuración y médico."""
    with Session(db_engine) as db:
        c = Consultorio(
            nombre="Clínica San Rafael",
            tipo="MEDICO",
            direccion="Calle 5 con Av. 10",
            telefono="04141234567",
            slug="clinica-san-rafael",
            agenda_publica_activa=True,
            duracion_cita_publica=30,
            telefono_whatsapp_publico="04141234567",
            bio_publica="Especialistas en salud familiar y preventiva.",
        )
        db.add(c)
        db.flush()

        cfg = Configuracion(
            consultorio_id=c.id,
            horario_apertura="08:00",
            horario_cierre="12:00",
            dias_laborables="LUN,MAR,MIE,JUE,VIE,SAB,DOM",  # Todos para facilidad en tests
            duracion_cita_default=30,
        )
        db.add(cfg)

        medico = Usuario(
            consultorio_id=c.id,
            nombre="Dr. Rafael",
            email="dr.rafael@clinica.com",
            password_hash=hash_password("clave123"),
            rol="MEDICO",
        )
        db.add(medico)

        asistente = Usuario(
            consultorio_id=c.id,
            nombre="Asistente",
            email="asistente@clinica.com",
            password_hash=hash_password("clave123"),
            rol="ASISTENTE",
        )
        db.add(asistente)

        db.commit()
        db.refresh(c)
        db.refresh(medico)
        db.refresh(asistente)

    return {
        "consultorio_id": c.id,
        "slug": c.slug,
        "medico_id": medico.id,
        "token_medico": crear_token(medico),
        "token_asistente": crear_token(asistente),
    }


def test_slugify_nombre_con_espacios():
    assert slugify("Clínica San Rafael & Asociados") == "clinica-san-rafael-asociados"
    assert slugify("Centro Médico Los Pinos!") == "centro-medico-los-pinos"
    assert slugify("   ") == "consultorio"


def test_generar_slug_unico(db_engine):
    with Session(db_engine) as db:
        c1 = Consultorio(nombre="Salud Total", direccion="Dir", telefono="123", slug="salud-total")
        db.add(c1)
        db.commit()

        slug2 = generar_slug_unico(db, "Salud Total")
        assert slug2 == "salud-total-2"


def test_obtener_slots_disponibles_7_dias(db_engine, setup):
    with Session(db_engine) as db:
        slots = obtener_slots_disponibles(db, setup["consultorio_id"], dias=7)
        assert len(slots) > 0
        # Debe contener fechas futuras con slots de 30 mins entre 08:00 y 12:00
        fechas = list(slots.keys())
        manana = fechas[1] if len(fechas) > 1 else fechas[0]
        assert "08:00" in slots[manana]
        assert "08:30" in slots[manana]
        assert "11:30" in slots[manana]


def test_slots_excluye_citas_existentes(db_engine, setup):
    with Session(db_engine) as db:
        manana_date = date.today() + timedelta(days=1)
        hora_ocupada = datetime.combine(manana_date, datetime.min.time().replace(hour=9, minute=0), tzinfo=timezone.utc)

        # Crear cita a las 09:00
        p = Paciente(consultorio_id=setup["consultorio_id"], nombre="Pedro", telefono="04140000000")
        db.add(p)
        db.flush()

        cita = Cita(
            consultorio_id=setup["consultorio_id"],
            paciente_id=p.id,
            profesional_id=setup["medico_id"],
            fecha_hora=hora_ocupada,
            duracion_min=30,
            estado="confirmada",
            creada_por=setup["medico_id"],
        )
        db.add(cita)
        db.commit()

        slots = obtener_slots_disponibles(db, setup["consultorio_id"], dias=7)
        slots_manana = slots[manana_date.isoformat()]
        assert "09:00" not in slots_manana
        assert "08:30" in slots_manana
        assert "09:30" in slots_manana


def test_slots_excluye_dias_no_laborables(db_engine, setup):
    with Session(db_engine) as db:
        cfg = db.exec(select(Configuracion).where(Configuracion.consultorio_id == setup["consultorio_id"])).first()
        cfg.dias_laborables = "LUN,MIE,VIE"
        db.add(cfg)
        db.commit()

        slots = obtener_slots_disponibles(db, setup["consultorio_id"], dias=7)
        # Revisar que las fechas generadas correspondan solo a LUN, MIE o VIE
        dias_es = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]
        for f_str in slots.keys():
            dt = date.fromisoformat(f_str)
            dia_cod = dias_es[dt.weekday()]
            assert dia_cod in ["LUN", "MIE", "VIE"]


def test_reservar_cita_publica_ok(db_engine, setup):
    with Session(db_engine) as db:
        manana_str = (date.today() + timedelta(days=1)).isoformat()
        datos = {
            "nombre": "María Rodríguez",
            "telefono": "04129998877",
            "motivo": "Evaluación general",
            "fecha": manana_str,
            "hora": "10:00",
        }
        res = reservar_cita_publica(db, setup["slug"], datos)
        assert res["cita_id"] is not None
        assert "wa.me" in res["enlace_whatsapp"]

        # Verificar en base de datos
        cita = db.get(Cita, res["cita_id"])
        assert cita is not None
        assert cita.origen == "publico"
        assert cita.nombre_solicitante == "María Rodríguez"
        assert cita.estado == "confirmada"

        # Verificar que se creó el paciente
        paciente = db.get(Paciente, cita.paciente_id)
        assert paciente is not None
        assert paciente.nombre == "María Rodríguez"
        assert paciente.telefono == "04129998877"


def test_reservar_cita_slot_ocupado_falla(db_engine, setup):
    with Session(db_engine) as db:
        manana_str = (date.today() + timedelta(days=1)).isoformat()
        datos = {
            "nombre": "Paciente 1",
            "telefono": "04121111111",
            "motivo": "Motivo 1",
            "fecha": manana_str,
            "hora": "10:30",
        }
        reservar_cita_publica(db, setup["slug"], datos)

        # Segundo intento en el mismo slot debe lanzar error
        with pytest.raises(ValueError, match="no se encuentra disponible"):
            reservar_cita_publica(db, setup["slug"], {
                "nombre": "Paciente 2",
                "telefono": "04122222222",
                "motivo": "Motivo 2",
                "fecha": manana_str,
                "hora": "10:30",
            })


def test_reservar_cita_sin_activar_falla(db_engine, setup):
    with Session(db_engine) as db:
        c = db.get(Consultorio, setup["consultorio_id"])
        c.agenda_publica_activa = False
        db.add(c)
        db.commit()

        manana_str = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValueError, match="no está habilitada"):
            reservar_cita_publica(db, setup["slug"], {
                "nombre": "Test",
                "telefono": "04141111111",
                "motivo": "Test",
                "fecha": manana_str,
                "hora": "11:00",
            })


def test_reservar_cita_slug_inexistente_falla(db_engine):
    with Session(db_engine) as db:
        with pytest.raises(ValueError, match="no existe"):
            reservar_cita_publica(db, "slug-fantasma-xyz", {
                "nombre": "Test",
                "telefono": "04141111111",
                "motivo": "Test",
                "fecha": "2026-10-15",
                "hora": "10:00",
            })


def test_solicitar_horario_libre_ok(db_engine, setup):
    with Session(db_engine) as db:
        datos = {
            "nombre": "Carlos Solicitante",
            "telefono": "04165554433",
            "motivo": "Necesito consulta tarde después de las 6pm",
            "fecha_preferida": "2026-10-20",
            "hora_preferida": "18:30",
        }
        res = solicitar_horario_libre(db, setup["slug"], datos)
        assert res["solicitud_id"] is not None

        cita = db.get(Cita, res["solicitud_id"])
        assert cita is not None
        assert cita.origen == "solicitud"
        assert cita.estado == "pendiente"
        assert cita.nombre_solicitante == "Carlos Solicitante"
        assert "18:30" in cita.motivo


def test_rate_limiting_bloquea():
    limpiar_rate_limit()
    ip = "192.168.1.100"
    for _ in range(5):
        assert verificar_rate_limit(ip) is True
    # La 6ta petición dentro de la misma hora debe ser rechazada
    assert verificar_rate_limit(ip) is False


def test_validacion_nombre_telefono_motivo(db_engine, setup):
    with Session(db_engine) as db:
        manana_str = (date.today() + timedelta(days=1)).isoformat()
        # Nombre muy corto
        with pytest.raises(ValueError, match="nombre"):
            reservar_cita_publica(db, setup["slug"], {
                "nombre": "A",
                "telefono": "04121234567",
                "motivo": "Consulta general",
                "fecha": manana_str,
                "hora": "10:00",
            })

        # Teléfono inválido
        with pytest.raises(ValueError, match="teléfono"):
            reservar_cita_publica(db, setup["slug"], {
                "nombre": "Juan Perez",
                "telefono": "123",
                "motivo": "Consulta general",
                "fecha": manana_str,
                "hora": "10:00",
            })

        # Motivo muy corto
        with pytest.raises(ValueError, match="motivo"):
            reservar_cita_publica(db, setup["slug"], {
                "nombre": "Juan Perez",
                "telefono": "04121234567",
                "motivo": "ab",
                "fecha": manana_str,
                "hora": "10:00",
            })


def test_endpoint_publico_sin_auth_ok(client, setup):
    # GET info consultorio
    r1 = client.get(f"/api/agenda-publica/{setup['slug']}")
    assert r1.status_code == 200
    assert r1.json()["nombre"] == "Clínica San Rafael"

    # GET slots disponibles
    r2 = client.get(f"/api/agenda-publica/{setup['slug']}/disponibles")
    assert r2.status_code == 200
    assert "slots" in r2.json()

    # GET vistas HTML públicas
    r3 = client.get(f"/agenda/{setup['slug']}")
    assert r3.status_code == 200
    assert "Agendar Cita" in r3.text

    r4 = client.get(f"/agenda/{setup['slug']}/solicitar")
    assert r4.status_code == 200
    assert "Solicitar horario libre" in r4.text


def test_endpoint_configurar_solo_medico(client, setup):
    # Sin autenticación -> 401
    r_no_auth = client.get("/api/consultorio/agenda-publica")
    assert r_no_auth.status_code == 401

    # Como asistente -> 403 al modificar
    r_asistente = client.patch(
        "/api/consultorio/agenda-publica",
        headers={"Authorization": f"Bearer {setup['token_asistente']}"},
        json={"activa": True},
    )
    assert r_asistente.status_code == 403

    # Como médico -> 200 al consultar y modificar
    r_medico_get = client.get(
        "/api/consultorio/agenda-publica",
        headers={"Authorization": f"Bearer {setup['token_medico']}"},
    )
    assert r_medico_get.status_code == 200

    r_medico_patch = client.patch(
        "/api/consultorio/agenda-publica",
        headers={"Authorization": f"Bearer {setup['token_medico']}"},
        json={
            "activa": True,
            "slug": "san-rafael-nuevo",
            "duracion_cita_publica": 45,
            "bio_publica": "Nueva bio descriptiva",
        },
    )
    assert r_medico_patch.status_code == 200
    assert r_medico_patch.json()["slug"] == "san-rafael-nuevo"
    assert r_medico_patch.json()["duracion_cita_publica"] == 45
