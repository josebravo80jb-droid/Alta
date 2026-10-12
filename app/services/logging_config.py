"""Configuración de logging con enmascaramiento de datos sensibles — Opaque Logger."""

import logging
import re
import sys


def enmascarar_datos_sensibles(texto: str) -> str:
    """Enmascara datos sensibles en cadenas de log: Cédulas, RIF, Teléfonos y Emails.

    Formatos objetivo:
    - Cédulas: V-12345678 -> V-****5678
    - RIF: J-123456789 -> J-****789
    - Teléfonos: +584121234567 -> +58****4567
    - Emails: doctor@ejemplo.com -> d****@ejemplo.com
    """
    if not isinstance(texto, str):
        return texto

    # 1. Emails: doctor@ejemplo.com -> d****@ejemplo.com
    texto = re.sub(
        r"\b([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]*@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b",
        r"\1****@\2",
        texto,
    )

    # 2. RIF (J, P, G, V, E con formato RIF de 8-9 dígitos): J-123456789 -> J-****789
    def _repl_rif(m):
        pref = m.group(1).upper()
        digits = re.sub(r"\D", "", m.group(2))
        tail = digits[-3:] if len(digits) >= 3 else digits
        return f"{pref}-****{tail}"

    texto = re.sub(r"\b([JjPpGg])-?(\d{8,9}|\d{7,8}-?\d)\b", _repl_rif, texto)

    # 3. Cédulas (V o E): V-12345678 -> V-****5678
    def _repl_ci(m):
        pref = m.group(1).upper()
        digits = re.sub(r"\D", "", m.group(2))
        tail = digits[-4:] if len(digits) >= 4 else digits
        return f"{pref}-****{tail}"

    texto = re.sub(r"\b([VvEe])-?(\d{6,9})\b", _repl_ci, texto)

    # 4. Teléfonos venezolanos (+58...): +584121234567 -> +58****4567
    def _repl_tel(m):
        full = m.group(0)
        digits = re.sub(r"\D", "", full)
        tail = digits[-4:] if len(digits) >= 4 else digits
        if full.startswith("+58"):
            return f"+58****{tail}"
        return f"****{tail}"

    texto = re.sub(r"(\+58\d{10}|\b04\d{9}\b|\b02\d{9}\b)", _repl_tel, texto)

    return texto


class OpaqueMaskingFormatter(logging.Formatter):
    """Formatter de logging que intercepta y enmascara PII antes de emitir."""

    def format(self, record: logging.LogRecord) -> str:
        orig = super().format(record)
        return enmascarar_datos_sensibles(orig)


def configurar_logging():
    """Configura el logger raíz y de la aplicación con la máscara de privacidad."""
    root_logger = logging.getLogger()
    
    # Evitar duplicar handlers si ya se configuró
    for h in root_logger.handlers:
        if isinstance(h.formatter, OpaqueMaskingFormatter):
            return

    handler = logging.StreamHandler(sys.stdout)
    formatter = OpaqueMaskingFormatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    
    # Reemplazar o añadir
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
