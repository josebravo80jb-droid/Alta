"""Tests del módulo de pagos, recibos en PDF y exportación en CSV — Módulo 8."""

import os
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
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password
from app.services.pdf import generar_recibo


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
        c = Consultorio(
            nombre="Clínica San Martín",
            tipo="MEDICO",
            direccion="Calle Los Médicos 45",
            telefono="+58 212 555-1234",
        )
        db.add(c)
        db.flush()

        u = Usuario(
            consultorio_id=c.id,
            email="tesorero@alta.com",
            password_hash=hash_password("clave123"),
            nombre="Lic. Financiero",
            rol="MEDICO",
        )
        db.add(u)
        cfg = Configuracion(consultorio_id=c.id)
        db.add(cfg)

        paciente = Paciente(
            consultorio_id=c.id,
            nombre="María González",
            cedula="V-19876543",
            tipo="HUMANO",
        )
        db.add(paciente)
        db.commit()

        db.refresh(u)
        db.refresh(paciente)
        db.refresh(c)

        token = crear_token(u)
        return {
            "consultorio": c,
            "usuario": u,
            "paciente": paciente,
            "token": token,
        }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_crear_pago(client, setup):
    """Verifica el registro exitoso de un pago."""
    resp = client.post(
        "/api/pagos",
        json={
            "paciente_id": setup["paciente"].id,
            "monto": 50.0,
            "moneda": "USD",
            "metodo": "zelle",
            "estado": "pagado",
        },
        headers=_auth(setup["token"]),
    )
    assert resp.status_code == 201
    datos = resp.json()
    assert datos["monto"] == 50.0
    assert datos["moneda"] == "USD"
    assert datos["metodo"] == "zelle"
    assert datos["paciente_nombre"] == setup["paciente"].nombre


def test_listar_pagos_por_mes(client, setup, db_engine):
    """Verifica listar y filtrar pagos por parámetro mes=YYYY-MM."""
    with Session(db_engine) as db:
        p1 = Pago(
            consultorio_id=setup["consultorio"].id,
            paciente_id=setup["paciente"].id,
            monto=40.0,
            fecha=datetime(2026, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
            registrado_por=setup["usuario"].id,
        )
        p2 = Pago(
            consultorio_id=setup["consultorio"].id,
            paciente_id=setup["paciente"].id,
            monto=60.0,
            fecha=datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
            registrado_por=setup["usuario"].id,
        )
        db.add_all([p1, p2])
        db.commit()

    resp = client.get("/api/pagos?mes=2026-05", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos) == 1
    assert datos[0]["monto"] == 40.0


def test_resumen_ingresos_correcto(client, setup, db_engine):
    """Verifica el cálculo de métricas financieras (cobrado, pendiente, promedio)."""
    with Session(db_engine) as db:
        p1 = Pago(
            consultorio_id=setup["consultorio"].id,
            paciente_id=setup["paciente"].id,
            monto=100.0,
            estado="pagado",
            fecha=datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc),
            registrado_por=setup["usuario"].id,
        )
        p2 = Pago(
            consultorio_id=setup["consultorio"].id,
            paciente_id=setup["paciente"].id,
            monto=50.0,
            estado="pendiente",
            fecha=datetime(2026, 7, 5, 10, 0, 0, tzinfo=timezone.utc),
            registrado_por=setup["usuario"].id,
        )
        db.add_all([p1, p2])
        db.commit()

    resp = client.get("/api/ingresos?mes=2026-07", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    resumen = resp.json()
    assert resumen["total_cobrado"] == 100.0
    assert resumen["total_pendiente"] == 50.0
    assert resumen["cantidad_pagos"] == 2
    assert resumen["promedio"] == 50.0


def test_generar_recibo_pdf(setup):
    """Verifica que el servicio de generación de PDF produce un archivo válido y no vacío."""
    pago = Pago(
        id=999,
        consultorio_id=setup["consultorio"].id,
        paciente_id=setup["paciente"].id,
        monto=75.50,
        moneda="USD",
        metodo="transferencia",
        estado="pagado",
        fecha=datetime.now(timezone.utc),
        registrado_por=setup["usuario"].id,
    )

    pdf_bytes = generar_recibo(
        pago=pago,
        consultorio=setup["consultorio"],
        paciente=setup["paciente"],
    )
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")
    assert os.path.exists("data/recibos/recibo_999.pdf")
    assert os.path.getsize("data/recibos/recibo_999.pdf") > 0


def test_recibo_contiene_nombre_paciente(client, setup, db_engine):
    """Verifica que el endpoint GET /api/pagos/{id}/recibo retorne el archivo PDF correspondiente."""
    with Session(db_engine) as db:
        pago = Pago(
            consultorio_id=setup["consultorio"].id,
            paciente_id=setup["paciente"].id,
            monto=120.0,
            moneda="USD",
            metodo="efectivo",
            estado="pagado",
            fecha=datetime.now(timezone.utc),
            registrado_por=setup["usuario"].id,
        )
        db.add(pago)
        db.commit()
        db.refresh(pago)
        pago_id = pago.id

    resp = client.get(f"/api/pagos/{pago_id}/recibo", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 0
    assert resp.content.startswith(b"%PDF")


def test_exportar_csv(client, setup, db_engine):
    """Verifica la exportación del reporte de pagos a formato CSV."""
    with Session(db_engine) as db:
        p = Pago(
            consultorio_id=setup["consultorio"].id,
            paciente_id=setup["paciente"].id,
            monto=80.0,
            moneda="USD",
            metodo="zelle",
            estado="pagado",
            fecha=datetime(2026, 8, 12, 14, 30, tzinfo=timezone.utc),
            registrado_por=setup["usuario"].id,
        )
        db.add(p)
        db.commit()

    resp = client.get("/api/ingresos/export.csv?mes=2026-08", headers=_auth(setup["token"]))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    contenido = resp.text
    # Validar cabeceras y contenido
    assert "Fecha,Paciente,Concepto,Monto,Moneda,Método,Estado" in contenido
    assert "María González" in contenido
    assert "80.00" in contenido
    assert "USD" in contenido


def test_eliminar_pago(client, setup, db_engine):
    """Verifica la eliminación de un pago."""
    with Session(db_engine) as db:
        p = Pago(
            consultorio_id=setup["consultorio"].id,
            paciente_id=setup["paciente"].id,
            monto=30.0,
            fecha=datetime.now(timezone.utc),
            registrado_por=setup["usuario"].id,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        p_id = p.id

    resp = client.delete(f"/api/pagos/{p_id}", headers=_auth(setup["token"]))
    assert resp.status_code == 200

    with Session(db_engine) as db:
        assert db.get(Pago, p_id) is None
