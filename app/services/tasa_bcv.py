"""Servicio para consulta de tasa oficial BCV y conversiones monetarias — pyDolarVenezuela."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models.configuracion import Configuracion

logger = logging.getLogger("alta.tasa_bcv")

# Caché en memoria: almacena valor flotante y timestamp UTC
_cache_tasa = {"valor": None, "timestamp": None}
_CACHE_TTL_SEGUNDOS = 3600  # 1 hora


def obtener_tasa_respaldo(db: Optional[Session] = None, consultorio_id: Optional[int] = None) -> float:
    """Lee la tasa de respaldo desde la configuración del consultorio o usa 40.0 por defecto."""
    if db is not None and consultorio_id is not None:
        try:
            config = db.exec(
                select(Configuracion).where(Configuracion.consultorio_id == consultorio_id)
            ).first()
            if config and getattr(config, "tasa_respaldo", None):
                return float(config.tasa_respaldo)
        except Exception as e:
            logger.warning("No se pudo leer la tasa de respaldo de la BD: %s", e)

    return 40.0


def obtener_tasa_bcv(
    force_refresh: bool = False,
    db: Optional[Session] = None,
    consultorio_id: Optional[int] = None,
) -> float:
    """Obtiene la tasa oficial BCV del día con caché en memoria de 1 hora.

    Si falla pyDolarVenezuela (por red o error de API), devuelve la tasa de respaldo.
    NUNCA lanza excepción.
    """
    ahora = datetime.now(timezone.utc)

    # 1. Verificar si la caché está vigente y no se pide forzar refresco
    if not force_refresh and _cache_tasa["valor"] is not None and _cache_tasa["timestamp"] is not None:
        delta = (ahora - _cache_tasa["timestamp"]).total_seconds()
        if delta < _CACHE_TTL_SEGUNDOS:
            return float(_cache_tasa["valor"])

    # 2. Consultar pyDolarVenezuela
    try:
        from pyDolarVenezuela import Monitor
        from pyDolarVenezuela.pages import BCV

        monitor = Monitor(BCV, "USD")
        datos = monitor.get_value_monitors("usd")
        if datos and hasattr(datos, "price") and datos.price:
            valor = float(datos.price)
            _cache_tasa["valor"] = valor
            _cache_tasa["timestamp"] = ahora
            logger.info("Tasa BCV actualizada exitosamente desde monitor: %s", valor)
            return valor
    except Exception as err:
        logger.warning("Fallo al consultar pyDolarVenezuela: %s. Usando fallback de respaldo.", err)

    # 3. Fallback: Si no se forzó refresco y teníamos caché previa, usarla; si se forzó o no hay, usar respaldo
    if not force_refresh and _cache_tasa["valor"] is not None:
        return float(_cache_tasa["valor"])

    tasa_fallback = obtener_tasa_respaldo(db, consultorio_id)
    _cache_tasa["valor"] = tasa_fallback
    _cache_tasa["timestamp"] = ahora
    return tasa_fallback


def convertir_usd_a_bs(monto_usd: float, tasa: Optional[float] = None) -> float:
    """Convierte un monto en USD a Bolívares (VES). Si no se pasa tasa, se consulta la del día."""
    if tasa is None:
        tasa = obtener_tasa_bcv()
    return round(float(monto_usd) * float(tasa), 2)


def convertir_bs_a_usd(monto_bs: float, tasa: Optional[float] = None) -> float:
    """Convierte un monto en Bolívares (VES) a USD. Si no se pasa tasa, se consulta la del día."""
    if tasa is None:
        tasa = obtener_tasa_bcv()
    if float(tasa) <= 0:
        return 0.0
    return round(float(monto_bs) / float(tasa), 2)
