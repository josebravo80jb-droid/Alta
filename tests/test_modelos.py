"""Tests básicos de creación y relaciones de los modelos del Módulo 3."""

from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401 — registra TODOS los modelos antes de create_all
from app.models.cita import Cita
from app.models.consulta import Consulta
from app.models.consultorio import Consultorio
from app.models.dueno import Dueno
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.services.auth import hash_password

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(name="session")
def session_fixture():
    """Sesión SQLite en memoria, aislada por test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="consultorio")
def consultorio_fixture(session):
    """Consultorio base reutilizable."""
    c = Consultorio(nombre="Test", tipo="MEDICO", direccion="Calle 1", telefono="555")
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@pytest.fixture(name="usuario")
def usuario_fixture(session, consultorio):
    """Usuario médico reutilizable."""
    u = Usuario(
        consultorio_id=consultorio.id,
        email="medico@test.com",
        password_hash=hash_password("pwd"),
        nombre="Dr. Test",
        rol="MEDICO",
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_crear_paciente_humano(session, consultorio):
    """Paciente HUMANO se crea y recupera correctamente."""
    p = Paciente(
        consultorio_id=consultorio.id,
        tipo="HUMANO",
        nombre="Juan Pérez",
        telefono="555-0001",
        cedula="12345678",
    )
    session.add(p)
    session.commit()
    session.refresh(p)

    recuperado = session.get(Paciente, p.id)
    assert recuperado is not None
    assert recuperado.nombre == "Juan Pérez"
    assert recuperado.tipo == "HUMANO"
    assert recuperado.especie is None  # campo de mascota vacío


def test_crear_paciente_mascota(session, consultorio):
    """Paciente MASCOTA se crea con dueno y campos específicos."""
    # Crear dueño primero
    dueno = Dueno(
        consultorio_id=consultorio.id,
        nombre="Carlos López",
        telefono="555-0002",
    )
    session.add(dueno)
    session.commit()
    session.refresh(dueno)

    mascota = Paciente(
        consultorio_id=consultorio.id,
        tipo="MASCOTA",
        nombre="Firulais",
        especie="Perro",
        raza="Labrador",
        peso_kg=25.5,
        dueno_id=dueno.id,
    )
    session.add(mascota)
    session.commit()
    session.refresh(mascota)

    recuperado = session.get(Paciente, mascota.id)
    assert recuperado is not None
    assert recuperado.tipo == "MASCOTA"
    assert recuperado.especie == "Perro"
    assert recuperado.dueno_id == dueno.id
    assert recuperado.peso_kg == 25.5


def test_crear_cita(session, consultorio, usuario):
    """Cita se crea con estado 'pendiente' por defecto."""
    paciente = Paciente(
        consultorio_id=consultorio.id, nombre="Ana García", tipo="HUMANO"
    )
    session.add(paciente)
    session.commit()
    session.refresh(paciente)

    cita = Cita(
        consultorio_id=consultorio.id,
        paciente_id=paciente.id,
        profesional_id=usuario.id,
        fecha_hora=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
        creada_por=usuario.id,
        motivo="Control",
    )
    session.add(cita)
    session.commit()
    session.refresh(cita)

    recuperada = session.get(Cita, cita.id)
    assert recuperada is not None
    assert recuperada.estado == "pendiente"
    assert recuperada.duracion_min == 30
    assert recuperada.paciente_id == paciente.id


def test_crear_consulta(session, consultorio, usuario):
    """Consulta clínica se crea y vincula a paciente y profesional."""
    paciente = Paciente(
        consultorio_id=consultorio.id, nombre="Pedro Ruiz", tipo="HUMANO"
    )
    session.add(paciente)
    session.commit()
    session.refresh(paciente)

    consulta = Consulta(
        consultorio_id=consultorio.id,
        paciente_id=paciente.id,
        profesional_id=usuario.id,
        fecha=datetime.now(timezone.utc),
        motivo="Dolor de cabeza",
        nota="Cefalea tensional leve",
        indicaciones="Ibuprofeno 400mg c/8h",
    )
    session.add(consulta)
    session.commit()
    session.refresh(consulta)

    recuperada = session.get(Consulta, consulta.id)
    assert recuperada is not None
    assert recuperada.motivo == "Dolor de cabeza"
    assert recuperada.diagnostico is None
    assert recuperada.cita_id is None


def test_crear_pago(session, consultorio, usuario):
    """Pago se crea con estado 'pagado' por defecto."""
    paciente = Paciente(
        consultorio_id=consultorio.id, nombre="Laura Soto", tipo="HUMANO"
    )
    session.add(paciente)
    session.commit()
    session.refresh(paciente)

    pago = Pago(
        consultorio_id=consultorio.id,
        paciente_id=paciente.id,
        monto=75.00,
        moneda="USD",
        metodo="efectivo",
        registrado_por=usuario.id,
    )
    session.add(pago)
    session.commit()
    session.refresh(pago)

    recuperado = session.get(Pago, pago.id)
    assert recuperado is not None
    assert recuperado.monto == 75.00
    assert recuperado.estado == "pagado"
    assert recuperado.consulta_id is None  # pago sin consulta vinculada


def test_relacion_paciente_tiene_citas(session, consultorio, usuario):
    """Un paciente puede tener múltiples citas."""
    paciente = Paciente(
        consultorio_id=consultorio.id, nombre="Marco Díaz", tipo="HUMANO"
    )
    session.add(paciente)
    session.commit()
    session.refresh(paciente)

    for hora in [9, 10, 11]:
        cita = Cita(
            consultorio_id=consultorio.id,
            paciente_id=paciente.id,
            profesional_id=usuario.id,
            fecha_hora=datetime(2026, 2, 1, hora, 0, tzinfo=timezone.utc),
            creada_por=usuario.id,
        )
        session.add(cita)
    session.commit()

    citas = session.exec(select(Cita).where(Cita.paciente_id == paciente.id)).all()
    assert len(citas) == 3


def test_relacion_consultorio_tiene_pacientes(session, consultorio):
    """Un consultorio puede tener múltiples pacientes."""
    nombres = ["Alice", "Bob", "Carol"]
    for nombre in nombres:
        session.add(Paciente(consultorio_id=consultorio.id, nombre=nombre, tipo="HUMANO"))
    session.commit()

    pacientes = session.exec(
        select(Paciente).where(Paciente.consultorio_id == consultorio.id)
    ).all()
    assert len(pacientes) == 3
    assert {p.nombre for p in pacientes} == set(nombres)
