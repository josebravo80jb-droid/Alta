"""Servicio de generación de enlaces de recordatorio para WhatsApp vía wa.me."""

import re
import urllib.parse
from datetime import datetime


def generar_enlace_whatsapp(telefono: str, mensaje: str) -> str:
    """Limpia el número de teléfono, aplica código de país y genera el enlace wa.me.

    Args:
        telefono: Número de teléfono del destinatario.
        mensaje: Texto del mensaje a enviar.

    Returns:
        URL en formato https://wa.me/{telefono}?text={mensaje_codificado}

    Raises:
        ValueError: Si el teléfono está vacío o no contiene suficientes dígitos.
    """
    if not telefono or not telefono.strip():
        raise ValueError("El número de teléfono no puede estar vacío")

    # Limpiar caracteres que no sean dígitos ni el símbolo '+'
    # Quitar espacios, guiones, paréntesis, puntos, etc.
    limpio = re.sub(r"[^\d+]", "", telefono.strip())

    # Quitar el '+' inicial si existe
    if limpio.startswith("+"):
        limpio = limpio[1:]

    # Si empieza con 0 (ej. formato local venezolano 0412, 0414, 0424), asumir código de país 58
    if limpio.startswith("0"):
        limpio = "58" + limpio[1:]
    # Si tiene 10 dígitos (ej. 4121234567 sin el 0 inicial), asumir también 58
    elif len(limpio) == 10 and not limpio.startswith("58"):
        limpio = "58" + limpio

    # Validar longitud mínima razonable para un teléfono internacional E.164 (mínimo 8 dígitos)
    if not limpio.isdigit() or len(limpio) < 8:
        raise ValueError(f"El número de teléfono '{telefono}' no es válido")

    mensaje_codificado = urllib.parse.quote(mensaje)
    return f"https://wa.me/{limpio}?text={mensaje_codificado}"


def generar_mensaje_recordatorio(paciente, cita, consultorio) -> str:
    """Construye el texto en español para el recordatorio de cita.

    Args:
        paciente: Objeto Paciente con nombre.
        cita: Objeto Cita con fecha_hora y motivo.
        consultorio: Objeto Consultorio con nombre y direccion.

    Returns:
        Mensaje formateado listo para enviar.
    """
    nombre_paciente = getattr(paciente, "nombre", "Paciente")
    fecha_dt = cita.fecha_hora if isinstance(cita.fecha_hora, datetime) else datetime.fromisoformat(str(cita.fecha_hora))
    fecha_str = fecha_dt.strftime("%d/%m/%Y")
    hora_str = fecha_dt.strftime("%H:%M")

    direccion = getattr(consultorio, "direccion", "Consultorio") or "Consultorio"
    nombre_consultorio = getattr(consultorio, "nombre", "Alta") or "Alta"
    motivo = getattr(cita, "motivo", "") or "Consulta de rutina"

    return (
        f"Hola {nombre_paciente}, le recuerdo su cita:\n"
        f"📅 Fecha: {fecha_str}\n"
        f"🕐 Hora: {hora_str}\n"
        f"📍 Lugar: {direccion}\n"
        f"Motivo: {motivo}\n\n"
        f"Por favor confirme su asistencia.\n"
        f"- {nombre_consultorio}"
    )
