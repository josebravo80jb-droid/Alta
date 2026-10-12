"""Hardware ID determinista para anticopia de licencias.

100% Python puro. Sin red. Sin IA.
Combina MAC + UUID motherboard (WMIC) + hostname.
En entornos sin WMIC (Linux/CI), usa solo MAC + hostname.
"""

import hashlib
import socket
import subprocess
import uuid


def obtener_hardware_id() -> str:
    """Genera un ID único por máquina de 32 caracteres hex.

    Determinista: en la misma máquina siempre produce el mismo valor.
    Combina: MAC address + UUID motherboard (Windows WMIC) + hostname.
    Si WMIC no está disponible (Linux/CI), omite ese componente.
    """
    componentes: list[str] = []

    # Componente 1: MAC address (getnode es cross-platform)
    componentes.append(str(uuid.getnode()))

    # Componente 2: UUID del motherboard (Windows WMIC)
    try:
        resultado = subprocess.check_output(
            ["wmic", "csproduct", "get", "uuid"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lineas = [l.strip() for l in resultado.stdout.splitlines() if l.strip()]
        # La salida de WMIC es: ["UUID", "<valor>"]
        if len(lineas) >= 2:
            componentes.append(lineas[1])
    except Exception:
        # No disponible fuera de Windows o sin WMIC — se omite silenciosamente
        pass

    # Componente 3: hostname
    componentes.append(socket.gethostname())

    base = "|".join(componentes)
    return hashlib.sha256(base.encode()).hexdigest()[:32]
