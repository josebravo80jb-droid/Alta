"""Tests del Modo Demo en consultorios veterinarios (AltaPet) y regresión humana."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.cita import Cita
from app.models.configuracion import Configuracion
from app.models.consulta import Consulta
from app.models.consultorio import Consultorio
from app.models.dueno import Dueno
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.models.vacuna import Vacuna
from app.services.auth import crear_token, hash_password
from app.services.demo import (
    _MOTIVOS_CITAS_VET,
    borrar_datos_demo,
    contar_datos_demo,
    generar_datos_demo,
)


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


@pytest.fixture(name="setup_vet")
def setup_vet_fixture(db_engine):
    """Crea consultorio VETERINARIO, veterinario y 1 paciente real (demo=False)."""
    with Session(db_engine) as db:
        c = Consultorio(
            nombre="AltaPet Centro Veterinario",
            tipo="VETERINARIO",
            direccion="Av. Los Animales 123",
            telefono="04121234567",
        )
        db.add(c)
        db.flush()

        cfg = Configuracion(consultorio_id=c.id, moneda="USD")
        db.add(cfg)

        vet = Usuario(
            consultorio_id=c.id,
            nombre="Dra. Veterinaria",
            email="vet@altapet.com",
            password_hash=hash_password("clave123"),
            rol="MEDICO",
        )
        db.add(vet)
        db.flush()

        # Dueno real y Mascota real (demo=False)
        dueno_real = Dueno(
            consultorio_id=c.id,
            nombre="Propietario Real",
            telefono="04149999999",
            demo=False,
        )
        db.add(dueno_real)
        db.flush()

        mascota_real = Paciente(
            consultorio_id=c.id,
            tipo="MASCOTA",
            nombre="Firulais Real",
            especie="perro",
            raza="Pastor Alemán",
            dueno_id=dueno_real.id,
            demo=False,
        )
        db.add(mascota_real)
        db.commit()
        db.refresh(c)
        db.refresh(vet)
        db.refresh(dueno_real)
        db.refresh(mascota_real)

    return {
        "consultorio_id": c.id,
        "usuario_id": vet.id,
        "token": crear_token(vet),
        "mascota_real_id": mascota_real.id,
        "dueno_real_id": dueno_real.id,
    }


def test_demo_veterinario_no_genera_humanos(db_engine, setup_vet):
    with Session(db_engine) as db:
        generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        humanos_demo = db.exec(
            select(Paciente).where(
                Paciente.consultorio_id == setup_vet["consultorio_id"],
                Paciente.tipo == "HUMANO",
                Paciente.demo == True,
            )
        ).all()
        assert len(humanos_demo) == 0


def test_demo_veterinario_genera_20_duenos(db_engine, setup_vet):
    with Session(db_engine) as db:
        res = generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        assert res["duenos"] == 20
        duenos = db.exec(
            select(Dueno).where(
                Dueno.consultorio_id == setup_vet["consultorio_id"],
                Dueno.demo == True,
            )
        ).all()
        assert len(duenos) == 20
        for d in duenos:
            assert d.nombre is not None
            assert d.cedula.startswith("V-")


def test_demo_veterinario_genera_20_mascotas(db_engine, setup_vet):
    with Session(db_engine) as db:
        generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        mascotas = db.exec(
            select(Paciente).where(
                Paciente.consultorio_id == setup_vet["consultorio_id"],
                Paciente.tipo == "MASCOTA",
                Paciente.demo == True,
            )
        ).all()
        assert len(mascotas) == 20


def test_demo_veterinario_mascotas_tienen_especie_y_raza(db_engine, setup_vet):
    with Session(db_engine) as db:
        generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        mascotas = db.exec(
            select(Paciente).where(
                Paciente.consultorio_id == setup_vet["consultorio_id"],
                Paciente.demo == True,
            )
        ).all()
        for m in mascotas:
            assert m.especie in ["perro", "gato", "conejo", "ave", "roedor"]
            assert m.raza is not None and len(m.raza) > 0
            assert m.peso_kg is not None and m.peso_kg > 0
            assert m.microchip is not None and len(m.microchip) == 15


def test_demo_veterinario_mascotas_tienen_dueno(db_engine, setup_vet):
    with Session(db_engine) as db:
        generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        mascotas = db.exec(
            select(Paciente).where(
                Paciente.consultorio_id == setup_vet["consultorio_id"],
                Paciente.demo == True,
            )
        ).all()
        for m in mascotas:
            assert m.dueno_id is not None
            dueno = db.get(Dueno, m.dueno_id)
            assert dueno is not None
            assert dueno.demo is True


def test_demo_veterinario_genera_vacunas(db_engine, setup_vet):
    with Session(db_engine) as db:
        res = generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        assert res["vacunas"] > 0
        vacunas = db.exec(
            select(Vacuna).where(
                Vacuna.consultorio_id == setup_vet["consultorio_id"],
                Vacuna.demo == True,
            )
        ).all()
        assert len(vacunas) >= 30
        for v in vacunas:
            assert v.paciente_id is not None
            assert v.tipo in ["moquillo", "parvovirus", "rabia", "triple felina", "leucemia felina", "mixomatosis", "vhd"]


def test_demo_veterinario_motivos_son_veterinarios(db_engine, setup_vet):
    with Session(db_engine) as db:
        generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        citas = db.exec(
            select(Cita).where(
                Cita.consultorio_id == setup_vet["consultorio_id"],
                Cita.demo == True,
            )
        ).all()
        assert len(citas) == 50
        for c in citas:
            assert c.motivo in _MOTIVOS_CITAS_VET


def test_demo_humano_sigue_funcionando(db_engine):
    """Regresión: consultorio médico genera pacientes tipo HUMANO."""
    with Session(db_engine) as db:
        c_hum = Consultorio(
            nombre="Consultorio Médico Humano",
            tipo="MEDICO",
            direccion="Calle Salud 1",
            telefono="04127778899",
        )
        db.add(c_hum)
        db.flush()

        doc = Usuario(
            consultorio_id=c_hum.id,
            nombre="Dr. Medicina",
            email="doc@med.com",
            password_hash=hash_password("clave123"),
            rol="MEDICO",
        )
        db.add(doc)
        db.flush()

        res = generar_datos_demo(db, c_hum.id, doc.id)
        assert res["pacientes"] == 20
        assert res["citas"] == 50
        assert res["consultas"] == 30
        assert res["pagos"] == 15

        pacs = db.exec(
            select(Paciente).where(
                Paciente.consultorio_id == c_hum.id,
                Paciente.demo == True,
            )
        ).all()
        assert len(pacs) == 20
        for p in pacs:
            assert p.tipo == "HUMANO"
            assert p.cedula.startswith("V-")


def test_borrar_demo_veterinario_borra_todo(db_engine, setup_vet):
    with Session(db_engine) as db:
        generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        borrados = borrar_datos_demo(db, setup_vet["consultorio_id"])
        assert borrados["pacientes"] == 20
        assert borrados["duenos"] == 20
        assert borrados["vacunas"] > 0
        assert borrados["citas"] == 50
        assert borrados["consultas"] == 30
        assert borrados["pagos"] == 15

        conteo = contar_datos_demo(db, setup_vet["consultorio_id"])
        assert conteo["total"] == 0


def test_borrar_demo_veterinario_no_toca_reales(db_engine, setup_vet):
    with Session(db_engine) as db:
        generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        borrar_datos_demo(db, setup_vet["consultorio_id"])

        # Mascota y dueño reales deben seguir existiendo
        m_real = db.get(Paciente, setup_vet["mascota_real_id"])
        d_real = db.get(Dueno, setup_vet["dueno_real_id"])
        assert m_real is not None
        assert m_real.demo is False
        assert d_real is not None
        assert d_real.demo is False


def test_contar_demo_veterinario_cuenta_correcto(db_engine, setup_vet):
    with Session(db_engine) as db:
        generar_datos_demo(db, setup_vet["consultorio_id"], setup_vet["usuario_id"])
        c = contar_datos_demo(db, setup_vet["consultorio_id"])
        assert c["pacientes"] == 20
        assert c["mascotas"] == 20
        assert c["duenos"] == 20
        assert c["citas"] == 50
        assert c["consultas"] == 30
        assert c["pagos"] == 15
        assert c["vacunas"] >= 30
        assert c["total"] > 100
