"""Tests del Módulo 10: Modo Demo — cargar, borrar y verificar integridad de datos reales."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401 — registra tablas en SQLModel.metadata
from app.database import get_session
from app.main import app
from app.models.cita import Cita
from app.models.configuracion import Configuracion
from app.models.consulta import Consulta
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password


# ── Fixtures ──────────────────────────────────────────────────────────────────

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
    """TestClient con override de la sesión de BD."""
    def override():
        with Session(db_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(name="setup")
def setup_fixture(db_engine):
    """Crea consultorio, médico y 2 pacientes REALES (demo=False)."""
    with Session(db_engine) as db:
        c = Consultorio(
            nombre="Clínica Demo Test",
            tipo="MEDICO",
            direccion="Av. Principal 1",
            telefono="+58 412 555-0001",
        )
        db.add(c)
        db.flush()

        cfg = Configuracion(consultorio_id=c.id, moneda="USD")
        db.add(cfg)

        medico = Usuario(
            consultorio_id=c.id,
            nombre="Dr. Real",
            email="medico@demo.test",
            password_hash=hash_password("secret"),
            rol="MEDICO",
        )
        db.add(medico)
        db.flush()

        asistente = Usuario(
            consultorio_id=c.id,
            nombre="Asistente",
            email="asistente@demo.test",
            password_hash=hash_password("secret"),
            rol="ASISTENTE",
        )
        db.add(asistente)
        db.flush()

        # 2 pacientes reales (demo=False)
        for i in range(2):
            p = Paciente(
                consultorio_id=c.id,
                tipo="HUMANO",
                nombre=f"Paciente Real {i+1}",
                cedula=f"V-{10000000 + i}",
                demo=False,
            )
            db.add(p)

        db.commit()
        db.refresh(medico)
        db.refresh(asistente)
        db.refresh(c)

    return {
        "consultorio_id": c.id,
        "medico": medico,
        "asistente": asistente,
    }


@pytest.fixture(name="token_medico")
def token_medico_fixture(setup):
    return crear_token(setup["medico"])


@pytest.fixture(name="token_asistente")
def token_asistente_fixture(setup):
    return crear_token(setup["asistente"])


# ── Tests: GET /api/demo/estado ───────────────────────────────────────────────

class TestEstadoDemo:
    def test_estado_inicial_sin_demo(self, client, setup, token_medico):
        """Estado inicial debe indicar demo_activo=False con todos los conteos en 0."""
        r = client.get(
            "/api/demo/estado",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["demo_activo"] is False
        assert data["conteos"]["pacientes"] == 0
        assert data["conteos"]["citas"] == 0
        assert data["conteos"]["consultas"] == 0
        assert data["conteos"]["pagos"] == 0

    def test_estado_sin_autenticacion(self, client, setup):
        """Sin token debe retornar 401."""
        r = client.get("/api/demo/estado")
        assert r.status_code == 401


# ── Tests: POST /api/demo/cargar ─────────────────────────────────────────────

class TestCargarDemo:
    def test_cargar_genera_registros_correctos(self, client, setup, token_medico):
        """Debe generar 20 pacientes, 50 citas, 30 consultas y 15 pagos."""
        r = client.post(
            "/api/demo/cargar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        assert r.status_code == 201
        data = r.json()
        g = data["generados"]
        assert g["pacientes"] == 20
        assert g["citas"] == 50
        assert g["consultas"] == 30
        assert g["pagos"] == 15

    def test_cargar_marca_demo_true(self, client, setup, token_medico, db_engine):
        """Todos los registros generados deben tener demo=True."""
        client.post(
            "/api/demo/cargar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        with Session(db_engine) as db:
            pacientes_demo = db.exec(
                select(Paciente).where(Paciente.demo == True)
            ).all()
            citas_demo = db.exec(select(Cita).where(Cita.demo == True)).all()
            consultas_demo = db.exec(select(Consulta).where(Consulta.demo == True)).all()
            pagos_demo = db.exec(select(Pago).where(Pago.demo == True)).all()

        assert len(pacientes_demo) == 20
        assert len(citas_demo) == 50
        assert len(consultas_demo) == 30
        assert len(pagos_demo) == 15

    def test_cargar_no_toca_pacientes_reales(self, client, setup, token_medico, db_engine):
        """Los 2 pacientes reales (demo=False) no deben ser modificados."""
        client.post(
            "/api/demo/cargar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        with Session(db_engine) as db:
            reales = db.exec(
                select(Paciente).where(Paciente.demo == False)
            ).all()
        # Deben seguir siendo exactamente 2 reales
        assert len(reales) == 2

    def test_cargar_estado_activo_despues(self, client, setup, token_medico):
        """Después de cargar, /estado debe retornar demo_activo=True."""
        client.post(
            "/api/demo/cargar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        r = client.get(
            "/api/demo/estado",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        assert r.status_code == 200
        assert r.json()["demo_activo"] is True

    def test_cargar_requiere_rol_medico(self, client, setup, token_asistente):
        """El asistente no debe poder cargar datos demo (403)."""
        r = client.post(
            "/api/demo/cargar",
            headers={"Authorization": f"Bearer {token_asistente}"},
        )
        assert r.status_code == 403

    def test_cargar_sin_autenticacion(self, client, setup):
        """Sin token debe retornar 401."""
        r = client.post("/api/demo/cargar")
        assert r.status_code == 401


# ── Tests: DELETE /api/demo/borrar ───────────────────────────────────────────

class TestBorrarDemo:
    def test_borrar_elimina_solo_demo(self, client, setup, token_medico, db_engine):
        """Borrar debe eliminar TODOS los demo=True y dejar intactos los reales."""
        # Cargar demo primero
        client.post(
            "/api/demo/cargar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        # Borrar
        r = client.delete(
            "/api/demo/borrar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        assert r.status_code == 200
        data = r.json()
        e = data["eliminados"]
        assert e["pacientes"] == 20
        assert e["citas"] == 50
        assert e["consultas"] == 30
        assert e["pagos"] == 15

    def test_borrar_preserva_pacientes_reales(self, client, setup, token_medico, db_engine):
        """Los 2 pacientes reales deben sobrevivir al borrado de demo."""
        client.post(
            "/api/demo/cargar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        client.delete(
            "/api/demo/borrar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        with Session(db_engine) as db:
            reales = db.exec(
                select(Paciente).where(Paciente.demo == False)
            ).all()
            demo = db.exec(
                select(Paciente).where(Paciente.demo == True)
            ).all()

        assert len(reales) == 2  # intactos
        assert len(demo) == 0   # todos borrados

    def test_borrar_estado_inactivo_despues(self, client, setup, token_medico):
        """Tras borrar, /estado debe retornar demo_activo=False."""
        client.post(
            "/api/demo/cargar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        client.delete(
            "/api/demo/borrar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        r = client.get(
            "/api/demo/estado",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        assert r.json()["demo_activo"] is False

    def test_borrar_sin_datos_es_idempotente(self, client, setup, token_medico):
        """Borrar sin datos previos no debe fallar; devuelve todos los conteos en 0."""
        r = client.delete(
            "/api/demo/borrar",
            headers={"Authorization": f"Bearer {token_medico}"},
        )
        assert r.status_code == 200
        e = r.json()["eliminados"]
        assert e["pacientes"] == 0
        assert e["citas"] == 0

    def test_borrar_requiere_rol_medico(self, client, setup, token_asistente):
        """El asistente no debe poder borrar datos demo (403)."""
        r = client.delete(
            "/api/demo/borrar",
            headers={"Authorization": f"Bearer {token_asistente}"},
        )
        assert r.status_code == 403

    def test_borrar_sin_autenticacion(self, client, setup):
        """Sin token debe retornar 401."""
        r = client.delete("/api/demo/borrar")
        assert r.status_code == 401


# ── Test: ciclo completo cargar → borrar → reales intactos ───────────────────

def test_ciclo_completo(client, setup, token_medico, db_engine):
    """Ciclo completo: cargar → verificar → borrar → verificar reales intactos."""
    # Estado inicial: 0 demo, 2 reales
    with Session(db_engine) as db:
        assert db.exec(select(Paciente).where(Paciente.demo == False)).all().__len__() == 2

    # Cargar
    r = client.post("/api/demo/cargar", headers={"Authorization": f"Bearer {token_medico}"})
    assert r.status_code == 201

    # 22 pacientes totales: 2 reales + 20 demo
    with Session(db_engine) as db:
        todos = db.exec(select(Paciente)).all()
        assert len(todos) == 22

    # Borrar
    r = client.delete("/api/demo/borrar", headers={"Authorization": f"Bearer {token_medico}"})
    assert r.status_code == 200

    # Exactamente 2 reales — los demo desaparecieron
    with Session(db_engine) as db:
        todos = db.exec(select(Paciente)).all()
        assert len(todos) == 2
        for p in todos:
            assert p.demo is False
