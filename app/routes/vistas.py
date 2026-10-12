"""Rutas HTML (vistas Jinja2) para el frontend del sistema."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_session
from app.dependencies import get_current_user
from app.models.cita import Cita
from app.models.consulta import Consulta
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.models.vacuna import Vacuna
from app.models.dueno import Dueno
from app.models.consultorio import Consultorio
from app.routes.dashboard import resumen as calcular_resumen
from app.services.agenda import obtener_citas_semana
from sqlmodel import Session, select

router = APIRouter(tags=["vistas"])
templates = Jinja2Templates(directory="app/templates")

# Moneda por defecto para el template (viene de Configuracion en M5+)
_MONEDA_DEFAULT = "USD"


@router.get("/", response_class=RedirectResponse, include_in_schema=False)
def root_redirect(request: Request):
    """Redirige a /dashboard si hay sesión (token), o a /entrada si no la hay."""
    # Verificar si viene Authorization header o cookie con token
    auth_header = request.headers.get("Authorization", "")
    token_cookie = request.cookies.get("alta_token") or request.cookies.get("token")
    if auth_header.startswith("Bearer ") or token_cookie:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/entrada", status_code=302)


@router.get("/entrada", response_class=HTMLResponse, include_in_schema=False)
def vista_entrada(request: Request):
    """Renderiza la pantalla de elección de marca: AltaMed (médico) o AltaPet (veterinario)."""
    return templates.TemplateResponse(request, "entrada.html", {})


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def vista_login(request: Request):
    """Renderiza la página de inicio de sesión."""
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login", include_in_schema=False)
def procesar_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    """Procesa el formulario de login web, establece cookie de sesión y redirige."""
    from app.services.auth import crear_token, verify_password

    usuario = db.exec(select(Usuario).where(Usuario.email == email)).first()
    if not usuario or not usuario.activo or not verify_password(password, usuario.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Email o contraseña incorrectos"},
            status_code=400,
        )

    token = crear_token(usuario)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="alta_token",
        value=token,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout", include_in_schema=False)
def logout():
    """Cierra la sesión del usuario eliminando la cookie de autenticación."""
    response = RedirectResponse(url="/entrada", status_code=302)
    response.delete_cookie(key="alta_token")
    return response


@router.get("/registro", response_class=HTMLResponse, include_in_schema=False)
def vista_registro(request: Request, tipo: Optional[str] = "MEDICO"):
    """Renderiza la página de registro de nuevo consultorio adaptada por tipo."""
    tipo_norm = (tipo or "MEDICO").upper()
    return templates.TemplateResponse(request, "registro.html", {"tipo": tipo_norm})


@router.post("/registro", include_in_schema=False)
def procesar_registro(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    especialidad: str = Form(...),
    direccion: str = Form(...),
    telefono: str = Form(...),
    tipo: str = Form("MEDICO"),
    db: Session = Depends(get_session),
):
    """Procesa el formulario de registro web, crea consultorio y usuario, y establece cookie."""
    from app.models.configuracion import Configuracion
    from app.models.consultorio import Consultorio
    from app.services.auth import crear_token, hash_password

    tipo_norm = (tipo or "MEDICO").upper()
    if tipo_norm not in ("MEDICO", "VETERINARIO"):
        tipo_norm = "MEDICO"

    existente = db.exec(select(Usuario).where(Usuario.email == email)).first()
    if existente:
        return templates.TemplateResponse(
            request,
            "registro.html",
            {
                "error": "El email ya está registrado",
                "tipo": tipo_norm,
            },
            status_code=400,
        )

    consultorio = Consultorio(
        nombre=nombre,
        tipo=tipo_norm,
        direccion=direccion,
        telefono=telefono,
    )
    db.add(consultorio)
    db.flush()

    usuario = Usuario(
        consultorio_id=consultorio.id,
        email=email,
        password_hash=hash_password(password),
        nombre=nombre,
        rol="MEDICO",
    )
    db.add(usuario)
    db.flush()

    config = Configuracion(
        consultorio_id=consultorio.id,
        horario_apertura="08:00",
        horario_cierre="18:00",
        duracion_cita_default=30,
        precio_consulta_default=0.0,
    )
    db.add(config)
    db.commit()
    db.refresh(usuario)

    token = crear_token(usuario)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="alta_token",
        value=token,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def vista_dashboard(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el dashboard con el resumen del día.

    get_current_user lanzará 401 si no hay token válido;
    el manejador de errores en main.py redirigirá a /login.
    """
    datos = calcular_resumen(usuario=usuario, db=db)
    # Añadir moneda al resumen para el template
    datos_dict = datos.model_dump()
    datos_dict["moneda"] = _MONEDA_DEFAULT

    # Solicitudes de horario pendientes
    solicitudes_pendientes = db.exec(
        select(Cita).where(
            Cita.consultorio_id == usuario.consultorio_id,
            Cita.origen == "solicitud",
            Cita.estado == "pendiente",
        ).order_by(Cita.creado_en.desc())
    ).all()

    # Objeto simple para pasar al template
    class _Resumen:
        def __init__(self, d):
            self.__dict__.update(d)
            # proximas_citas como objetos con atributos
            from app.schemas.dashboard import CitaResumen
            self.proximas_citas = [CitaResumen(**c) for c in d["proximas_citas"]]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "usuario": usuario,
            "resumen": _Resumen(datos_dict),
            "solicitudes": solicitudes_pendientes,
            "fecha_hoy": date.today().strftime("%d/%m/%Y"),
            "active_page": "dashboard",
        },
    )


