"""Catálogo de razas por especie veterinaria para AltaPet."""

from typing import List

RAZAS = {
    "perro": [
        "Labrador Retriever", "Golden Retriever", "Pastor Alemán",
        "Bulldog Francés", "Beagle", "Poodle", "Chihuahua",
        "Yorkshire Terrier", "Schnauzer", "Rottweiler", "Mestizo", "Otro"
    ],
    "gato": [
        "Siamés", "Persa", "Maine Coon", "Bengalí",
        "Angora", "Ragdoll", "Sphynx", "Mestizo", "Otro"
    ],
    "conejo": [
        "Conejo común", "Angora", "Belier", "Rex", "Cabeza de león", "Otro"
    ],
    "roedor": [
        "Hámster", "Cobaya", "Chinchilla", "Jerbo", "Hurón", "Otro"
    ],
    "ave": [
        "Periquito", "Canario", "Loro", "Cacatúa",
        "Agapornis", "Ninfa", "Guacamayo", "Otro"
    ],
    "reptil": [
        "Tortuga", "Iguana", "Serpiente", "Gecko", "Camaleón", "Otro"
    ],
    "equino": [
        "Pura Sangre", "Cuarto de Milla", "Árabe",
        "Criollo", "Pony", "Appaloosa", "Otro"
    ],
}


def listar_razas(especie: str) -> List[str]:
    """Devuelve la lista de razas correspondientes a una especie dada."""
    if not especie:
        return []
    clave = str(especie).strip().lower()
    return RAZAS.get(clave, ["Mestizo", "Otro"])


def es_raza_valida(especie: str, raza: str) -> bool:
    """Verifica si una raza pertenece al catálogo de la especie indicada."""
    if not especie or not raza:
        return False
    clave = str(especie).strip().lower()
    razas_disponibles = RAZAS.get(clave, [])
    # Comparación case-insensitive
    return any(r.lower() == str(raza).strip().lower() for r in razas_disponibles)
