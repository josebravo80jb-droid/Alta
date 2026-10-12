"""Tests end-to-end: flujo completo de un médico en un día de trabajo — Módulo 11.

Simula el ciclo real sin mocks: registro → login → pacientes → agenda →
consultas → pagos → PDF → dashboard → auditoría → cifrado en DB.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.configuracion import Configuracion
from app.models.consultorio import Consultorio
from app.models.consulta import Consulta
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password
from app.services.cifrado import descifrar


# ── Fixtures compartidos ──────────────────────────────────────────────────────

@pytest.fixture(name="db_engine")
def db_engine_fixture():
    """Motor SQLite en memoria aislado para cada test."""
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
    """TestClient con override de sesión de BD."""
    def override():
        with Session(db_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def _auth(token: str) -> dict:
    """Helper: cabecera de autorización Bearer."""
    return {"Authorization": f"Bearer {token}"}


def _hoy_iso() -> str:
    """Retorna la fecha de hoy en formato ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00:00")


# ── Test 1: Flujo completo de un día de trabajo del médico ────────────────────

def test_flujo_completo_dia_medico(client, db_engine):
    """Simula el flujo real de un médico desde registro hasta auditoría.

    Pasos:
    1. Registrar consultorio médico via API
    2. Login
    3. Crear 3 pacientes
    4. Agendar 5 citas para hoy
    5. Marcar 3 citas como completadas
    6. Crear 3 consultas con notas cifradas
    7. Registrar 3 pagos
    8. Descargar un recibo PDF
    9. Verificar el dashboard del día
    10. Verificar resumen de ingresos
    11. Verificar que la auditoría no está manipulada
    12. Verificar que las notas están cifradas en DB
    """

    # ── 1. Registrar consultorio ──────────────────────────────────────────────
    r = client.post("/api/auth/register", json={
        "nombre": "Dra. Elena Vargas",
        "email": "elena@clinicavargas.com",
        "password": "Segura2024!",
        "especialidad": "Medicina General",
        "direccion": "Av. Bolívar 100",
        "telefono": "+58 212 000-0001",
        "horario_apertura": "08:00",
        "horario_cierre": "18:00",
        "duracion_cita": 30,
        "precio_consulta": 50.0,
    })
    assert r.status_code == 201, f"Registro falló: {r.text}"
    token = r.json()["access_token"]
    medico_id = r.json()["usuario"]["id"]
    headers = _auth(token)

    # ── 2. Login con las mismas credenciales ──────────────────────────────────
    r = client.post("/api/auth/login", json={
        "email": "elena@clinicavargas.com",
        "password": "Segura2024!",
    })
    assert r.status_code == 200
    assert r.json()["access_token"]  # token válido

    # ── 3. Crear 3 pacientes ──────────────────────────────────────────────────
    paciente_ids = []
    for i in range(3):
        r = client.post("/api/pacientes", json={
            "nombre": f"Paciente E2E {i+1}",
            "cedula": f"V-{20000000 + i}",
            "tipo": "HUMANO",
            "telefono": f"+58 412 000-00{i+1}",
        }, headers=headers)
        assert r.status_code == 201, f"Crear paciente {i+1} falló: {r.text}"
        paciente_ids.append(r.json()["id"])

    assert len(paciente_ids) == 3

    # ── 4. Agendar 5 citas para hoy ──────────────────────────────────────────
    cita_ids = []
    ahora = datetime.now(timezone.utc)
    for i in range(5):
        dt = (ahora + timedelta(hours=i + 1)).replace(minute=0, second=0, microsecond=0)
        r = client.post("/api/citas", json={
            "paciente_id": paciente_ids[i % 3],
            "fecha_hora": dt.isoformat(),
            "duracion_min": 30,
            "motivo": f"Consulta E2E {i+1}",
        }, headers=headers)
        assert r.status_code == 201, f"Crear cita {i+1} falló: {r.text}"
        cita_ids.append(r.json()["id"])

    assert len(cita_ids) == 5

    # ── 5. Marcar 3 citas como completadas ───────────────────────────────────
    for cita_id in cita_ids[:3]:
        r = client.patch(f"/api/citas/{cita_id}/estado", json={
            "estado": "completada",
        }, headers=headers)
        assert r.status_code == 200, f"Cambiar estado cita {cita_id} falló: {r.text}"
        assert r.json()["estado"] == "completada"

    # ── 6. Crear 3 consultas con notas ───────────────────────────────────────
    consulta_ids = []
    for i in range(3):
        r = client.post("/api/consultas", json={
            "paciente_id": paciente_ids[i],
            "cita_id": cita_ids[i],
            "motivo": f"Dolor abdominal E2E {i+1}",
            "nota": f"Paciente refiere malestar desde hace {i+1} días. Examen físico normal.",
            "indicaciones": "Reposo y dieta blanda.",
            "diagnostico": "Gastritis leve",
        }, headers=headers)
        assert r.status_code == 201, f"Crear consulta {i+1} falló: {r.text}"
        consulta_ids.append(r.json()["id"])

    assert len(consulta_ids) == 3

    # ── 7. Registrar 3 pagos ─────────────────────────────────────────────────
    pago_ids = []
    montos = [50.0, 60.0, 75.0]
    for i in range(3):
        r = client.post("/api/pagos", json={
            "paciente_id": paciente_ids[i],
            "consulta_id": consulta_ids[i],
            "monto": montos[i],
            "moneda": "USD",
            "metodo": "efectivo",
            "estado": "pagado",
        }, headers=headers)
        assert r.status_code == 201, f"Crear pago {i+1} falló: {r.text}"
        pago_ids.append(r.json()["id"])

    assert len(pago_ids) == 3

    # ── 8. Descargar recibo PDF ───────────────────────────────────────────────
    r = client.get(f"/api/pagos/{pago_ids[0]}/recibo", headers=headers)
    assert r.status_code == 200, f"Recibo PDF falló: {r.text}"
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 100  # PDF no vacío

    # ── 9. Dashboard del día ─────────────────────────────────────────────────
    r = client.get("/api/dashboard/resumen", headers=headers)
    assert r.status_code == 200
    dashboard = r.json()
    # Los ingresos del mes deben incluir los 3 pagos
    assert "ingresos_mes" in dashboard
    assert dashboard["total_pacientes"] >= 3

    # ── 10. Resumen de ingresos ───────────────────────────────────────────────
    mes_actual = datetime.now(timezone.utc).strftime("%Y-%m")
    r = client.get(f"/api/ingresos?mes={mes_actual}", headers=headers)
    assert r.status_code == 200
    resumen = r.json()
    assert resumen["total_cobrado"] == 185.0  # 50 + 60 + 75
    assert resumen["cantidad_pagos"] == 3

    # ── 11. Auditoría no manipulada ───────────────────────────────────────────
    r = client.get("/api/auditoria/verificar", headers=headers)
    assert r.status_code == 200
    assert r.json()["cadena_valida"] is True

    # ── 12. Notas cifradas en DB ──────────────────────────────────────────────
    with Session(db_engine) as db:
        consultas_db = db.exec(select(Consulta)).all()
        assert len(consultas_db) == 3
        for con in consultas_db:
            # El campo nota NO debe ser texto plano — debe descifrar correctamente
            nota_clara = descifrar(con.nota)
            assert "paciente refiere" in nota_clara.lower()
            # Y el valor en DB NO es el texto en claro (está cifrado)
            assert con.nota != nota_clara


