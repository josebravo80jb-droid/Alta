"""Endpoints de autenticación: registro y login."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models.configuracion import Configuracion
from app.models.consultorio import Consultorio
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, RegistroRequest, TokenResponse, UsuarioResponse
from app.services.auth import crear_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=UsuarioResponse)
def me(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> UsuarioResponse:
    """Devuelve los datos del usuario autenticado."""
    tipo_cons = usuario.tipo_consultorio
    if not tipo_cons or tipo_cons == "MEDICO":
        consultorio = db.get(Consultorio, usuario.consultorio_id)
        if consultorio:
            tipo_cons = consultorio.tipo

    return UsuarioResponse(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        tipo_consultorio=tipo_cons,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(datos: RegistroRequest, db: Session = Depends(get_session)) -> TokenResponse:
    """Crea un nuevo Consultorio, su Usuario titular (rol MEDICO) y la Configuracion inicial."""

    # Validar tipo de consultorio
    tipo_normalizado = (datos.tipo or "MEDICO").upper()
    if tipo_normalizado not in ("MEDICO", "VETERINARIO"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de consultorio inválido. Debe ser MEDICO o VETERINARIO.",
        )

    # Verificar email único antes de escribir nada
    existente = db.exec(select(Usuario).where(Usuario.email == datos.email)).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado",
        )

    # Crear consultorio con el tipo recibido
    consultorio = Consultorio(
        nombre=datos.nombre,
        tipo=tipo_normalizado,
        direccion=datos.direccion,
        telefono=datos.telefono,
        rif=datos.rif,
    )
    db.add(consultorio)
    db.flush()  # obtener consultorio.id sin commit

    # Crear usuario titular
    usuario = Usuario(
        consultorio_id=consultorio.id,
        email=datos.email,
        password_hash=hash_password(datos.password),
        nombre=datos.nombre,
        rol="MEDICO",
    )
    db.add(usuario)
    db.flush()

    # Crear configuración inicial
    config = Configuracion(
        consultorio_id=consultorio.id,
        horario_apertura=datos.horario_apertura,
        horario_cierre=datos.horario_cierre,
        duracion_cita_default=datos.duracion_cita,
        precio_consulta_default=datos.precio_consulta,
    )
    db.add(config)
    db.commit()
    db.refresh(usuario)

    usuario.tipo_consultorio = consultorio.tipo

    token = crear_token(usuario)
    return TokenResponse(
        access_token=token,
        tipo_consultorio=consultorio.tipo,
        usuario=UsuarioResponse(
            id=usuario.id,
            nombre=usuario.nombre,
            email=usuario.email,
            rol=usuario.rol,
            tipo_consultorio=consultorio.tipo,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(datos: LoginRequest, db: Session = Depends(get_session)) -> TokenResponse:
    """Autentica un usuario existente y devuelve un JWT."""

    usuario = db.exec(select(Usuario).where(Usuario.email == datos.email)).first()

    # Misma excepción para email y password: no revelar cuál falló
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not usuario or not usuario.activo:
        raise credenciales_invalidas

    if not verify_password(datos.password, usuario.password_hash):
        raise credenciales_invalidas

    consultorio = db.get(Consultorio, usuario.consultorio_id)
    tipo_cons = consultorio.tipo if consultorio else "MEDICO"
    usuario.tipo_consultorio = tipo_cons

    token = crear_token(usuario)
    return TokenResponse(
        access_token=token,
        tipo_consultorio=tipo_cons,
        usuario=UsuarioResponse(
            id=usuario.id,
            nombre=usuario.nombre,
            email=usuario.email,
            rol=usuario.rol,
            tipo_consultorio=tipo_cons,
        ),
    )
