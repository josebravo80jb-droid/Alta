"""Tests unitarios y de integración para el Módulo: Configuración de horarios públicos."""

from datetime import date, datetime, time, timedelta, timezone
import json
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
from app.models.usuario import Usuario
from app.services.agenda_publica import (
    obtener_slots_disponibles,
    parsear_horario_publico,
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


@pytest.fixture(name="setup_data")
def setup_data_fixture(db_engine):
    with Session(db_engine) as db:
        c = Consultorio(
            nombre="Clínica Pruebas",
            tipo="MEDICO",
            direccion="Caracas",
            telefono="04141234567",
            slug="clinica-pruebas",
            agenda_publica_activa=True,
            duracion_cita_publica=30,
        )
        db.add(c)
        db.flush()

        cfg = Configuracion(
            consultorio_id=c.id,
            horario_apertura="08:00",
            horario_cierre="18:00",
            dias_laborables="LUN,MAR,MIE,JUE,VIE",
            duracion_cita_default=30,
        )
        db.add(cfg)

        medico = Usuario(
            consultorio_id=c.id,
            nombre="Dr. Juan",
            email="dr.juan@test.com",
            password_hash=hash_password("clave123"),
            rol="MEDICO",
        )
        db.add(medico)

        asistente = Usuario(
            consultorio_id=c.id,
            nombre="Asistente",
            email="asistente@test.com",
            password_hash=hash_password("clave123"),
            rol="ASISTENTE",
        )
        db.add(asistente)

        pac = Paciente(
            consultorio_id=c.id,
            nombre="Paciente Uno",
            telefono="04149999999",
        )
        db.add(pac)
        db.commit()
        db.refresh(c)
        db.refresh(medico)
        db.refresh(asistente)
        db.refresh(pac)
        return {
            "consultorio": c,
            "configuracion": cfg,
            "medico": medico,
            "asistente": asistente,
            "paciente": pac,
        }


def test_parsear_horario_publico_sin_configuracion_usa_fallback(db_engine, setup_data):
    """Test 1: Si horario_publico es None, usa la Configuracion global como fallback."""
    with Session(db_engine) as db:
        consultorio = setup_data["consultorio"]
        horario = parsear_horario_publico(consultorio, db=db)
        assert horario["hora_apertura"] == "08:00"
        assert horario["hora_cierre"] == "18:00"
        assert horario["dias"] == [1, 2, 3, 4, 5]
        assert horario["pausa_inicio"] is None
        assert horario["limite_diario"] == 0
        assert horario["dias_bloqueados"] == []


def test_parsear_horario_publico_con_json_valido(db_engine, setup_data):
    """Test 2: Si hay JSON válido en consultorio.horario_publico, devuelve sus valores."""
    with Session(db_engine) as db:
        consultorio = setup_data["consultorio"]
        datos = {
            "dias": [1, 3, 5],
            "hora_apertura": "09:00",
            "hora_cierre": "16:00",
            "pausa_inicio": "12:30",
            "pausa_fin": "13:30",
            "limite_diario": 15,
            "dias_bloqueados": ["2026-10-20"],
        }
        consultorio.horario_publico = json.dumps(datos)
        horario = parsear_horario_publico(consultorio, db=db)
        assert horario == datos


def test_slots_solo_en_dias_laborables(db_engine, setup_data):
    """Test 3: Slots únicamente se generan en los días permitidos."""
    with Session(db_engine) as db:
        c = db.get(Consultorio, setup_data["consultorio"].id)
        c.horario_publico = json.dumps({
            "dias": [1],
            "hora_apertura": "08:00",
            "hora_cierre": "12:00",
            "pausa_inicio": None,
            "pausa_fin": None,
            "limite_diario": 0,
            "dias_bloqueados": [],
        })
        db.add(c)
        db.commit()

        slots = obtener_slots_disponibles(db, c.id, dias=14)
        for fecha_str in slots:
            dt = date.fromisoformat(fecha_str)
            dia_num = (dt.weekday() + 1) % 7
            assert dia_num == 1


def test_slots_excluye_pausa_mediodia(db_engine, setup_data):
    """Test 4: No debe haber slots entre pausa_inicio y pausa_fin."""
    with Session(db_engine) as db:
        c = db.get(Consultorio, setup_data["consultorio"].id)
        c.horario_publico = json.dumps({
            "dias": [0, 1, 2, 3, 4, 5, 6],
            "hora_apertura": "08:00",
            "hora_cierre": "17:00",
            "pausa_inicio": "12:00",
            "pausa_fin": "14:00",
            "limite_diario": 0,
            "dias_bloqueados": [],
        })
        db.add(c)
        db.commit()

        slots = obtener_slots_disponibles(db, c.id, dias=7)
        for dia_str, lista in slots.items():
            assert "12:00" not in lista
            assert "12:30" not in lista
            assert "13:00" not in lista
            assert "13:30" not in lista


def test_slots_respetan_limite_diario(db_engine, setup_data):
    """Test 5: Si hay límite diario y se alcanza, no se muestran más slots."""
    with Session(db_engine) as db:
        c = db.get(Consultorio, setup_data["consultorio"].id)
        c.horario_publico = json.dumps({
            "dias": [0, 1, 2, 3, 4, 5, 6],
            "hora_apertura": "08:00",
            "hora_cierre": "12:00",
            "pausa_inicio": None,
            "pausa_fin": None,
            "limite_diario": 1,
            "dias_bloqueados": [],
        })
        db.add(c)

        manana = datetime.now(timezone.utc) + timedelta(days=1)
        fecha_hora_cita = datetime.combine(manana.date(), time(9, 0), tzinfo=timezone.utc)
        cita = Cita(
            consultorio_id=c.id,
            paciente_id=setup_data["paciente"].id,
            profesional_id=setup_data["medico"].id,
            fecha_hora=fecha_hora_cita,
            duracion_min=30,
            estado="PENDIENTE", creada_por=setup_data["medico"].id,
        )
        db.add(cita)
        db.commit()

        slots = obtener_slots_disponibles(db, c.id, dias=3)
        key_manana = manana.date().isoformat()
        assert slots.get(key_manana, []) == []


def test_slots_excluyen_dias_bloqueados(db_engine, setup_data):
    """Test 6: Los días en dias_bloqueados no deben aparecer en los slots."""
    with Session(db_engine) as db:
        c = db.get(Consultorio, setup_data["consultorio"].id)
        fecha_bloqueada = (date.today() + timedelta(days=2)).isoformat()
        c.horario_publico = json.dumps({
            "dias": [0, 1, 2, 3, 4, 5, 6],
            "hora_apertura": "08:00",
            "hora_cierre": "17:00",
            "pausa_inicio": None,
            "pausa_fin": None,
            "limite_diario": 0,
            "dias_bloqueados": [fecha_bloqueada],
        })
        db.add(c)
        db.commit()

        slots = obtener_slots_disponibles(db, c.id, dias=7)
        assert fecha_bloqueada not in slots


def test_hora_apertura_cierre_personalizadas(db_engine, setup_data):
    """Test 7: Horarios de apertura y cierre personalizados generan la cantidad correcta de slots."""
    with Session(db_engine) as db:
        c = db.get(Consultorio, setup_data["consultorio"].id)
        c.horario_publico = json.dumps({
            "dias": [0, 1, 2, 3, 4, 5, 6],
            "hora_apertura": "09:00",
            "hora_cierre": "11:00",
            "pausa_inicio": None,
            "pausa_fin": None,
            "limite_diario": 0,
            "dias_bloqueados": [],
        })
        db.add(c)
        db.commit()

        fecha_futura = (date.today() + timedelta(days=3)).isoformat()
        slots = obtener_slots_disponibles(db, c.id, dias=5)
        assert slots[fecha_futura] == ["09:00", "09:30", "10:00", "10:30"]


def test_endpoint_get_horario_publico(client, setup_data):
    """Test 8: GET /api/consultorio/horario-publico devuelve el horario actual."""
    token = crear_token(setup_data["medico"])
    res = client.get(
        "/api/consultorio/horario-publico",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "dias" in data
    assert "hora_apertura" in data
    assert "hora_cierre" in data


def test_endpoint_patch_horario_publico(client, setup_data):
    """Test 9: PATCH /api/consultorio/horario-publico actualiza correctamente."""
    token = crear_token(setup_data["medico"])
    payload = {
        "dias": [1, 2, 3, 4],
        "hora_apertura": "08:30",
        "hora_cierre": "16:30",
        "pausa_inicio": "12:00",
        "pausa_fin": "13:00",
        "limite_diario": 8,
        "dias_bloqueados": ["2026-10-25"],
    }
    res = client.patch(
        "/api/consultorio/horario-publico",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["horario"]["dias"] == [1, 2, 3, 4]
    assert data["horario"]["limite_diario"] == 8


def test_patch_horario_solo_medico(client, setup_data):
    """Test 10: Solo el médico puede modificar el horario público (asistente da 403)."""
    token_asistente = crear_token(setup_data["asistente"])
    payload = {
        "dias": [1, 2, 3],
        "hora_apertura": "08:00",
        "hora_cierre": "17:00",
    }
    res = client.patch(
        "/api/consultorio/horario-publico",
        json=payload,
        headers={"Authorization": f"Bearer {token_asistente}"},
    )
    assert res.status_code == 403


def test_patch_horario_datos_invalidos_falla(client, setup_data):
    """Test 11: Datos con formatos de hora o días fuera de rango deben fallar (422)."""
    token = crear_token(setup_data["medico"])
    # Hora inválida
    res1 = client.patch(
        "/api/consultorio/horario-publico",
        json={"dias": [1], "hora_apertura": "25:00", "hora_cierre": "17:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 422

    # Día fuera de rango (ej 7)
    res2 = client.patch(
        "/api/consultorio/horario-publico",
        json={"dias": [7], "hora_apertura": "08:00", "hora_cierre": "17:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 422

    # Fecha bloqueada inválida
    res3 = client.patch(
        "/api/consultorio/horario-publico",
        json={"dias": [1], "hora_apertura": "08:00", "hora_cierre": "17:00", "dias_bloqueados": ["fecha-mala"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res3.status_code == 422
