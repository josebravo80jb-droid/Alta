"""Script de migración de datos de SQLite local a PostgreSQL (Neon) — Alta."""

import argparse
import sys
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import sessionmaker

# Tablas en orden de dependencia relacional para inserción correcta
TABLAS_ORDENADAS = [
    "consultorio",
    "usuario",
    "configuracion",
    "dueno",
    "paciente",
    "cita",
    "consulta",
    "pago",
    "vacuna",
    "auditoria",
    "licencialocal",
]


def migrar_datos(sqlite_path: str, postgres_url: str):
    """Copia todas las filas de SQLite local a PostgreSQL preservando IDs y datos cifrados intactos."""
    sqlite_file = Path(sqlite_path)
    if not sqlite_file.exists():
        print(f"[ERROR] No se encontró la base de datos SQLite en: {sqlite_path}")
        sys.exit(1)

    # Adaptar URL postgres si viene con esquema obsoleto
    pg_url = postgres_url
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif pg_url.startswith("postgresql://") and not pg_url.startswith("postgresql+"):
        pg_url = pg_url.replace("postgresql://", "postgresql+psycopg://", 1)

    print(f"Conectando a SQLite: {sqlite_path}")
    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
    print(f"Conectando a PostgreSQL de destino...")
    pg_engine = create_engine(pg_url, echo=False)

    meta_sqlite = MetaData()
    meta_sqlite.reflect(bind=sqlite_engine)

    meta_pg = MetaData()
    meta_pg.reflect(bind=pg_engine)

    total_tablas = 0
    total_filas = 0

    with sqlite_engine.connect() as conn_sq, pg_engine.begin() as conn_pg:
        # Detectar tablas a procesar
        tablas_a_migrar = [t for t in TABLAS_ORDENADAS if t in meta_sqlite.tables and t in meta_pg.tables]
        # Agregar cualquier otra tabla no explícita en la lista
        for t in meta_sqlite.tables:
            if t in meta_pg.tables and t not in tablas_a_migrar:
                tablas_a_migrar.append(t)

        for nombre_tabla in tablas_a_migrar:
            t_sq = meta_sqlite.tables[nombre_tabla]
            t_pg = meta_pg.tables[nombre_tabla]

            # Leer filas de SQLite
            filas = conn_sq.execute(select(t_sq)).mappings().all()
            if not filas:
                print(f"  • {nombre_tabla}: 0 registros (vacía)")
                continue

            # Convertir a dicts y preparar inserción
            datos = [dict(f) for f in filas]
            conn_pg.execute(t_pg.insert(), datos)
            print(f"  ✓ {nombre_tabla}: {len(datos)} registros migrados")
            total_tablas += 1
            total_filas += len(datos)

    print("\n" + "=" * 50)
    print(f"[OK] Migración finalizada con éxito.")
    print(f"Tablas migradas: {total_tablas}")
    print(f"Filas totales transferidas: {total_filas}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Migra base de datos Alta de SQLite a PostgreSQL en la nube.")
    parser.add_argument(
        "--source",
        default="data/alta.db",
        help="Ruta al archivo SQLite de origen (default: data/alta.db)",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Cadena de conexión de PostgreSQL de destino (ej: postgresql://...)",
    )
    args = parser.parse_args()
    migrar_datos(args.source, args.target)


if __name__ == "__main__":
    main()
