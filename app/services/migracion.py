"""Migración SQL idempotente para añadir nuevas columnas de librerías venezolanas y módulos."""

import logging
from sqlalchemy import inspect, text
from app.database import engine

logger = logging.getLogger("alta.migracion")


def ejecutar_migraciones():
    """Ejecuta alteraciones de esquema seguras e idempotentes en SQLite y PostgreSQL."""
    # Definición de columnas a migrar por tabla: (tabla, columna, tipo_sql)
    migraciones = [
        ("consultorio", "rif", "TEXT"),
        ("configuracion", "tasa_respaldo", "REAL DEFAULT 40.0"),
        ("pago", "tasa_bcv_aplicada", "REAL"),
        ("vacuna", "laboratorio", "TEXT"),
        ("vacuna", "demo", "BOOLEAN DEFAULT FALSE"),
        ("paciente", "peso_kg_humano", "REAL"),
        ("paciente", "es_diabetico", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("paciente", "tiene_hipertension", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("paciente", "esta_embarazada", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("paciente", "toma_anticoagulantes", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("consulta", "medicamentos", "TEXT"),
        ("consulta", "diagnostico_codigo", "TEXT"),
        ("dueno", "demo", "BOOLEAN DEFAULT FALSE"),
        ("consultorio", "slug", "TEXT"),
        ("consultorio", "agenda_publica_activa", "BOOLEAN DEFAULT FALSE"),
        ("consultorio", "duracion_cita_publica", "INTEGER DEFAULT 30"),
        ("consultorio", "telefono_whatsapp_publico", "TEXT"),
        ("consultorio", "bio_publica", "TEXT"),
        ("cita", "origen", "TEXT DEFAULT 'interno'"),
        ("cita", "nombre_solicitante", "TEXT"),
        ("cita", "telefono_solicitante", "TEXT"),
        ("consultorio", "horario_publico", "TEXT"),
    ]

    try:
        inspector = inspect(engine)
        tablas_existentes = set(inspector.get_table_names())
    except Exception as exc:
        logger.warning("No se pudo inspeccionar el esquema: %s", exc)
        return

    # Cache de columnas existentes por tabla inspeccionada
    columnas_por_tabla = {}
    for tabla, _, _ in migraciones:
        if tabla in tablas_existentes and tabla not in columnas_por_tabla:
            try:
                cols = {c["name"] for c in inspector.get_columns(tabla)}
                columnas_por_tabla[tabla] = cols
            except Exception:
                columnas_por_tabla[tabla] = set()

    with engine.begin() as conn:
        for tabla, columna, tipo_sql in migraciones:
            if tabla not in tablas_existentes:
                continue
            cols_actuales = columnas_por_tabla.get(tabla, set())
            if columna not in cols_actuales:
                try:
                    sql = f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo_sql}"
                    conn.execute(text(sql))
                    cols_actuales.add(columna)
                    logger.info("Migración aplicada: %s", sql)
                except Exception as exc:
                    logger.warning("Error aplicando migración %s.%s: %s", tabla, columna, exc)
