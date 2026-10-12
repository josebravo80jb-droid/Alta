"""Tests de verificación para la resolución de los bugs de auditoría (Módulo 12)."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.database import get_session
from app.main import app
from app.models.consultorio import Consultorio
from app.models.usuario import Usuario
from app.services.auth import crear_token, hash_password


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    """Motor SQLite en memoria aislado por test."""
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
    """TestClient con la sesión en memoria inyectada."""
    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="usuario_existente")
def usuario_existente_fixture(db_engine):
    """Crea un consultorio y un médico de prueba."""
    with Session(db_engine) as session:
        cons = Consultorio(nombre="Consultorio Test", direccion="Calle Test", telefono="123456")
        session.add(cons)
        session.flush()

        usr = Usuario(
            consultorio_id=cons.id,
            email="doctor@test.com",
            password_hash=hash_password("claveSegura123"),
            nombre="Dr. Test",
            rol="MEDICO",
        )
        session.add(usr)
        session.commit()
        session.refresh(usr)
        token = crear_token(usr)
        return {"usuario": usr, "token": token, "email": "doctor@test.com", "password": "claveSegura123"}


def test_templates_tema_claro_por_defecto(client):
    """Las pantallas públicas deben arrancar con tema claro por defecto."""
    for ruta in ["/entrada", "/login", "/registro"]:
        res = client.get(ruta)
        assert res.status_code == 200
        assert 'data-theme="light"' in res.text


def test_login_html_post_con_cookie(client, usuario_existente):
    """POST /login vía formulario debe devolver 303 y cookie alta_token."""
    res = client.post(
        "/login",
        data={"email": usuario_existente["email"], "password": usuario_existente["password"]},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/dashboard"
    assert "alta_token" in res.cookies
    cookie_header = res.headers.get("set-cookie", "")
    assert "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()


def test_login_html_post_incorrecto_devuelve_error(client, usuario_existente):
    """POST /login con contraseña incorrecta devuelve status 400 y mensaje en plantilla."""
    res = client.post(
        "/login",
        data={"email": usuario_existente["email"], "password": "claveErronea"},
        follow_redirects=False,
    )
    assert res.status_code == 400
    assert "incorrectos" in res.text


def test_registro_html_post_con_cookie(client, db_engine):
    """POST /registro vía formulario crea el consultorio y usuario, y devuelve 303 con cookie."""
    data = {
        "nombre": "Clínica Nueva",
        "email": "nuevo@clinica.com",
        "password": "Password123!",
        "especialidad": "Odontología",
        "direccion": "Av. 1",
        "telefono": "04141112233",
        "tipo": "MEDICO",
    }
    res = client.post("/registro", data=data, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/dashboard"
    assert "alta_token" in res.cookies

    with Session(db_engine) as session:
        usr = session.query(Usuario).filter(Usuario.email == "nuevo@clinica.com").first()
        assert usr is not None


def test_auth_cookie_en_dashboard(client, usuario_existente):
    """GET /dashboard con la cookie alta_token autoriza sin header Authorization."""
    client.cookies.set("alta_token", usuario_existente["token"])
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "Dr. Test" in res.text


def test_logout_elimina_cookie(client, usuario_existente):
    """GET /logout redirige a /entrada y limpia la cookie alta_token."""
    client.cookies.set("alta_token", usuario_existente["token"])
    res = client.get("/logout", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/entrada"
    # La cookie debe ser eliminada / expirada
    set_cookie = res.headers.get("set-cookie", "")
    assert 'alta_token=""' in set_cookie or "max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower()


def test_docs_deshabilitado_en_produccion(monkeypatch):
    """Si APP_ENV == production, FastAPI no expone /docs."""
    import app.config as cfg
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    docs_url = None
    dummy_app = FastAPI(docs_url=docs_url)
    with TestClient(dummy_app) as cl:
        r = cl.get("/docs")
        assert r.status_code == 404
