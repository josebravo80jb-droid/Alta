"""Tests del módulo de gestión y fichas completas de pacientes — Módulo 6."""

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
from app.models.dueno import Dueno
from app.models.paciente import Paciente
from app.models.usuario import Usuario
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
        c = Consultorio(nombre="Clinica Alta", tipo="MEDICO", direccion="Av 1", telefono="111")
        db.add(c)
        db.flush()

        u = Usuario(
            consultorio_id=c.id,
            email="dr@alta.com",
            password_hash=hash_password("clave123"),
            nombre="Dr. Prueba",
            rol="MEDICO",
        )
        db.add(u)
        cfg = Configuracion(consultorio_id=c.id)
        db.add(cfg)
        db.commit()
        db.refresh(u)
        db.refresh(c)

        token = crear_token(u)
        return {"consultorio": c, "usuario": u, "token": token}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_listar_pacientes(client, setup, db_engine):
    """Verifica listar pacientes pertenecientes al consultorio."""
    with Session(db_engine) as db:
        p1 = Paciente(consultorio_id=setup["consultorio"].id, nombre="Ana Pérez", cedula="123")
        p2 = Paciente(consultorio_id=setup["consultorio"].id, nombre="Carlos Ruiz", cedula="456")
        db.add_all([p1, p2])
        db.commit()

    resp = client.get("/api/pacientes", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos) == 2
    nombres = [item["nombre"] for item in datos]
    assert "Ana Pérez" in nombres
    assert "Carlos Ruiz" in nombres


def test_buscar_paciente_por_nombre(client, setup, db_engine):
    """Verifica que la búsqueda por parámetro q filtra por coincidencia de nombre."""
    with Session(db_engine) as db:
        p1 = Paciente(consultorio_id=setup["consultorio"].id, nombre="Beatriz Gomez", cedula="111")
        p2 = Paciente(consultorio_id=setup["consultorio"].id, nombre="Gonzalo Lopez", cedula="222")
        db.add_all([p1, p2])
        db.commit()

    resp = client.get("/api/pacientes?q=Beatriz", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos) == 1
    assert datos[0]["nombre"] == "Beatriz Gomez"


def test_buscar_paciente_por_cedula(client, setup, db_engine):
    """Verifica la búsqueda por cédula de paciente."""
    with Session(db_engine) as db:
        p1 = Paciente(consultorio_id=setup["consultorio"].id, nombre="Persona Uno", cedula="888999")
        p2 = Paciente(consultorio_id=setup["consultorio"].id, nombre="Persona Dos", cedula="111222")
        db.add_all([p1, p2])
        db.commit()

    resp = client.get("/api/pacientes?q=888999", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos) == 1
    assert datos[0]["cedula"] == "888999"


