"""Catálogo de especies veterinarias para AltaPet."""

from typing import Optional

ESPECIES = {
    "perro": {
        "nombre": "Perro",
        "categoria": "mamifero",
        "esperanza_vida_anios": 12,
        "peso_promedio_kg": 15.0,
        "vacunas_obligatorias": ["rabia", "moquillo", "parvovirus", "hepatitis"],
    },
    "gato": {
        "nombre": "Gato",
        "categoria": "mamifero",
        "esperanza_vida_anios": 15,
        "peso_promedio_kg": 4.0,
        "vacunas_obligatorias": ["rabia", "triple felina", "leucemia felina"],
    },
    "conejo": {
        "nombre": "Conejo",
        "categoria": "mamifero",
        "esperanza_vida_anios": 8,
        "peso_promedio_kg": 2.0,
        "vacunas_obligatorias": ["mixomatosis", "vhd"],
    },
    "roedor": {
        "nombre": "Roedor",
        "categoria": "mamifero",
        "esperanza_vida_anios": 3,
        "peso_promedio_kg": 0.3,
        "vacunas_obligatorias": [],
    },
    "ave": {
        "nombre": "Ave",
        "categoria": "ave",
        "esperanza_vida_anios": 10,
        "peso_promedio_kg": 0.3,
        "vacunas_obligatorias": [],
    },
    "reptil": {
        "nombre": "Reptil",
        "categoria": "reptil",
        "esperanza_vida_anios": 20,
        "peso_promedio_kg": 2.0,
        "vacunas_obligatorias": [],
    },
    "equino": {
        "nombre": "Equino",
        "categoria": "mamifero",
        "esperanza_vida_anios": 25,
        "peso_promedio_kg": 500.0,
        "vacunas_obligatorias": ["rabia", "influenza equina", "tétanos"],
    },
}


def listar_especies() -> list[dict]:
    """Devuelve la lista completa de especies con su clave identificadora."""
    resultado = []
    for clave, datos in ESPECIES.items():
        item = {"id": clave, **datos}
        resultado.append(item)
    return resultado


def obtener_especie(nombre: str) -> Optional[dict]:
    """Obtiene los detalles de una especie por su nombre o clave (case-insensitive)."""
    if not nombre:
        return None
    clave = str(nombre).strip().lower()
    return ESPECIES.get(clave)
