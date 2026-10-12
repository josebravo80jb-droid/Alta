"""Pruebas unitarias para catálogos veterinarios (especies, razas y endpoints)."""

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.consultorio import Consultorio
from app.models.usuario import Usuario
from app.services.auth import crear_token
from app.services.veterinaria.especies import listar_especies, obtener_especie
from app.services.veterinaria.razas import es_raza_valida, listar_razas


@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def test_listar_especies():
    """Comprueba que se listen las 7 especies requeridas."""
    especies = listar_especies()
    assert len(especies) == 7
    ids = [e["id"] for e in especies]
    for esperada in ["perro", "gato", "conejo", "roedor", "ave", "reptil", "equino"]:
        assert esperada in ids


def test_obtener_especie():
    """Comprueba obtención de especie existente case-insensitive."""
    perro = obtener_especie("perro")
    assert perro is not None
    assert perro["nombre"] == "Perro"
    assert perro["peso_promedio_kg"] == 15.0

    gato = obtener_especie("GATO")
    assert gato is not None
    assert gato["nombre"] == "Gato"


def test_especie_inexistente_devuelve_none():
    """Comprueba que una especie inexistente devuelva None."""
    assert obtener_especie("dinosaurio") is None
    assert obtener_especie("") is None
    assert obtener_especie(None) is None


def test_listar_razas_por_especie():
    """Comprueba que devuelva la lista de razas correspondientes."""
    razas_perro = listar_razas("perro")
    assert "Labrador Retriever" in razas_perro
    assert "Golden Retriever" in razas_perro
    assert "Mestizo" in razas_perro

    razas_gato = listar_razas("gato")
    assert "Siamés" in razas_gato
    assert "Persa" in razas_gato


def test_es_raza_valida():
    """Comprueba que detecte razas válidas de una especie."""
    assert es_raza_valida("perro", "Labrador Retriever") is True
    assert es_raza_valida("perro", "labrador retriever") is True
    assert es_raza_valida("gato", "Siamés") is True


def test_es_raza_invalida():
    """Comprueba rechazo de razas no pertenecientes a la especie."""
    assert es_raza_valida("perro", "Siamés") is False
    assert es_raza_valida("gato", "Pastor Alemán") is False
    assert es_raza_valida("ave", "Chihuahua") is False


def test_endpoint_especies(client, db_session):
    """Comprueba endpoint GET /api/veterinaria/especies con autenticación."""
    consultorio = Consultorio(nombre="Vet AltaPet", tipo="VETERINARIO", direccion="Dir", telefono="123")
    db_session.add(consultorio)
    db_session.commit()
    usuario = Usuario(consultorio_id=consultorio.id, nombre="Vet", email="vet@test.com", password_hash="h", rol="MEDICO")
    db_session.add(usuario)
    db_session.commit()

    token = crear_token(usuario)
    resp = client.get("/api/veterinaria/especies", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7


def test_endpoint_razas(client, db_session):
    """Comprueba endpoint GET /api/veterinaria/razas?especie=perro."""
    consultorio = Consultorio(nombre="Vet AltaPet", tipo="VETERINARIO", direccion="Dir", telefono="123")
    db_session.add(consultorio)
    db_session.commit()
    usuario = Usuario(consultorio_id=consultorio.id, nombre="Vet", email="vet@test.com", password_hash="h", rol="MEDICO")
    db_session.add(usuario)
    db_session.commit()

    token = crear_token(usuario)
    resp = client.get("/api/veterinaria/razas?especie=perro", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "Labrador Retriever" in data
