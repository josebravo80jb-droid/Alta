"""Script utilitario para preparar variables de entorno y claves de producción."""

import os
import secrets
from pathlib import Path
from cryptography.fernet import Fernet


def generar_env_production():
    """Genera el archivo .env.production.example con claves criptográficas reales generadas al momento."""
    secret_key = secrets.token_urlsafe(48)
    encryption_key = Fernet.generate_key().decode("utf-8")

    contenido = f"""# Alta — Configuración de Producción (Koyeb + Neon)
APP_ENV=production
SECRET_KEY={secret_key}
ENCRYPTION_KEY={encryption_key}
DATABASE_URL=postgresql://neondb_owner:PASSWORD@ep-tu-proyecto.us-east-2.aws.neon.tech/neondb?sslmode=require
"""
    destino = Path(".env.production.example")
    destino.write_text(contenido, encoding="utf-8")
    print(f"[OK] Archivo generado exitosamente en {destino.resolve()}")
    print("\nValores listos para configurar en Koyeb (Environment Variables):")
    print("-" * 60)
    print(f"APP_ENV=production")
    print(f"SECRET_KEY={secret_key}")
    print(f"ENCRYPTION_KEY={encryption_key}")
    print("DATABASE_URL=<tu_connection_string_de_neon>")
    print("-" * 60)


if __name__ == "__main__":
    generar_env_production()