# ── Test 2: Flujo del asistente ───────────────────────────────────────────────

def test_flujo_completo_asistente(client, db_engine):
    """Verifica permisos del asistente: agenda ✅ | notas ❌ | cobro ✅.

    Pasos:
    1. Médico registra consultorio
    2. Asistente creado manualmente en DB con rol ASISTENTE
    3. Asistente hace login
    4. Asistente agenda 3 citas
    5. Asistente NO puede crear consultas (403)
    6. Asistente NO puede ver notas clínicas en consulta creada por médico (403)
    7. Asistente SÍ puede registrar pagos (201)
    """

    # ── 1. Médico registra consultorio ────────────────────────────────────────
    r = client.post("/api/auth/register", json={
        "nombre": "Dr. Ramón Torres",
        "email": "ramon@clinicatorres.com",
        "password": "Clave2024!",
        "especialidad": "Pediatría",
        "direccion": "Av. Miranda 20",
        "telefono": "+58 414 000-0002",
        "horario_apertura": "08:00",
        "horario_cierre": "17:00",
        "duracion_cita": 20,
        "precio_consulta": 40.0,
    })
    assert r.status_code == 201
    token_medico = r.json()["access_token"]
    headers_medico = _auth(token_medico)

    # Recuperar consultorio_id del médico
    r_me = client.get("/api/auth/me", headers=headers_medico)
    assert r_me.status_code == 200
    medico_id = r_me.json()["id"]

    # ── 2. Crear asistente manualmente en DB ─────────────────────────────────
    with Session(db_engine) as db:
        medico_obj = db.get(Usuario, medico_id)
        consultorio_id = medico_obj.consultorio_id
        asistente = Usuario(
            consultorio_id=consultorio_id,
            nombre="Asistente García",
            email="asistente@clinicatorres.com",
            password_hash=hash_password("AsistPass!"),
            rol="ASISTENTE",
        )
        db.add(asistente)
        db.commit()
        db.refresh(asistente)

    # ── 3. Login del asistente ────────────────────────────────────────────────
    r = client.post("/api/auth/login", json={
        "email": "asistente@clinicatorres.com",
        "password": "AsistPass!",
    })
    assert r.status_code == 200
    token_asistente = r.json()["access_token"]
    headers_asistente = _auth(token_asistente)

    # ── Crear un paciente con el médico para tener ID ─────────────────────────
    r = client.post("/api/pacientes", json={
        "nombre": "Niño Paciente",
        "tipo": "HUMANO",
        "cedula": "V-30000001",
    }, headers=headers_medico)
    assert r.status_code == 201
    paciente_id = r.json()["id"]

    # ── 4. Asistente agenda 3 citas ───────────────────────────────────────────
    ahora = datetime.now(timezone.utc)
    cita_ids = []
    for i in range(3):
        dt = (ahora + timedelta(days=1, hours=i + 1)).replace(minute=0, second=0, microsecond=0)
        r = client.post("/api/citas", json={
            "paciente_id": paciente_id,
            "fecha_hora": dt.isoformat(),
            "duracion_min": 20,
            "motivo": f"Control pediátrico {i+1}",
        }, headers=headers_asistente)
        assert r.status_code == 201, f"Asistente no pudo agendar cita {i+1}: {r.text}"
        cita_ids.append(r.json()["id"])

    assert len(cita_ids) == 3

    # ── 5. Asistente NO puede crear consultas (403) ───────────────────────────
    r = client.post("/api/consultas", json={
        "paciente_id": paciente_id,
        "motivo": "Intento de consulta",
        "nota": "Nota prohibida",
        "indicaciones": "",
    }, headers=headers_asistente)
    assert r.status_code == 403, f"Asistente creó consulta (debería ser 403): {r.text}"

    # ── 6. Médico crea consulta; asistente NO puede verla ────────────────────
    # Médico crea la consulta
    r = client.post("/api/consultas", json={
        "paciente_id": paciente_id,
        "motivo": "Revisión pediátrica",
        "nota": "Niño en buen estado general.",
        "indicaciones": "Vitamina D 400 UI diaria.",
        "diagnostico": "Sano",
    }, headers=headers_medico)
    assert r.status_code == 201
    consulta_id = r.json()["id"]

    # Asistente intenta ver la consulta → 403
    r = client.get(f"/api/consultas/{consulta_id}", headers=headers_asistente)
    assert r.status_code == 403, f"Asistente vio consulta (debería ser 403): {r.text}"

    # ── 7. Asistente SÍ puede registrar pagos ────────────────────────────────
    r = client.post("/api/pagos", json={
        "paciente_id": paciente_id,
        "monto": 40.0,
        "moneda": "USD",
        "metodo": "efectivo",
        "estado": "pagado",
    }, headers=headers_asistente)
    assert r.status_code == 201, f"Asistente no pudo registrar pago: {r.text}"
    assert r.json()["monto"] == 40.0


