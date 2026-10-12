"""Punto de entrada de la aplicación Alta."""

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — registra tablas en SQLModel.metadata
from app.config import APP_ENV, APP_NAME
from app.database import init_db
from app.routes.auth import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.agenda import router as agenda_router
from app.routes.pacientes import router as pacientes_router
from app.routes.consultas import router as consultas_router
from app.routes.pagos import router as pagos_router
from app.routes.auditoria import router as auditoria_router
from app.routes.demo import router as demo_router
from app.routes.health import router as health_router
from app.routes.configuracion import router as configuracion_router
from app.routes.vistas import router as vistas_router
from app.routes.veterinaria import router as veterinaria_router
from app.routes.reportes import router as reportes_router
from app.routes.licencia import router as licencia_router
from app.routes.agenda_publica import router as agenda_publica_router
from app.routes.consultorio import router as consultorio_router
from app.services.cifrado import get_fernet

import logging
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

docs_url = "/docs" if APP_ENV != "production" else None
redoc_url = "/redoc" if APP_ENV != "production" else None
openapi_url = "/openapi.json" if APP_ENV != "production" else None

app = FastAPI(
    title=APP_NAME,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup():
    """Inicializa la base de datos, migraciones, logging y la clave simétrica de cifrado al arrancar."""
    from app.services.logging_config import configurar_logging
    from app.services.migracion import ejecutar_migraciones

    configurar_logging()
    init_db()
    ejecutar_migraciones()
    get_fernet()
    # Validar estado de licencia al arrancar
    from app.services.licencia import validar_periodicamente
    from app.database import engine
    from sqlmodel import Session
    with Session(engine) as _db:
        validar_periodicamente(_db)


# ── Manejador 401: redirige a /login en contexto de navegador ────────────────
@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    """Redirige a /login si la petición viene de un navegador (no API)."""
    # Las rutas /api/* responden JSON; el resto redirige a login
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": str(exc.detail)})
    return RedirectResponse(url="/login", status_code=302)


# ── Middleware de licencia: bloquea escritura si expirada/bloqueada ──────────
_RUTAS_LIBRES = {"/licencia", "/health", "/login", "/registro", "/entrada"}


@app.middleware("http")
async def middleware_licencia(request: Request, call_next):
    """Deniega métodos de escritura si la licencia está expirada o bloqueada.

    Rutas exentas: /licencia, /health, /login, /registro, /entrada, /static, /api/licencia/*, /api/agenda-publica/*, /agenda/*
    GET siempre permitido (modo solo lectura).
    """
    path = request.url.path
    method = request.method

    # GET y rutas exentas siempre pasan
    if (
        method == "GET"
        or path in _RUTAS_LIBRES
        or path.startswith("/static")
        or path.startswith("/api/licencia")
        or path.startswith("/api/health")
        or path.startswith("/api/agenda-publica")
        or path.startswith("/agenda")
    ):
        return await call_next(request)

    # Verificar licencia solo para escrituras (POST/PUT/PATCH/DELETE)
    try:
        from app.services.licencia import puede_escribir
        from app.database import engine
        from sqlmodel import Session as _Session
        with _Session(engine) as _db:
            if not puede_escribir(_db):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=402,
                    content={
                        "detail": "Licencia expirada. Activa tu licencia en /licencia para continuar.",
                        "licencia_url": "/licencia",
                    },
                )
    except Exception:
        pass  # No interrumpir si el módulo de licencia falla

    return await call_next(request)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(agenda_router)
app.include_router(pacientes_router)
app.include_router(consultas_router)
app.include_router(pagos_router)
app.include_router(auditoria_router)
app.include_router(demo_router)
app.include_router(health_router)
app.include_router(configuracion_router)
app.include_router(vistas_router)
app.include_router(veterinaria_router)
app.include_router(reportes_router)
app.include_router(licencia_router)
app.include_router(agenda_publica_router)
app.include_router(consultorio_router)