def test_obtener_ficha_con_historial(client, setup, db_engine):
    """Verifica obtener ficha de detalle completa incluyendo historial de citas."""
    with Session(db_engine) as db:
        p = Paciente(consultorio_id=setup["consultorio"].id, nombre="Juan Detalle", cedula="555")
        db.add(p)
        db.flush()

        cita = Cita(
            consultorio_id=setup["consultorio"].id,
            paciente_id=p.id,
            profesional_id=setup["usuario"].id,
            fecha_hora=datetime.now(timezone.utc),
            duracion_min=30,
            motivo="Control general",
            estado="completada",
            creada_por=setup["usuario"].id,
        )
        db.add(cita)
        db.commit()
        db.refresh(p)

    resp = client.get(f"/api/pacientes/{p.id}/historial", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["paciente"]["nombre"] == "Juan Detalle"
    assert len(datos["historial"]["citas"]) == 1
    assert datos["historial"]["citas"][0]["motivo"] == "Control general"


def test_actualizar_paciente(client, setup, db_engine):
    """Verifica actualización de campos del paciente."""
    with Session(db_engine) as db:
        p = Paciente(consultorio_id=setup["consultorio"].id, nombre="Original", telefono="123")
        db.add(p)
        db.commit()
        db.refresh(p)

    resp = client.put(
        f"/api/pacientes/{p.id}",
        json={"nombre": "Modificado", "telefono": "999888"},
        headers=_auth(setup["token"]),
    )
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["nombre"] == "Modificado"
    assert datos["telefono"] == "999888"


def test_eliminar_paciente_sin_historial_borra(client, setup, db_engine):
    """Verifica que un paciente sin citas ni consultas es borrado físicamente de la base de datos."""
    with Session(db_engine) as db:
        p = Paciente(consultorio_id=setup["consultorio"].id, nombre="Borrar Fisico")
        db.add(p)
        db.commit()
        db.refresh(p)
        p_id = p.id

    resp = client.delete(f"/api/pacientes/{p_id}", headers=_auth(setup["token"]))
    assert resp.status_code == 200

    with Session(db_engine) as db:
        assert db.get(Paciente, p_id) is None


def test_eliminar_paciente_con_historial_soft_delete(client, setup, db_engine):
    """Verifica que un paciente con citas no se borra físicamente sino que se marca como archivado (demo=True)."""
    with Session(db_engine) as db:
        p = Paciente(consultorio_id=setup["consultorio"].id, nombre="Borrar Logico")
        db.add(p)
        db.flush()

        cita = Cita(
            consultorio_id=setup["consultorio"].id,
            paciente_id=p.id,
            profesional_id=setup["usuario"].id,
            fecha_hora=datetime.now(timezone.utc),
            duracion_min=30,
            motivo="Prueba",
            estado="pendiente",
            creada_por=setup["usuario"].id,
        )
        db.add(cita)
        db.commit()
        db.refresh(p)
        p_id = p.id

    resp = client.delete(f"/api/pacientes/{p_id}", headers=_auth(setup["token"]))
    assert resp.status_code == 200

    # No debe aparecer en la lista activa
    resp_lista = client.get("/api/pacientes", headers=_auth(setup["token"]))
    ids = [item["id"] for item in resp_lista.json()]
    assert p_id not in ids

    # Pero sigue existiendo en base de datos con demo=True
    with Session(db_engine) as db:
        p_db = db.get(Paciente, p_id)
        assert p_db is not None
        assert p_db.demo is True


def test_crear_paciente_mascota_con_dueno(client, setup, db_engine):
    """Verifica el registro de un dueño y la creación de un paciente tipo MASCOTA asociado a él."""
    # 1. Crear dueño
    resp_dueno = client.post(
        "/api/duenos",
        json={
            "nombre": "Pedro Dueño",
            "telefono": "555-4321",
            "email": "pedro@dueno.com",
            "direccion": "Calle Central 10",
        },
        headers=_auth(setup["token"]),
    )
    assert resp_dueno.status_code == 201
    dueno = resp_dueno.json()
    assert dueno["nombre"] == "Pedro Dueño"

    # 2. Crear paciente tipo MASCOTA
    resp_pet = client.post(
        "/api/pacientes",
        json={
            "nombre": "Firulais",
            "tipo": "MASCOTA",
            "especie": "Canino",
            "raza": "Golden Retriever",
            "peso_kg": 25.5,
            "microchip": "CHIP-9988",
            "dueno_id": dueno["id"],
        },
        headers=_auth(setup["token"]),
    )
    assert resp_pet.status_code == 201
    pet = resp_pet.json()
    assert pet["nombre"] == "Firulais"
    assert pet["tipo"] == "MASCOTA"
    assert pet["especie"] == "Canino"
    assert pet["dueno_id"] == dueno["id"]

    # 3. Consultar historial/ficha completa y comprobar datos del dueño
    resp_ficha = client.get(f"/api/pacientes/{pet['id']}/historial", headers=_auth(setup["token"]))
    assert resp_ficha.status_code == 200
    ficha = resp_ficha.json()
    assert ficha["dueno"] is not None
    assert ficha["dueno"]["nombre"] == "Pedro Dueño"


def test_filtrar_pacientes_por_tipo(client, setup, db_engine):
    """Verifica el filtrado de pacientes por parámetro tipo=HUMANO o tipo=MASCOTA."""
    with Session(db_engine) as db:
        p_humano = Paciente(consultorio_id=setup["consultorio"].id, nombre="Laura Humana", tipo="HUMANO")
        p_mascota = Paciente(consultorio_id=setup["consultorio"].id, nombre="Michi Gato", tipo="MASCOTA")
        db.add_all([p_humano, p_mascota])
        db.commit()

    # Filtro HUMANO
    resp_h = client.get("/api/pacientes?tipo=HUMANO", headers=_auth(setup["token"]))
    assert resp_h.status_code == 200
    datos_h = resp_h.json()
    assert all(p["tipo"] == "HUMANO" for p in datos_h)
    assert any(p["nombre"] == "Laura Humana" for p in datos_h)

    # Filtro MASCOTA
    resp_m = client.get("/api/pacientes?tipo=MASCOTA", headers=_auth(setup["token"]))
    assert resp_m.status_code == 200
    datos_m = resp_m.json()
    assert all(p["tipo"] == "MASCOTA" for p in datos_m)
    assert any(p["nombre"] == "Michi Gato" for p in datos_m)


def test_ficha_medico_muestra_sexo_no_tipo(client, setup, db_engine):
    """Ficha HTML de AltaMed: el badge verde 'HUMANO' no debe aparecer para pacientes humanos.
    El badge solo se renderiza para mascotas (naranja). En AltaMed el tipo HUMANO es implícito.
    Nota: el campo 'sexo' aún no existe en el modelo; este test verifica solo la presentación del badge.
    """
    with Session(db_engine) as db:
        p = Paciente(
            consultorio_id=setup["consultorio"].id,
            nombre="María Ficha Test",
            cedula="V-99999999",
            tipo="HUMANO",
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        paciente_id = p.id

    resp = client.get(f"/pacientes/{paciente_id}", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    html = resp.text

    # AltaMed (paciente HUMANO): el badge naranja de MASCOTA no debe aparecer
    assert "background-color:#fdf0d5" not in html  # color exclusivo del badge MASCOTA

    # El badge verde original (#e2f0d9) tampoco debe aparecer para HUMANO
    # (se eliminó en Bug 1 — solo se muestra para MASCOTA)
    assert "background-color:#e2f0d9" not in html

    # El nombre del paciente sí debe aparecer
    assert "Mar" in html  # parte del nombre "María Ficha Test"

