import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME: str = os.getenv("APP_NAME", "Alta")
APP_ENV: str = os.getenv("APP_ENV", "development")
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret")
ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/alta.db")
ENCRYPTION_KEY_FILE: str = os.getenv("ENCRYPTION_KEY_FILE", "data/clave.key")

# ── Founder ─────────────────────────────────────────────────────────────────
# Acceso permanente sin licencia. El desarrollador nunca paga.
FOUNDER_EMAILS: list[str] = [
    "josebravo80.jb@gmail.com",
]

FOUNDER_HARDWARE_IDS: list[str] = [
    # Se rellena con el hardware_id propio después del primer arranque.
    # Usa GET /api/licencia/hardware-id para obtenerlo.
]


def es_founder(email: str, hardware_id: str = "") -> bool:
    """True si el email o el hardware_id pertenece al founder.

    Permite acceso permanente sin licencia al desarrollador.
    """
    return (
        email.lower() in [e.lower() for e in FOUNDER_EMAILS]
        or (hardware_id and hardware_id in FOUNDER_HARDWARE_IDS)
    )

