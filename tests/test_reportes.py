"""Tests para el servicio y endpoints de Reportes."""

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
from app.services.reportes import kpi_clinico, generar_reporte


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
    """Retorna IDs enteros para evitar DetachedInstanceError fuera de sesión."""
    with Session(db_engine) as db:
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
            password_hash=hash_password("pass123"),
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

        # Extraer IDs dentro de la sesión antes de cerrarla
        return {
            "consultorio_id": c.id,
            "medico_id": u.id,
            "medico_email": u.email,
            "paciente_id": p.id,
        }



def test_reportes_no_incluye_solicitudes(db_engine, setup_data):
    """Verifica que solicitudes de horario libre (origen=solicitud) se excluyan de los conteos."""
    c_id = setup_data["consultorio_id"]
    p_id = setup_data["paciente_id"]
    m_id = setup_data["medico_id"]
    ahra = datetime.now(timezone.utc)

    with Session(db_engine) as db:
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

        # Solicitud libre (origen=solicitud, paciente_id=None)
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

        clinico = kpi_clinico(db, c_id, "mes")
        # Solo la cita normal debe computarse en citas_completadas
        assert clinico["citas_completadas"] == 1


def test_reportes_con_solicitud_sin_paciente_no_falla(client, db_engine, setup_data):
    """Verifica que una solicitud con paciente_id=None no produzca error 500 en /api/reportes/completo y /reportes."""
    c_id = setup_data["consultorio_id"]
    m_id = setup_data["medico_id"]
    ahra = datetime.now(timezone.utc)

    with Session(db_engine) as db:
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

    # Obtener medico desde DB para generar token válido
    from app.models.usuario import Usuario as UsuarioModel
    with Session(db_engine) as db:
        medico = db.get(UsuarioModel, m_id)
        token = crear_token(medico)

    # API JSON
    res_api = client.get(
        "/api/reportes/completo",
        headers={"Authorization": "Bearer " + token},
    )
    assert res_api.status_code == 200
    data = res_api.json()
    assert "financiero" in data
    assert "clinico" in data

    # Vista HTML
    res_html = client.get(
        "/reportes",
        headers={"Authorization": "Bearer " + token},
    )
    assert res_html.status_code == 200
    assert "Reportes del Consultorio" in res_html.text


def test_demografia_medico_no_menciona_mascotas(client, db_engine, setup_data):
    """En consultorio tipo MEDICO, /reportes no debe mostrar tarjetas ni texto sobre mascotas."""
    m_id = setup_data["medico_id"]

    from app.models.usuario import Usuario as UsuarioModel
    with Session(db_engine) as db:
        medico = db.get(UsuarioModel, m_id)
        token = crear_token(medico)

    res = client.get("/reportes", headers={"Authorization": "Bearer " + token})
    assert res.status_code == 200
    html = res.text

    # El consultorio del fixture es tipo MEDICO (no VETERINARIO):
    # - No debe aparecer la tarjeta KPI de "Mascotas"
    # - No debe aparecer "Mascotas por especie"
    # - No debe aparecer "No hay mascotas registradas"
    assert 'kpi-label">Mascotas<' not in html
    assert "Mascotas por especie" not in html
    assert "No hay mascotas registradas" not in html
    # La sección demografía sí debe existir
    assert "Demograf" in html