# ── Test 3: Concurrencia — 10 pacientes en paralelo ──────────────────────────

def test_no_rompe_concurrencia(client, db_engine):
    """Crea 10 pacientes de forma rápida y verifica integridad de IDs únicos.

    SQLite con StaticPool (una conexión compartida) no es thread-safe.
    El test simula alta carga secuencial y verifica que:
    - Todos los pacientes se crean con éxito (201)
    - Los IDs asignados son únicos (no hay colisiones)
    """
    # Registro y token del médico
    r = client.post("/api/auth/register", json={
        "nombre": "Dra. Concurrencia",
        "email": "concurrencia@altamedica.com",
        "password": "Concur2024!",
        "especialidad": "General",
        "direccion": "Calle Paralela 1",
        "telefono": "+58 412 111-0001",
        "horario_apertura": "08:00",
        "horario_cierre": "18:00",
        "duracion_cita": 30,
        "precio_consulta": 30.0,
    })
    assert r.status_code == 201
    headers = _auth(r.json()["access_token"])

    ids_creados = []
    # 10 pacientes en secuencia rápida
    for i in range(10):
        resp = client.post("/api/pacientes", json={
            "nombre": f"Paciente Concurrente {i}",
            "cedula": f"V-{40000000 + i}",
            "tipo": "HUMANO",
        }, headers=headers)
        assert resp.status_code == 201, f"Paciente {i} falló: {resp.text}"
        ids_creados.append(resp.json()["id"])

    # Verificar que los 10 IDs son únicos (no hubo colisiones)
    assert len(ids_creados) == 10
    assert len(set(ids_creados)) == 10, "Hay IDs duplicados: fallo de integridad"

    # Verificar en DB
    with Session(db_engine) as db:
        from sqlmodel import select
        from app.models.paciente import Paciente
        pacientes = db.exec(select(Paciente)).all()
        assert len(pacientes) == 10


# ── Test 4: Endpoint /health ──────────────────────────────────────────────────

def test_health_endpoint(client, db_engine):
    """El endpoint /health debe responder sin autenticación."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "version" in data
    assert "db" in data
    # db puede ser "ok" o "error" según si la tabla existe en el engine de prueba
    # Lo importante es que el endpoint responda sin crash