# ── Agenda ────────────────────────────────────────────────────────────────────

_DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _semana_desde(fecha_str: str | None) -> datetime:
    """Devuelve el lunes de la semana dada, o el lunes actual si fecha_str es None."""
    if fecha_str:
        try:
            d = datetime.strptime(fecha_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return d - timedelta(days=d.weekday())  # retroceder al lunes
        except ValueError:
            pass
    hoy = datetime.now(timezone.utc)
    return hoy - timedelta(days=hoy.weekday())


@router.get("/agenda", response_class=HTMLResponse, include_in_schema=False)
def vista_agenda(
    request: Request,
    fecha: str | None = None,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza la vista semanal de la agenda."""
    lunes = _semana_desde(fecha)
    citas_todas = obtener_citas_semana(db, usuario.consultorio_id, lunes)
    # Excluir solicitudes no asignadas a horario de la agenda normal
    citas = [c for c in citas_todas if getattr(c, "origen", "interno") != "solicitud"]

    # Enriquecer cada cita con nombre del paciente
    paciente_cache: dict[int, str] = {}
    for cita in citas:
        if cita.paciente_id:
            if cita.paciente_id not in paciente_cache:
                p = db.get(Paciente, cita.paciente_id)
                paciente_cache[cita.paciente_id] = p.nombre if p else "—"
        else:
            paciente_cache[cita.id] = cita.nombre_solicitante or "Solicitud"

    # Construir estructura de 7 días
    hoy = datetime.now(timezone.utc).date()
    dias = []
    for i in range(7):
        dia_dt = lunes + timedelta(days=i)
        dia_date = dia_dt.date()
        citas_dia = [
            type("C", (), {
                "id": c.id,
                "fecha_hora": c.fecha_hora,
                "paciente_nombre": paciente_cache.get(c.paciente_id) or c.nombre_solicitante or "—",
                "motivo": c.motivo,
                "estado": c.estado,
                "origen": getattr(c, "origen", "interno"),
            })()
            for c in citas
            if c.fecha_hora.date() == dia_date
        ]
        dias.append(type("D", (), {
            "nombre": _DIAS_ES[i],
            "numero": dia_date.strftime("%d/%m"),
            "es_hoy": dia_date == hoy,
            "citas": citas_dia,
        })())

    semana_ant = (lunes - timedelta(days=7)).strftime("%Y-%m-%d")
    semana_sig = (lunes + timedelta(days=7)).strftime("%Y-%m-%d")
    label = f"{lunes.strftime('%d/%m')} – {(lunes + timedelta(days=6)).strftime('%d/%m/%Y')}"

    return templates.TemplateResponse(
        request,
        "agenda/semana.html",
        {
            "usuario": usuario,
            "dias": dias,
            "semana_anterior": semana_ant,
            "semana_siguiente": semana_sig,
            "label_semana": label,
            "hoy": hoy.strftime("%Y-%m-%d"),
            "active_page": "agenda",
        },
    )


@router.get("/agenda/nueva", response_class=HTMLResponse, include_in_schema=False)
def vista_nueva_cita(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    """Renderiza el formulario de nueva cita."""
    return templates.TemplateResponse(
        request,
        "agenda/cita_form.html",
        {"usuario": usuario, "cita": None, "active_page": "agenda"},
    )


@router.get("/agenda/{cita_id}/editar", response_class=HTMLResponse, include_in_schema=False)
def vista_editar_cita(
    cita_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el formulario de edición de una cita existente."""
    from app.routes.agenda import _get_cita_del_consultorio
    cita = _get_cita_del_consultorio(cita_id, usuario.consultorio_id, db)
    paciente = db.get(Paciente, cita.paciente_id)
    # Enriquecer con nombre del paciente para el template
    cita_ctx = type("C", (), {
        "id": cita.id,
        "paciente_id": cita.paciente_id,
        "paciente_nombre": paciente.nombre if paciente else "",
        "fecha_hora": cita.fecha_hora,
        "duracion_min": cita.duracion_min,
        "motivo": cita.motivo,
        "estado": cita.estado,
    })()
    return templates.TemplateResponse(
        request,
        "agenda/cita_form.html",
        {"usuario": usuario, "cita": cita_ctx, "active_page": "agenda"},
    )


# ── Pacientes ─────────────────────────────────────────────────────────────────

@router.get("/pacientes", response_class=HTMLResponse, include_in_schema=False)
def vista_pacientes(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza la lista de pacientes del consultorio."""
    from app.services.pacientes import buscar_pacientes
    pacientes = buscar_pacientes(db=db, consultorio_id=usuario.consultorio_id)
    return templates.TemplateResponse(
        request,
        "pacientes/lista.html",
        {"usuario": usuario, "pacientes": pacientes, "active_page": "pacientes"},
    )


@router.get("/pacientes/nuevo", response_class=HTMLResponse, include_in_schema=False)
def vista_nuevo_paciente(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el formulario para registrar un nuevo paciente."""
    from app.services.pacientes import buscar_duenos
    duenos = buscar_duenos(db=db, consultorio_id=usuario.consultorio_id)
    return templates.TemplateResponse(
        request,
        "pacientes/paciente_form.html",
        {"usuario": usuario, "paciente": None, "duenos": duenos, "active_page": "pacientes"},
    )


@router.get("/pacientes/{paciente_id}", response_class=HTMLResponse, include_in_schema=False)
def vista_ficha_paciente(
    paciente_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza la ficha médica individual y su historial."""
    from app.services.pacientes import obtener_paciente_detalle
    detalle = obtener_paciente_detalle(db=db, paciente_id=paciente_id, consultorio_id=usuario.consultorio_id, usuario=usuario)
    if not detalle:
        return RedirectResponse(url="/pacientes", status_code=302)

    return templates.TemplateResponse(
        request,
        "pacientes/ficha.html",
        {
            "usuario": usuario,
            "paciente": detalle["paciente"],
            "dueno": detalle["dueno"],
            "historial": detalle["historial"],
            "active_page": "pacientes",
        },
    )


@router.get("/pacientes/{paciente_id}/editar", response_class=HTMLResponse, include_in_schema=False)
def vista_editar_paciente(
    paciente_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el formulario para editar un paciente existente."""
    from app.services.pacientes import buscar_duenos
    paciente = db.exec(
        select(Paciente).where(
            Paciente.id == paciente_id,
            Paciente.consultorio_id == usuario.consultorio_id,
        )
    ).first()
    if not paciente:
        return RedirectResponse(url="/pacientes", status_code=302)

    duenos = buscar_duenos(db=db, consultorio_id=usuario.consultorio_id)
    return templates.TemplateResponse(
        request,
        "pacientes/paciente_form.html",
        {"usuario": usuario, "paciente": paciente, "duenos": duenos, "active_page": "pacientes"},
    )



# ── Consultas Clínicas ────────────────────────────────────────────────────────

@router.get("/consultas", response_class=HTMLResponse, include_in_schema=False)
def vista_lista_consultas(
    request: Request,
    q: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el listado general de consultas del consultorio.

    El asistente solo ve fecha y motivo (sin nota, indicaciones ni diagnóstico).
    Admite filtros: búsqueda por nombre de paciente (q), rango de fechas (desde/hasta).
    Por defecto muestra los últimos 30 días.
    """
    from datetime import timedelta

    # Rango por defecto: últimos 30 días
    hoy = datetime.now(timezone.utc)
    if desde:
        try:
            fecha_desde = datetime.strptime(desde, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            fecha_desde = hoy - timedelta(days=30)
    else:
        fecha_desde = hoy - timedelta(days=30)

    if hasta:
        try:
            # Incluir todo el día hasta
            fecha_hasta = datetime.strptime(hasta, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            fecha_hasta = fecha_hasta.replace(hour=23, minute=59, second=59)
        except ValueError:
            fecha_hasta = hoy.replace(hour=23, minute=59, second=59)
    else:
        fecha_hasta = hoy.replace(hour=23, minute=59, second=59)

    stmt = (
        select(Consulta)
        .where(
            Consulta.consultorio_id == usuario.consultorio_id,
            Consulta.demo == False,
            Consulta.fecha >= fecha_desde,
            Consulta.fecha <= fecha_hasta,
        )
        .order_by(Consulta.fecha.desc())
    )
    consultas_raw = db.exec(stmt).all()

    # Caché de pacientes para no hacer N queries
    paciente_cache: dict[int, str] = {}
    for con in consultas_raw:
        if con.paciente_id not in paciente_cache:
            p = db.get(Paciente, con.paciente_id)
            paciente_cache[con.paciente_id] = p.nombre if p else "—"

    # Filtro por nombre (en Python, tras obtener los datos)
    if q:
        q_lower = q.lower()
        consultas_raw = [
            c for c in consultas_raw
            if q_lower in paciente_cache.get(c.paciente_id, "").lower()
        ]

    # Enriquecer con nombre del paciente
    consultas = [
        type("C", (), {
            "id": c.id,
            "fecha": c.fecha,
            "paciente_id": c.paciente_id,
            "paciente_nombre": paciente_cache.get(c.paciente_id, "—"),
            "motivo": c.motivo,
            "diagnostico": c.diagnostico if usuario.rol == "MEDICO" else None,
        })()
        for c in consultas_raw
    ]

    return templates.TemplateResponse(
        request,
        "consultas/lista.html",
        {
            "usuario": usuario,
            "consultas": consultas,
            "q": q or "",
            "desde": desde or "",
            "hasta": hasta or "",
            "active_page": "consultas",
        },
    )


@router.get("/consultas/nueva", response_class=HTMLResponse, include_in_schema=False)
def vista_nueva_consulta(
    request: Request,
    paciente_id: int = 0,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el formulario para crear una consulta médica (solo rol MEDICO)."""
    if usuario.rol != "MEDICO":
        return RedirectResponse(url="/pacientes", status_code=302)

    pacientes = db.exec(
        select(Paciente)
        .where(Paciente.consultorio_id == usuario.consultorio_id, Paciente.demo == False)
        .order_by(Paciente.nombre)
    ).all()

    paciente_sel = db.get(Paciente, paciente_id) if paciente_id else None
    citas = []
    if paciente_id:
        citas = db.exec(
            select(Cita)
            .where(Cita.consultorio_id == usuario.consultorio_id, Cita.paciente_id == paciente_id)
            .order_by(Cita.fecha_hora.desc())
        ).all()

    return templates.TemplateResponse(
        request,
        "consultas/form.html",
        {
            "usuario": usuario,
            "consulta": None,
            "pacientes": pacientes,
            "paciente": paciente_sel,
            "paciente_id_sel": paciente_id if paciente_id else None,
            "citas": citas,
            "active_page": "pacientes",
        },
    )


@router.get("/consultas/{consulta_id}", response_class=HTMLResponse, include_in_schema=False)
def vista_detalle_consulta(
    consulta_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Muestra el detalle clínico completo de una consulta (solo rol MEDICO)."""
    if usuario.rol != "MEDICO":
        return RedirectResponse(url="/pacientes", status_code=302)

    from app.services.consultas import obtener_consulta
    consulta = obtener_consulta(db=db, consulta_id=consulta_id, consultorio_id=usuario.consultorio_id)
    if not consulta:
        return RedirectResponse(url="/pacientes", status_code=302)

    paciente = db.get(Paciente, consulta.paciente_id)
    medico = db.get(Usuario, consulta.profesional_id)

    return templates.TemplateResponse(
        request,
        "consultas/detalle.html",
        {
            "usuario": usuario,
            "consulta": consulta,
            "paciente": paciente,
            "medico": medico,
            "active_page": "pacientes",
        },
    )


@router.get("/consultas/{consulta_id}/editar", response_class=HTMLResponse, include_in_schema=False)
def vista_editar_consulta(
    consulta_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el formulario de edición para una consulta médica existente (solo rol MEDICO)."""
    if usuario.rol != "MEDICO":
        return RedirectResponse(url="/pacientes", status_code=302)

    from app.services.consultas import obtener_consulta
    consulta = obtener_consulta(db=db, consulta_id=consulta_id, consultorio_id=usuario.consultorio_id)
    if not consulta:
        return RedirectResponse(url="/pacientes", status_code=302)

    paciente = db.get(Paciente, consulta.paciente_id)
    pacientes = [paciente] if paciente else []

    citas = []
    if paciente:
        citas = db.exec(
            select(Cita)
            .where(Cita.consultorio_id == usuario.consultorio_id, Cita.paciente_id == paciente.id)
            .order_by(Cita.fecha_hora.desc())
        ).all()

    return templates.TemplateResponse(
        request,
        "consultas/form.html",
        {
            "usuario": usuario,
            "consulta": consulta,
            "paciente": paciente,
            "paciente_id_sel": paciente.id if paciente else None,
            "pacientes": pacientes,
            "citas": citas,
            "active_page": "pacientes",
        },
    )


# ── Ingresos y Pagos ──────────────────────────────────────────────────────────

@router.get("/ingresos", response_class=HTMLResponse, include_in_schema=False)
def vista_ingresos(
    request: Request,
    mes: Optional[str] = None,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el reporte financiero mensual con listado de pagos y totales."""
    from app.services.pagos import listar_pagos, obtener_resumen_ingresos

    hoy = datetime.now(timezone.utc)
    mes_actual = mes if mes else hoy.strftime("%Y-%m")

    pagos = listar_pagos(db=db, consultorio_id=usuario.consultorio_id, mes=mes_actual)
    resumen = obtener_resumen_ingresos(db=db, consultorio_id=usuario.consultorio_id, mes=mes_actual)

    # Enriquecer pagos con nombres de paciente y concepto para la vista
    pagos_view = []
    for p in pagos:
        pac = db.get(Paciente, p.paciente_id)
        con = db.get(Consulta, p.consulta_id) if p.consulta_id else None
        pagos_view.append(
            type("P", (), {
                "id": p.id,
                "fecha": p.fecha,
                "paciente_id": p.paciente_id,
                "paciente_nombre": pac.nombre if pac else "—",
                "concepto": f"Consulta: {con.motivo}" if con else "Atención médica",
                "monto": p.monto,
                "moneda": p.moneda,
                "metodo": p.metodo,
                "estado": p.estado,
            })()
        )

    return templates.TemplateResponse(
        request,
        "ingresos/reporte.html",
        {
            "usuario": usuario,
            "mes_sel": mes_actual,
            "resumen": resumen,
            "pagos": pagos_view,
            "active_page": "ingresos",
        },
    )


@router.get("/ingresos/nuevo", response_class=HTMLResponse, include_in_schema=False)
def vista_nuevo_pago(
    request: Request,
    paciente_id: int = 0,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el formulario para registrar un nuevo pago/cobro."""
    pacientes = db.exec(
        select(Paciente)
        .where(Paciente.consultorio_id == usuario.consultorio_id, Paciente.demo == False)
        .order_by(Paciente.nombre)
    ).all()

    consultas = []
    if paciente_id:
        consultas = db.exec(
            select(Consulta)
            .where(Consulta.consultorio_id == usuario.consultorio_id, Consulta.paciente_id == paciente_id)
            .order_by(Consulta.fecha.desc())
        ).all()

    return templates.TemplateResponse(
        request,
        "pagos/pago_form.html",
        {
            "usuario": usuario,
            "pago": None,
            "pacientes": pacientes,
            "paciente_id_sel": paciente_id if paciente_id else None,
            "consultas": consultas,
            "active_page": "ingresos",
        },
    )


@router.get("/pagos/{pago_id}/editar", response_class=HTMLResponse, include_in_schema=False)
def vista_editar_pago(
    pago_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza el formulario para editar un pago existente."""
    pago = db.exec(
        select(Pago).where(Pago.id == pago_id, Pago.consultorio_id == usuario.consultorio_id)
    ).first()
    if not pago:
        return RedirectResponse(url="/ingresos", status_code=302)

    pacientes = db.exec(
        select(Paciente)
        .where(Paciente.consultorio_id == usuario.consultorio_id, Paciente.demo == False)
        .order_by(Paciente.nombre)
    ).all()

    consultas = db.exec(
        select(Consulta)
        .where(Consulta.consultorio_id == usuario.consultorio_id, Consulta.paciente_id == pago.paciente_id)
        .order_by(Consulta.fecha.desc())
    ).all()

    return templates.TemplateResponse(
        request,
        "pagos/pago_form.html",
        {
            "usuario": usuario,
            "pago": pago,
            "pacientes": pacientes,
            "paciente_id_sel": pago.paciente_id,
            "consultas": consultas,
            "active_page": "ingresos",
        },
    )



# ── Configuración ─────────────────────────────────────────────────────────────

@router.get("/configuracion", response_class=HTMLResponse, include_in_schema=False)
def vista_configuracion(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Renderiza la página de configuración del consultorio.

    El médico ve todas las secciones (datos, usuarios, backup, sesión).
    El asistente solo ve datos del consultorio, preferencias y sesión.
    """
    from app.models.configuracion import Configuracion
    from app.models.consultorio import Consultorio

    consultorio = db.get(Consultorio, usuario.consultorio_id)
    config = db.exec(
        select(Configuracion).where(Configuracion.consultorio_id == usuario.consultorio_id)
    ).first()

    # Lista de usuarios del consultorio (para médico)
    usuarios_cons = []
    if usuario.rol == "MEDICO":
        usuarios_cons = db.exec(
            select(Usuario)
            .where(Usuario.consultorio_id == usuario.consultorio_id, Usuario.activo == True)
            .order_by(Usuario.nombre)
        ).all()

    return templates.TemplateResponse(
        request,
        "configuracion/index.html",
        {
            "usuario": usuario,
            "consultorio": consultorio,
            "config": config,
            "usuarios": usuarios_cons,
            "active_page": "configuracion",
        },
    )


@router.get("/vacunas", response_class=HTMLResponse, include_in_schema=False)
def vista_vacunas_lista(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Listado general de vacunas y recordatorios para consultorios veterinarios."""
    consultorio = db.get(Consultorio, usuario.consultorio_id)
    if not consultorio or consultorio.tipo != "VETERINARIO":
        return RedirectResponse(url="/dashboard", status_code=302)

    from app.services.veterinaria.recordatorios import vacunas_proximas_7_dias, vacunas_vencidas

    vacunas = db.exec(
        select(Vacuna, Paciente)
        .join(Paciente, Vacuna.paciente_id == Paciente.id)
        .where(Vacuna.consultorio_id == usuario.consultorio_id)
        .order_by(Vacuna.fecha_aplicacion.desc())
    ).all()

    proximas = vacunas_proximas_7_dias(db, usuario.consultorio_id)
    vencidas = vacunas_vencidas(db, usuario.consultorio_id)

    return templates.TemplateResponse(
        request,
        "vacunas/lista.html",
        {
            "usuario": usuario,
            "consultorio": consultorio,
            "vacunas": vacunas,
            "proximas": proximas,
            "vencidas": vencidas,
            "active_page": "vacunas",
            "tipo_consultorio": consultorio.tipo,
        },
    )


@router.get("/vacunas/{paciente_id}", response_class=HTMLResponse, include_in_schema=False)
def vista_vacunas_calendario(
    paciente_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Vista de calendario de vacunación para una mascota específica."""
    consultorio = db.get(Consultorio, usuario.consultorio_id)
    if not consultorio or consultorio.tipo != "VETERINARIO":
        return RedirectResponse(url="/dashboard", status_code=302)

    paciente = db.get(Paciente, paciente_id)
    if not paciente or paciente.consultorio_id != usuario.consultorio_id:
        return RedirectResponse(url="/pacientes", status_code=302)

    from app.services.veterinaria.vacunas import calcular_calendario, vacunas_pendientes

    vacunas_aplicadas = db.exec(
        select(Vacuna)
        .where(Vacuna.paciente_id == paciente_id, Vacuna.consultorio_id == usuario.consultorio_id)
        .order_by(Vacuna.fecha_aplicacion.desc())
    ).all()

    teorico = []
    if paciente.especie and paciente.fecha_nacimiento:
        teorico = calcular_calendario(paciente.especie, paciente.fecha_nacimiento)

    pendientes = vacunas_pendientes(paciente, vacunas_aplicadas)

    return templates.TemplateResponse(
        request,
        "vacunas/calendario.html",
        {
            "usuario": usuario,
            "consultorio": consultorio,
            "paciente": paciente,
            "vacunas_aplicadas": vacunas_aplicadas,
            "calendario_teorico": teorico,
            "pendientes": pendientes,
            "active_page": "vacunas",
            "tipo_consultorio": consultorio.tipo,
        },
    )


@router.get("/vacunas/{paciente_id}/nueva", response_class=HTMLResponse, include_in_schema=False)
def vista_vacuna_form(
    paciente_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Formulario para registrar una nueva vacuna a una mascota."""
    consultorio = db.get(Consultorio, usuario.consultorio_id)
    if not consultorio or consultorio.tipo != "VETERINARIO":
        return RedirectResponse(url="/dashboard", status_code=302)

    paciente = db.get(Paciente, paciente_id)
    if not paciente or paciente.consultorio_id != usuario.consultorio_id:
        return RedirectResponse(url="/pacientes", status_code=302)

    from app.services.veterinaria.especies import obtener_especie
    esp_info = obtener_especie(paciente.especie) if paciente.especie else None
    vacunas_sugeridas = esp_info.get("vacunas_obligatorias", []) if esp_info else []

    return templates.TemplateResponse(
        request,
        "vacunas/form.html",
        {
            "usuario": usuario,
            "consultorio": consultorio,
            "paciente": paciente,
            "vacunas_sugeridas": vacunas_sugeridas,
            "hoy": date.today(),
            "active_page": "vacunas",
            "tipo_consultorio": consultorio.tipo,
        },
    )


# ── Rutas de Agenda Pública (Sin autenticación) ───────────────────────────────

@router.get("/agenda/{slug}", response_class=HTMLResponse, include_in_schema=False)
def vista_agenda_publica(slug: str, request: Request, db: Session = Depends(get_session)):
    """Página pública de reserva de citas para pacientes."""
    consultorio = db.exec(select(Consultorio).where(Consultorio.slug == slug)).first()
    if not consultorio or not consultorio.agenda_publica_activa:
        return HTMLResponse(
            "<h2>Agenda no disponible</h2><p>El consultorio no existe o no tiene habilitada la agenda pública.</p>",
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "publico/agenda.html",
        {"consultorio": consultorio},
    )


@router.get("/agenda/{slug}/solicitar", response_class=HTMLResponse, include_in_schema=False)
def vista_solicitar_publico(slug: str, request: Request, db: Session = Depends(get_session)):
    """Formulario público para solicitar horario libre."""
    consultorio = db.exec(select(Consultorio).where(Consultorio.slug == slug)).first()
    if not consultorio or not consultorio.agenda_publica_activa:
        return HTMLResponse(
            "<h2>Agenda no disponible</h2><p>El consultorio no existe o no tiene habilitada la agenda pública.</p>",
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "publico/solicitud.html",
        {"consultorio": consultorio},
    )


@router.get("/agenda/{slug}/exito/{cita_id}", response_class=HTMLResponse, include_in_schema=False)
def vista_exito_publico(
    slug: str,
    cita_id: int,
    request: Request,
    wa: Optional[str] = None,
    fecha: Optional[str] = None,
    hora: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Página de confirmación de cita agendada."""
    consultorio = db.exec(select(Consultorio).where(Consultorio.slug == slug)).first()
    if not consultorio:
        return HTMLResponse("<h2>Consultorio no encontrado</h2>", status_code=404)

    cita = db.get(Cita, cita_id)
    if not cita or cita.consultorio_id != consultorio.id:
        return HTMLResponse("<h2>Cita no encontrada</h2>", status_code=404)

    paciente = db.get(Paciente, cita.paciente_id) if cita.paciente_id else None

    # Formatear fecha y hora
    f_str = fecha or cita.fecha_hora.strftime("%d/%m/%Y")
    h_str = hora or cita.fecha_hora.strftime("%H:%M")

    # Si wa no viene en query param, generarlo
    enlace_wa = wa
    if not enlace_wa:
        from app.services.whatsapp import generar_enlace_whatsapp
        tel_dest = consultorio.telefono_whatsapp_publico or consultorio.telefono
        msg = (
            f"Hola, soy {cita.nombre_solicitante or (paciente.nombre if paciente else 'Paciente')}.\n"
            f"Acabo de agendar una cita para el {f_str} a las {h_str}.\n"
            f"Motivo: {cita.motivo}"
        )
        try:
            enlace_wa = generar_enlace_whatsapp(tel_dest, msg)
        except Exception:
            enlace_wa = ""

    return templates.TemplateResponse(
        request,
        "publico/exito.html",
        {
            "consultorio": consultorio,
            "cita": cita,
            "paciente": paciente,
            "fecha_formateada": f_str,
            "hora_formateada": h_str,
            "enlace_whatsapp": enlace_wa,
        },
    )


@router.get("/agenda/{slug}/solicitud-exito", response_class=HTMLResponse, include_in_schema=False)
def vista_solicitud_exito_publico(slug: str, request: Request, db: Session = Depends(get_session)):
    """Pantalla de éxito tras enviar solicitud libre."""
    consultorio = db.exec(select(Consultorio).where(Consultorio.slug == slug)).first()
    if not consultorio:
        return HTMLResponse("<h2>Consultorio no encontrado</h2>", status_code=404)

    return templates.TemplateResponse(
        request,
        "publico/solicitud_exito.html",
        {"consultorio": consultorio},
    )

