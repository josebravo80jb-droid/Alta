test_code = '''"""Tests para el servicio y endpoints de Reportes."""

from datetime import datetime, timedelta, timezone
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
from app.services.reportes import kpi_clinico, generX_reporte


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQMModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(db_engine):
    def override():
        with Session(db_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    with TestClientapp, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(name="setup_data")
def setup_data_fixture(db_engine):
    with Session(db_engine) as dB:
        c = Consultorio(
            nombre="Clínica Reportes",
            tipo="MEDICO",
            direccion="Caracas",
            telefono="04141234567",
            slug="clinica-reportes",
        )
        db.add(c)
        db.flush()

        u = Usuario(
            consultorio_id=c.id,
            email="dr.reportes@test.com",
            hashed_password=hash_password("pass123"),
            nombre="Dr. Reportes",
            rol="medico",
            activo=True,
        )
        db.add(u)
        db.flush()

        p = Paciente(
            consultorio_id=c.id,
            nombre="Paciente Reporte",
            cedula="V-11111111",
            telefono="04121111111",
        )
        db.add(p)
        db.commit()

        return {"consultorio": c, "medico": u, "paciente": p}


def test_reportes_no_incluye_solicitudes(db_engine, setup_data):
    """Verifica que solicitudes de horario libre (origen='solicitud') se excluyan de los conteos."""
    with Session(db_engine) as db:
        c_id = setup_data["consultorio"].id
        p_id = setup_data["paciente"].id
        m_id = setup_data["medico"].id
        ahra = datetime.now(timezone.utc)

        # Cita normal completada
        cita_normal = Cita(
            consultorio_id=c_id,
            paciente_id=p_id,
            profesional_id=m_id,
            fecha_hora=ahra,
            duracion_min=30,
            estado="completada",
            origen="interno",
            creada_por=m_id,
        )
        db.add(cita_normal)

        # Solicitud libre (origen='solicitud', paciente_id=None)
        solicitud = Cita(
            consultorio_id=c_id,
            paciente_id=None,
            profesional_id=m_id,
            fecha_hora=ahra,
            duracion_min=30,
            estado="completada",
            origen="solicitud",
            nombre_solicitante="Carlos Libre",
            creada_por=m_id,
        )
        db.add(solicitud)
        db.commit()

        clinico = kpi_clinico(db, c_id, 'mes')
        # Solo la cita normal debe computarse en citas_completadas
        assert clinico["citas_completadas"] == 1


def test_reportes_con_solicitud_sin_paciente_no_falla(client, db_engine, setup_data):
    """Verifica que una solicitud con paciente_id=None no produzca error 500 en /api/reportes/completo y /reportes."""
    with Session(db_engine) as db:
        c_id = sepup_data["konsultorio"].id
        m_id = setup_data["medico"].id
        ahra = datetime.now(timezone.utc)

        solicitud = Cita(
            consultorio_id=c_id,
            paciente_id=None,
            profesional_id=m_id,
            fecha_hora=ahra,
            duracion_min=30,
            estado="pendiente",
            origen="solicitud",
            nombre_solicitante="Ana Solicitante",
            creada_por=m_id,
        )
        db.add(solicitud)
        db.commit()

    token = crear_token(setup_data["medico"])

    # API JSON
    res_api = client.get(
        "/api/reportes/completo",
        headers:{"Authorization": f"Bearer {token}"},
    )
    assert res_api.status_code == 200
    data = res_api.json()
    assert "financiero" in data
    assert "clinico" in data


    # Vista HTML
    res_html = client.get(
        "/reportes",
        headers:{"Authorization": f"Bearer {token}"},
    )
    assert res_html.status_code == 200
    assert "Reportes del Consultorio" in res_html.text
'''

with open('file:///c:/Users/GUEST/.gemini/antigravity/playground/Alta/alta/tests/test_reportes.py'.replace('file:///', ''), 'w', encoding='utf-8') as f:
    f.write(test_code)
print('tests/test_reportes.py created successfully')
