"""Script de arranque de Alta.

Uso:
    python run.py

Verifica el entorno antes de iniciar:
- Python 3.11+
- Directorio data/ existe
- Clave de cifrado generada
- Base de datos creada
Luego arranca uvicorn en el puerto 8000 y abre el navegador automáticamente.
"""

import os
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

# Asegurar encoding UTF-8 en terminales Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _verificar_python():
    """Detiene la ejecución si la versión de Python es inferior a 3.11."""
    print("Verificando Python...")
    version = sys.version_info
    if version < (3, 11):
        print(f"❌ Alta requiere Python 3.11 o superior.")
        print(f"   Versión detectada: {version.major}.{version.minor}.{version.micro}")
        print(f"   Descarga Python 3.11+: https://www.python.org/downloads/")
        sys.exit(1)
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")


def _crear_directorio_data():
    """Crea el directorio data/ si no existe."""
    print("Verificando data/...")
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        print("✓ Directorio data/ creado")
    else:
        print("✓ Directorio data/ encontrado")


def _generar_clave_cifrado():
    """Genera data/clave.key si no existe."""
    print("Verificando clave.key...")
    from cryptography.fernet import Fernet

    clave_path = Path("data/clave.key")
    if not clave_path.exists():
        clave = Fernet.generate_key()
        clave_path.write_bytes(clave)
        print("✓ Clave de cifrado generada en data/clave.key")
        print("  ⚠️  IMPORTANTE: Haz copia de seguridad de data/clave.key")
        print("      Sin ella, las notas clínicas no se podrán recuperar.")
    else:
        print("✓ Clave de cifrado encontrada")


def _inicializar_base_de_datos():
    """Crea la base de datos y las tablas si no existen."""
    print("Verificando base de datos...")
    try:
        from app.database import init_db
        from app.services.cifrado import get_fernet
        init_db()
        get_fernet()
        print("✓ Base de datos lista")
    except Exception as e:
        print(f"❌ Error al inicializar la base de datos: {e}")
        traceback.print_exc()
        sys.exit(1)


def abrir_navegador():
    """Abre el navegador web automáticamente tras arrancar uvicorn."""
    time.sleep(3)
    try:
        webbrowser.open("http://localhost:8000")
    except Exception:
        pass


def main():
    """Punto de entrada principal del script de arranque."""
    print("\n" + "=" * 50)
    print("  Alta — Gestión de consultorios")
    print("=" * 50 + "\n")

    try:
        _verificar_python()
        _crear_directorio_data()
        _generar_clave_cifrado()
        _inicializar_base_de_datos()

        print("\nArrancando servidor en http://localhost:8000...")
        print("Abriendo navegador en 3 segundos...")
        print("Para detener: Ctrl + C\n")

        # Iniciar apertura automática del navegador en segundo plano
        threading.Thread(target=abrir_navegador, daemon=True).start()

        import uvicorn
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )
    except KeyboardInterrupt:
        print("\n\nAlta detenido. ¡Hasta pronto!")
    except Exception as e:
        print(f"\nERROR: {e}")
        traceback.print_exc()
        try:
            input("\nPulsa Enter para cerrar...")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
