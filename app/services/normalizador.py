"""Normalizador de texto clínico — diagnósticos y medicamentos.

100% Python puro. Sin IA. Sin red. Determinista.
Limpia y estandariza nombres de medicamentos y diagnósticos
para facilitar búsquedas y estadísticas.
"""

import re
import unicodedata


def _quitar_tildes(texto: str) -> str:
    """Elimina diacríticos (tildes, diéresis) de una cadena."""
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Medicamentos frecuentes en español (nombre genérico normalizado)
# Editable por el administrador del consultorio.
# ---------------------------------------------------------------------------
MEDICAMENTOS_CONOCIDOS: list[str] = [
    "Ibuprofeno",
    "Paracetamol",
    "Amoxicilina",
    "Azitromicina",
    "Metformina",
    "Losartán",
    "Enalapril",
    "Amlodipino",
    "Atorvastatina",
    "Omeprazol",
    "Ranitidina",
    "Metronidazol",
    "Ciprofloxacino",
    "Diclofenac",
    "Dexametasona",
    "Prednisona",
    "Salbutamol",
    "Loratadina",
    "Cetirizina",
    "Clonazepam",
    "Alprazolam",
    "Sertralina",
    "Fluoxetina",
    "Levotiroxina",
    "Insulina",
    "Warfarina",
    "Heparina",
    "Aspirina",
    "Clopidogrel",
    "Furosemida",
    "Espironolactona",
]

# Mapa de alias → nombre normalizado (minúsculas sin tildes → nombre limpio)
_ALIAS_MEDS: dict[str, str] = {_quitar_tildes(m.lower()): m for m in MEDICAMENTOS_CONOCIDOS}


def normalizar_medicamento(nombre: str) -> str:
    """Normaliza el nombre de un medicamento.

    1. Limpia espacios y caracteres raros.
    2. Intenta mapear al nombre genérico conocido.
    3. Si no lo reconoce, capitaliza el texto limpio.

    Ejemplo:
        "ibuprofeno 400mg" → "Ibuprofeno"
        "amoxiclina" → "Amoxiclina" (no match, devuelve capitalizado)
    """
    nombre = nombre.strip()
    if not nombre:
        return ""
    # Quitar dosis (números + unidades al final, ej: "400mg", "500 mg", "1g")
    nombre_base = re.sub(r"\s*\d+\s*(?:mg|g|ml|mcg|ug|ui|u\.?i\.?)\b.*$", "", nombre, flags=re.IGNORECASE)
    nombre_base = nombre_base.strip()
    clave = _quitar_tildes(nombre_base.lower())
    return _ALIAS_MEDS.get(clave, nombre_base.capitalize())


def normalizar_lista_medicamentos(texto: str) -> str:
    """Normaliza una lista de medicamentos separados por comas o saltos de línea.

    Devuelve string con medicamentos normalizados separados por ", ".
    Elimina duplicados preservando orden.

    Ejemplo:
        "ibuprofeno, Paracetamol 500mg\\namoxicilina" → "Ibuprofeno, Paracetamol, Amoxicilina"
    """
    if not texto or not texto.strip():
        return ""
    # Separar por coma, punto y coma, o salto de línea
    partes = re.split(r"[,;\n]+", texto)
    normalizados = []
    vistos: set[str] = set()
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        norm = normalizar_medicamento(parte)
        if norm and norm.lower() not in vistos:
            normalizados.append(norm)
            vistos.add(norm.lower())
    return ", ".join(normalizados)


# ---------------------------------------------------------------------------
# Diagnósticos orientativos (texto libre → código CIE-10 sugerido)
# SOLO ORIENTATIVO — el profesional valida y firma.
# ---------------------------------------------------------------------------
_CIE10_TABLA: list[tuple[list[str], str, str]] = [
    # (palabras clave, código, descripción)
    (["hipertension", "hta", "presion alta"], "I10", "Hipertensión esencial"),
    (["diabetes", "dm2", "diabetico"], "E11", "Diabetes mellitus tipo 2"),
    (["diabetes tipo 1", "dm1"], "E10", "Diabetes mellitus tipo 1"),
    (["gripe", "influenza", "gripal"], "J10", "Influenza"),
    (["resfriado", "catarro", "rinitis viral"], "J00", "Rinofaringitis aguda"),
    (["amigdalitis", "faringitis", "faringoamigdalitis"], "J02", "Faringitis aguda"),
    (["bronquitis aguda"], "J20", "Bronquitis aguda"),
    (["asma", "broncoespasmo"], "J45", "Asma"),
    (["neumonía", "neumonia", "pulmonía"], "J18", "Neumonía"),
    (["gastroenteritis", "diarrea aguda", "gastritis aguda"], "K29", "Gastritis y duodenitis"),
    (["ulcera gastrica", "ulcera peptica"], "K25", "Úlcera gástrica"),
    (["colitis", "colon irritable", "sindrome intestino irritable"], "K58", "Síndrome del intestino irritable"),
    (["infeccion urinaria", "itu", "cistitis"], "N39", "Infección del tracto urinario"),
    (["anemia", "ferropenica"], "D50", "Anemia por deficiencia de hierro"),
    (["hipotiroidismo"], "E03", "Hipotiroidismo"),
    (["hipertiroidismo"], "E05", "Hipertiroidismo"),
    (["depresion", "episodio depresivo"], "F32", "Episodio depresivo"),
    (["ansiedad", "trastorno ansioso"], "F41", "Trastorno de ansiedad"),
    (["lumbalgia", "dolor lumbar", "lumbago"], "M54", "Dolor de espalda"),
    (["artritis", "artralgia"], "M13", "Artritis"),
    (["migraña", "migrana", "jaqueca", "cefalea migranosa"], "G43", "Migraña"),
    (["cefalea", "dolor cabeza"], "R51", "Cefalea"),
    (["conjuntivitis"], "H10", "Conjuntivitis"),
    (["otitis"], "H66", "Otitis media supurativa"),
    (["dermatitis", "eczema"], "L30", "Dermatitis"),
    (["urticaria"], "L50", "Urticaria"),
    (["fractura"], "T14", "Traumatismo no especificado"),
    (["control", "revision", "chequeo", "preventivo"], "Z00", "Examen médico general"),
]


def sugerir_cie10(diagnostico: str) -> tuple[str, str]:
    """Sugiere un código CIE-10 basado en el texto libre del diagnóstico.

    ADVERTENCIA: Solo es orientativo. El profesional valida y asigna el código final.
    Retorna tupla (codigo, descripcion). Si no hay match: ("", "").

    Determinista: mismo texto → mismo resultado.
    """
    if not diagnostico or not diagnostico.strip():
        return ("", "")
    clave = _quitar_tildes(diagnostico.lower())
    for palabras, codigo, descripcion in _CIE10_TABLA:
        for kw in palabras:
            if kw in clave:
                return (codigo, descripcion)
    return ("", "")


def normalizar_diagnostico(texto: str) -> tuple[str, str]:
    """Normaliza el texto del diagnóstico y sugiere código CIE-10.

    Retorna (texto_limpio, codigo_cie10).
    El código puede estar vacío si no hay match.
    """
    texto = texto.strip() if texto else ""
    if not texto:
        return ("", "")
    # Limpiar espacios múltiples
    texto_limpio = re.sub(r"\s+", " ", texto)
    codigo, _ = sugerir_cie10(texto_limpio)
    return (texto_limpio, codigo)
