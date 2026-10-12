"""Dependencias compartidas de FastAPI."""

import jwt
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.database import get_session
from app.models.usuario import Usuario
from app.services.auth import decodificar_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_session),
) -> Usuario:
    """Extrae y valida el JWT (header Authorization Bearer o cookie alta_token).

    Retorna el Usuario activo o lanza 401 si no hay credenciales válidas.
    """
    credencial_invalida = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_str: Optional[str] = None
    if credentials and credentials.credentials:
        token_str = credentials.credentials
    else:
        token_str = request.cookies.get("alta_token") or request.cookies.get("token")

    if not token_str:
        raise credencial_invalida

    try:
        payload = decodificar_token(token_str)
        usuario_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise credencial_invalida

    usuario = db.exec(select(Usuario).where(Usuario.id == usuario_id)).first()
    if not usuario or not usuario.activo:
        raise credencial_invalida

    from app.models.consultorio import Consultorio
    consultorio = db.get(Consultorio, usuario.consultorio_id)
    if consultorio:
        usuario.tipo_consultorio = consultorio.tipo

    return usuario
