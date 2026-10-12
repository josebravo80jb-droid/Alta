"""Script generador de claves de activación para Alta.

Uso:
    python scripts/generar_clave.py [CANTIDAD]

Formato de clave: ALTA-XXXX-XXXX-XXXX-XXXX
Caracteres válidos: letras (excluye I, O) y números (excluye 0, 1) para evitar ambigüedades.
"""

import secrets
import sys

CARACTERES = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generar_bloque(longitud: int = 4) -> str:
    return "".join(secrets.choice(CARACTERES) for _ in range(longitud))


def generar_clave() -> str:
    b1 = generar_bloque(4)
    b2 = generar_bloque(4)
    b3 = generar_bloque(4)
    b4 = generar_bloque(4)
    return f"ALTA-{b1}-{b2}-{b3}-{b4}"


def main():
    cantidad = 1
    if len(sys.argv) > 1:
        try:
            cantidad = int(sys.argv[1])
        except ValueError:
            print("Uso: python scripts/generar_clave.py [CANTIDAD]")
            sys.exit(1)

    print(f"--- Generando {cantidad} clave(s) de licencia Alta ---")
    for _ in range(cantidad):
        print(generar_clave())


if __name__ == "__main__":
    main()
