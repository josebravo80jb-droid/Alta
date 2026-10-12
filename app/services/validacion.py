"""Servicio de validación y normalización para documentos venezolanos (RIF y Cédula)."""

import re
from typing import Optional
from stdnum.ve import rif as stdnum_rif


def validar_cedula_ve(cedula: Optional[str]) -> bool:
    """Valida el formato y valor de una Cédula de Identidad venezolana.

    Formatos aceptados: V-12345678, E-12345678, 12345678, V12345678, E12345678.
    Reglas:
    - Prefijo opcional V o E (case insensitive)
    - Entre 6 y 9 dígitos
    - No puede ser todo ceros (ej. 00000000)
    """
    if not cedula:
        return False

    c = str(cedula).strip()
    match = re.match(r"^(?:[VEve]-?)?(\d+)$", c)
    if not match:
        return False

    digitos = match.group(1)
    if not (6 <= len(digitos) <= 9):
        return False

    if int(digitos) == 0:
        return False

    return True


def normalizar_cedula(cedula: str) -> str:
    """Normaliza una cédula venezolana al formato estándar V-XXXXXXXX o E-XXXXXXXX."""
    if not cedula:
        return ""
    c = str(cedula).strip().upper()
    prefijo = "E" if c.startswith("E") else "V"
    digitos = re.sub(r"\D", "", c)
    return f"{prefijo}-{digitos}"


def validar_rif_ve(rif: Optional[str]) -> bool:
    """Valida un Registro de Información Fiscal (RIF) venezolano.

    Usa la validación matemática de dígito verificador provista por python-stdnum.
    Acepta formatos: J-12345678-9, J123456789, V-12345678-9, etc.
    """
    if not rif:
        return False
    r = str(rif).strip().upper().replace(" ", "")
    # stdnum.ve.rif valida cadenas como J-12345678-9 o J123456789
    return stdnum_rif.is_valid(r)


def normalizar_rif(rif: str) -> str:
    """Normaliza un RIF venezolano al formato estándar X-XXXXXXXX-X."""
    if not rif:
        return ""
    r = str(rif).strip().upper().replace(" ", "")
    compacto = stdnum_rif.compact(r)
    if len(compacto) == 10:
        return f"{compacto[0]}-{compacto[1:9]}-{compacto[9]}"
    return r
