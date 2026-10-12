"""Servicio de gestión y generación de datos de ejemplo (Modo Demo) — Módulo 10 y AltaPet."""

from datetime import date, datetime, timedelta, timezone
import random
from typing import Optional

from faker import Faker
from sqlmodel import Session, col, func, select

from app.models.cita import Cita
from app.models.consulta import Consulta
from app.models.consultorio import Consultorio
from app.models.dueno import Dueno
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.vacuna import Vacuna
from app.services.cifrado import cifrar

_NOTAS_EJEMPLO = [
    ("Control de rutina", "Paciente acude para revisión anual periódica. Sin sintomatología aguda.", "Dieta balanceada e hidratación abundante.", "Paciente clínicamente sano"),
    ("Cefalea recurrente", "Refiere dolor pulsátil en región frontal que cede parcialmente con analgésicos comunes.", "Ibuprofeno 400mg cada 8h en caso de dolor. Descanso visual.", "Cefalea tensional"),
    ("Gastroenteritis aguda", "Cuadro de 24 horas de evolución con náuseas y malestar general tras ingesta alimentaria.", "Sales de rehidratación oral. Dieta blanda por 48 horas.", "Gastroenteritis probable viral"),
    ("Hipertensión arterial", "Control de presión arterial. Cifras ligeramente elevadas respecto al basal.", "Continuar con Enalapril 10mg diario. Reducir consumo de sodio.", "Hipertensión arterial estadio 1"),
    ("Lumbago mecánico", "Dolor lumbar bajo posterior a esfuerzo físico moderado. Maniobras de estiramiento positivas.", "Calor local, Paracetamol 1g cada 8h. Ejercicios de elongación.", "Lumbago mecánico agudo"),
    ("Faringoamigdalitis", "Dolor deglutorio y febrícula de 2 días. Hiperemia faríngea sin placas purulentas.", "Ibuprofeno 600mg cada 8 horas, gárgaras con solución salina.", "Faringitis aguda"),
    ("Dermatitis de contacto", "Prurito y eritema en miembros superiores tras exposición a detergente industrial.", "Crema hidratante neutra y Cetirizina 10mg en la noche por 5 días.", "Dermatitis por contacto"),
    ("Chequeo preventivo", "Evaluación médica general solicitada por el paciente. Constantes vitales dentro de parámetros normales.", "Mantener actividad física regular y control en 12 meses.", "Examen médico general"),
]

_MOTIVOS_CITAS = [
    "Consulta general",
    "Control de rutina",
    "Revisión de exámenes",
    "Dolor abdominal",
    "Seguimiento de tratamiento",
    "Evaluación médica",
    "Chequeo preventivo",
]

# Catálogos veterinarios deterministas para Modo Demo AltaPet
_MOTIVOS_CITAS_VET = [
    "Vacunación",
    "Desparasitación",
    "Control postoperatorio",
    "Corte de uñas",
    "Limpieza dental",
    "Consulta general",
    "Revisión de piel",
    "Problema digestivo",
    "Esterilización",
]

_NOTAS_EJEMPLO_VET = [
    (
        "Gastroenteritis canina",
        "Canino presenta vómitos y deposiciones líquidas de 24h. Mucosas rosadas, abdomen blando no doloroso.",
        "Dieta blanda gastrointestinal, hidratación oral, metronidazol 10mg/kg cada 12h por 5 días.",
        "Gastroenteritis aguda infecciosa",
        "metronidazol 10mg/kg",
    ),
    (
        "Dermatitis alérgica por pulgas",
        "Prurito intenso en zona lumbosacra con alopecia parcial y eritema. Presencia de deyecciones de pulgas.",
        "Antiparasitario externo pipeta, champú medicado cada 3 días, meloxicam 0.1mg/kg cada 24h por 3 días.",
        "DAP (Dermatitis alérgica a picadura de pulga)",
        "meloxicam 0.1mg/kg",
    ),
    (
        "Otitis externa",
        "Sacudidas frecuentes de cabeza y rascado auricular bilateral. Exudado ceruminoso marrón oscuro abundante.",
        "Limpieza ótica diaria, gotas óticas antibióticas/antiinflamatorias cada 12h x 7 días, amoxicilina 10mg/kg cada 12h.",
        "Otitis externa bacteriana/fúngica",
        "amoxicilina 10mg/kg",
    ),
    (
        "Parasitosis intestinal",
        "Decaimiento leve, pérdida de apetito y abdomen distendido en cachorro.",
        "Praziquantel 5mg/kg dosis única, repetir a los 15 días. Probióticos en alimento.",
        "Parasitosis gastrointestinal por nematodos",
        "praziquantel 5mg/kg",
    ),
    (
        "Control de peso",
        "Paciente acude a chequeo nutricional por sobrepeso. Constantes cardíacas y respiratorias estables.",
        "Reducción de ración al 20%, paseos diarios guiados de 30 minutos.",
        "Sobrepeso grado 1",
        "control dietético",
    ),
    (
        "Reacción post-vacunal",
        "Edema facial leve transitorio posterior a vacunación anual. Sin compromiso de vías aéreas.",
        "Dexametasona 0.2mg/kg inyectable dosis única. Observación por 2 horas.",
        "Hipersensibilidad tipo I leve post-vacunal",
        "dexametasona 0.2mg/kg",
    ),
    (
        "Conjuntivitis felina",
        "Secreción ocular mucopurulenta bilateral, blefaroespasmo y congestión conjuntival.",
        "Colirio oftálmico con tobramicina cada 8 horas por 7 días. Limpieza con suero fisiológico.",
        "Conjuntivitis bilateral infecciosa",
        "tobramicina oftálmica",
    ),
]

_NOMBRES_MASCOTAS_DEMO = [
    "Rocky", "Max", "Luna", "Milo", "Nina",
    "Simba", "Coco", "Bella", "Toby", "Pelusa",
    "Firulais", "Duna", "Rocco", "Kiara", "Manchas",
    "Bobi", "Nala", "Zeus", "Chispa", "Canela"
]

_CONFIG_ESPECIES_DEMO = [
    # 10 perros
    {"especie": "perro", "raza": "Labrador Retriever", "peso_min": 25.0, "peso_max": 35.0},
    {"especie": "perro", "raza": "Golden Retriever", "peso_min": 26.0, "peso_max": 34.0},
    {"especie": "perro", "raza": "Beagle", "peso_min": 9.0, "peso_max": 14.0},
    {"especie": "perro", "raza": "Mestizo", "peso_min": 10.0, "peso_max": 22.0},
    {"especie": "perro", "raza": "Poodle", "peso_min": 4.0, "peso_max": 8.0},
    {"especie": "perro", "raza": "Pastor Alemán", "peso_min": 28.0, "peso_max": 38.0},
    {"especie": "perro", "raza": "Schnauzer", "peso_min": 6.0, "peso_max": 15.0},
    {"especie": "perro", "raza": "Rottweiler", "peso_min": 35.0, "peso_max": 45.0},
    {"especie": "perro", "raza": "Chihuahua", "peso_min": 2.0, "peso_max": 4.0},
    {"especie": "perro", "raza": "Yorkshire Terrier", "peso_min": 2.5, "peso_max": 4.0},
    # 5 gatos
    {"especie": "gato", "raza": "Siamés", "peso_min": 3.5, "peso_max": 5.5},
    {"especie": "gato", "raza": "Persa", "peso_min": 3.0, "peso_max": 6.0},
    {"especie": "gato", "raza": "Mestizo", "peso_min": 3.0, "peso_max": 5.0},
    {"especie": "gato", "raza": "Angora", "peso_min": 3.5, "peso_max": 5.5},
    {"especie": "gato", "raza": "Bengalí", "peso_min": 4.0, "peso_max": 7.0},
    # 2 conejos
    {"especie": "conejo", "raza": "Conejo común", "peso_min": 1.5, "peso_max": 2.8},
    {"especie": "conejo", "raza": "Belier", "peso_min": 1.8, "peso_max": 2.5},
    # 2 aves
    {"especie": "ave", "raza": "Periquito", "peso_min": 0.03, "peso_max": 0.05},
    {"especie": "ave", "raza": "Canario", "peso_min": 0.02, "peso_max": 0.04},
    # 1 roedor
    {"especie": "roedor", "raza": "Hámster", "peso_min": 0.1, "peso_max": 0.25},
]

_ESTADOS_CITAS = ["pendiente", "confirmada", "completada"]
_METODOS_PAGOS = ["efectivo", "zelle", "transferencia", "binance"]


def generar_datos_demo(
    db: Session,
    consultorio_id: int,
    usuario_id: int,
) -> dict[str, int]:
    """Genera datos de demostración según la especialidad del consultorio.

    Detecta si el consultorio es VETERINARIO o MEDICO.
    Todos los registros creados llevan estrictamente demo=True.
    """
    consultorio = db.get(Consultorio, consultorio_id)
    if consultorio and getattr(consultorio, "tipo", "MEDICO") == "VETERINARIO":
        return _generar_demo_veterinario(db, consultorio_id, usuario_id)
    else:
        return _generar_demo_humano(db, consultorio_id, usuario_id)


def _generar_demo_humano(
    db: Session,
    consultorio_id: int,
    usuario_id: int,
) -> dict[str, int]:
    """Genera datos de demostración para consultorios médicos humanos."""
    fake = Faker("es_ES")
    ahora = datetime.now(timezone.utc)

    # 1. 20 Pacientes humanos con demo=True
    pacientes_creados: list[Paciente] = []
    for _ in range(20):
        genero = random.choice(["M", "F"])
        nombre = fake.name_female() if genero == "F" else fake.name_male()
        cedula = f"V-{fake.random_int(min=10000000, max=32000000)}"
        telefono = fake.phone_number()[:15]
        email = fake.email()
        f_nac = fake.date_of_birth(minimum_age=18, maximum_age=75)

        p = Paciente(
            consultorio_id=consultorio_id,
            tipo="HUMANO",
            nombre=nombre,
            cedula=cedula,
            telefono=telefono,
            email=email,
            fecha_nacimiento=f_nac,
            alergias=random.choice([None, "Penicilina", "Sulfas", "Aspirina", None, None]),
            notas_generales="Paciente demo generado para pruebas de demostración.",
            demo=True,
            creado_en=ahora - timedelta(days=random.randint(15, 60)),
        )
        db.add(p)
        pacientes_creados.append(p)

    db.commit()
    for p in pacientes_creados:
        db.refresh(p)

    # 2. 50 Citas con demo=True (25 pasadas, 25 futuras)
    citas_creadas: list[Cita] = []
    for _ in range(25):
        paciente = random.choice(pacientes_creados)
        dias_atras = random.randint(1, 14)
        hora = random.randint(8, 17)
        minuto = random.choice([0, 30])
        dt = (ahora - timedelta(days=dias_atras)).replace(hour=hora, minute=minuto, second=0, microsecond=0)

        c = Cita(
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=usuario_id,
            fecha_hora=dt,
            duracion_min=30,
            estado=random.choice(["completada", "confirmada"]),
            motivo=random.choice(_MOTIVOS_CITAS),
            creada_por=usuario_id,
            demo=True,
            creado_en=dt - timedelta(days=2),
        )
        db.add(c)
        citas_creadas.append(c)

    for _ in range(25):
        paciente = random.choice(pacientes_creados)
        dias_adelante = random.randint(1, 14)
        hora = random.randint(8, 17)
        minuto = random.choice([0, 30])
        dt = (ahora + timedelta(days=dias_adelante)).replace(hour=hora, minute=minuto, second=0, microsecond=0)

        c = Cita(
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=usuario_id,
            fecha_hora=dt,
            duracion_min=30,
            estado=random.choice(["pendiente", "confirmada"]),
            motivo=random.choice(_MOTIVOS_CITAS),
            creada_por=usuario_id,
            demo=True,
            creado_en=ahora,
        )
        db.add(c)
        citas_creadas.append(c)

    db.commit()
    for c in citas_creadas:
        db.refresh(c)

    # 3. 30 Consultas médicas con demo=True
    consultas_creadas: list[Consulta] = []
    for _ in range(30):
        paciente = random.choice(pacientes_creados)
        motivo, nota_plana, indicaciones_plana, diag_plano = random.choice(_NOTAS_EJEMPLO)
        dias_atras = random.randint(1, 25)
        dt_consulta = ahora - timedelta(days=dias_atras)

        con = Consulta(
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=usuario_id,
            fecha=dt_consulta,
            motivo=motivo,
            nota=cifrar(nota_plana),
            indicaciones=cifrar(indicaciones_plana),
            diagnostico=cifrar(diag_plano),
            proxima_cita=dt_consulta + timedelta(days=30) if random.random() > 0.5 else None,
            demo=True,
            creado_en=dt_consulta,
        )
        db.add(con)
        consultas_creadas.append(con)

    db.commit()
    for con in consultas_creadas:
        db.refresh(con)

    # 4. 15 Pagos con demo=True entre 20 y 100 USD
    pagos_creados: list[Pago] = []
    for _ in range(15):
        paciente = random.choice(pacientes_creados)
        monto = float(random.choice([20.0, 30.0, 40.0, 50.0, 60.0, 75.0, 80.0, 100.0]))
        dias_atras = random.randint(1, 20)
        dt_pago = ahora - timedelta(days=dias_atras)

        pago = Pago(
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            monto=monto,
            moneda="USD",
            metodo=random.choice(_METODOS_PAGOS),
            estado="pagado",
            fecha=dt_pago,
            registrado_por=usuario_id,
            demo=True,
        )
        db.add(pago)
        pagos_creados.append(pago)

    db.commit()

    return {
        "pacientes": len(pacientes_creados),
        "citas": len(citas_creadas),
        "consultas": len(consultas_creadas),
        "pagos": len(pagos_creados),
    }


def _generar_demo_veterinario(
    db: Session,
    consultorio_id: int,
    usuario_id: int,
) -> dict[str, int]:
    """Genera datos de demostración específicos para AltaPet.

    Genera:
    - 20 Dueños (Dueno con demo=True)
    - 20 Mascotas (Paciente tipo MASCOTA con especie, raza, peso, chip y dueno_id)
    - 50 Citas con motivos veterinarios
    - 30 Consultas con notas y medicamentos veterinarios
    - 15 Pagos
    - ~40 Vacunas históricas y de control con demo=True
    """
    fake = Faker("es_ES")
    ahora = datetime.now(timezone.utc)
    hoy = ahora.date()

    # 1. 20 Dueños humanos
    duenos_creados: list[Dueno] = []
    for _ in range(20):
        nombre_dueno = fake.name()
        cedula_dueno = f"V-{fake.random_int(min=10000000, max=32000000)}"
        telefono_dueno = fake.phone_number()[:15]
        email_dueno = fake.email()
        dir_dueno = fake.address().replace("\n", ", ")[:100]

        d = Dueno(
            consultorio_id=consultorio_id,
            nombre=nombre_dueno,
            cedula=cedula_dueno,
            telefono=telefono_dueno,
            email=email_dueno,
            direccion=dir_dueno,
            demo=True,
            creado_en=ahora - timedelta(days=random.randint(20, 60)),
        )
        db.add(d)
        duenos_creados.append(d)

    db.commit()
    for d in duenos_creados:
        db.refresh(d)

    # 2. 20 Mascotas con distribución precisa
    mascotas_creadas: list[Paciente] = []
    for i in range(20):
        nombre_mascota = _NOMBRES_MASCOTAS_DEMO[i]
        cfg = _CONFIG_ESPECIES_DEMO[i]
        especie = cfg["especie"]
        raza = cfg["raza"]
        peso = round(random.uniform(cfg["peso_min"], cfg["peso_max"]), 2)
        dueno = duenos_creados[i]  # 1 dueño por mascota

        # Fecha de nacimiento variada (cachorro/joven/adulto)
        edad_meses = random.randint(4, 96)
        fecha_nac = hoy - timedelta(days=edad_meses * 30)

        # Microchip de 15 dígitos determinista único
        chip = f"981098{100000000 + i}"

        m = Paciente(
            consultorio_id=consultorio_id,
            tipo="MASCOTA",
            nombre=nombre_mascota,
            especie=especie,
            raza=raza,
            peso_kg=peso,
            microchip=chip,
            dueno_id=dueno.id,
            fecha_nacimiento=fecha_nac,
            telefono=dueno.telefono,
            email=dueno.email,
            alergias=random.choice([None, "Picadura de pulga", "Polen", None, None]),
            notas_generales="Mascota demo generada para pruebas de AltaPet.",
            demo=True,
            creado_en=ahora - timedelta(days=random.randint(15, 60)),
        )
        db.add(m)
        mascotas_creadas.append(m)

    db.commit()
    for m in mascotas_creadas:
        db.refresh(m)

    # 3. 50 Citas veterinarias (25 pasadas, 25 futuras)
    citas_creadas: list[Cita] = []
    for _ in range(25):
        mascota = random.choice(mascotas_creadas)
        dias_atras = random.randint(1, 14)
        hora = random.randint(8, 17)
        minuto = random.choice([0, 30])
        dt = (ahora - timedelta(days=dias_atras)).replace(hour=hora, minute=minuto, second=0, microsecond=0)

        c = Cita(
            consultorio_id=consultorio_id,
            paciente_id=mascota.id,
            profesional_id=usuario_id,
            fecha_hora=dt,
            duracion_min=30,
            estado=random.choice(["completada", "confirmada"]),
            motivo=random.choice(_MOTIVOS_CITAS_VET),
            creada_por=usuario_id,
            demo=True,
            creado_en=dt - timedelta(days=2),
        )
        db.add(c)
        citas_creadas.append(c)

    for _ in range(25):
        mascota = random.choice(mascotas_creadas)
        dias_adelante = random.randint(1, 14)
        hora = random.randint(8, 17)
        minuto = random.choice([0, 30])
        dt = (ahora + timedelta(days=dias_adelante)).replace(hour=hora, minute=minuto, second=0, microsecond=0)

        c = Cita(
            consultorio_id=consultorio_id,
            paciente_id=mascota.id,
            profesional_id=usuario_id,
            fecha_hora=dt,
            duracion_min=30,
            estado=random.choice(["pendiente", "confirmada"]),
            motivo=random.choice(_MOTIVOS_CITAS_VET),
            creada_por=usuario_id,
            demo=True,
            creado_en=ahora,
        )
        db.add(c)
        citas_creadas.append(c)

    db.commit()
    for c in citas_creadas:
        db.refresh(c)

    # 4. 30 Consultas con motivos y medicamentos veterinarios
    consultas_creadas: list[Consulta] = []
    for _ in range(30):
        mascota = random.choice(mascotas_creadas)
        motivo, nota_plana, indicaciones_plana, diag_plano, med = random.choice(_NOTAS_EJEMPLO_VET)
        dias_atras = random.randint(1, 25)
        dt_consulta = ahora - timedelta(days=dias_atras)

        con = Consulta(
            consultorio_id=consultorio_id,
            paciente_id=mascota.id,
            profesional_id=usuario_id,
            fecha=dt_consulta,
            motivo=motivo,
            nota=cifrar(nota_plana),
            indicaciones=cifrar(indicaciones_plana),
            diagnostico=cifrar(diag_plano),
            medicamentos=med,
            proxima_cita=dt_consulta + timedelta(days=30) if random.random() > 0.5 else None,
            demo=True,
            creado_en=dt_consulta,
        )
        db.add(con)
        consultas_creadas.append(con)

    db.commit()
    for con in consultas_creadas:
        db.refresh(con)

    # 5. 15 Pagos entre 20 y 100 USD
    pagos_creados: list[Pago] = []
    for _ in range(15):
        mascota = random.choice(mascotas_creadas)
        monto = float(random.choice([20.0, 30.0, 40.0, 50.0, 60.0, 75.0, 80.0, 100.0]))
        dias_atras = random.randint(1, 20)
        dt_pago = ahora - timedelta(days=dias_atras)

        pago = Pago(
            consultorio_id=consultorio_id,
            paciente_id=mascota.id,
            monto=monto,
            moneda="USD",
            metodo=random.choice(_METODOS_PAGOS),
            estado="pagado",
            fecha=dt_pago,
            registrado_por=usuario_id,
            demo=True,
        )
        db.add(pago)
        pagos_creados.append(pago)

    db.commit()

    # 6. ~40 Vacunas según especie
    vacunas_creadas: list[Vacuna] = []
    # Vacunas por especie
    vacs_perro = ["moquillo", "parvovirus", "rabia"]
    vacs_gato = ["triple felina", "leucemia felina", "rabia"]
    vacs_conejo = ["mixomatosis", "vhd"]

    for mascota in mascotas_creadas:
        if mascota.especie == "perro":
            lista_vacs = vacs_perro
        elif mascota.especie == "gato":
            lista_vacs = vacs_gato
        elif mascota.especie == "conejo":
            lista_vacs = vacs_conejo
        else:
            lista_vacs = []  # aves y roedores sin vacunas

        for idx, tipo_vac in enumerate(lista_vacs):
            # Fecha aplicación en los últimos 6 meses
            dias_aplicacion = random.randint(30, 180)
            f_ap = hoy - timedelta(days=dias_aplicacion)

            # Distribuir próximas dosis:
            # - Algunas en próximos 7 días (alerta amarilla)
            # - Algunas vencidas (alerta roja)
            # - Algunas regulares a 6-12 meses
            if idx == 0 and random.random() < 0.4:
                # Próximos 2 a 6 días
                f_prox = hoy + timedelta(days=random.randint(2, 6))
            elif idx == 1 and random.random() < 0.4:
                # Vencida hace 5 a 20 días
                f_prox = hoy - timedelta(days=random.randint(5, 20))
            else:
                f_prox = f_ap + timedelta(days=365)

            v = Vacuna(
                consultorio_id=consultorio_id,
                paciente_id=mascota.id,
                tipo=tipo_vac,
                fecha_aplicacion=f_ap,
                proxima_dosis=f_prox,
                lote=f"LT-2026-{random.randint(100, 999)}",
                laboratorio=random.choice(["Zoetis", "Boehringer", "MSD", "Virbac"]),
                aplicada_por=usuario_id,
                notas=f"Dosis administrada en campaña demo para {mascota.nombre}",
                demo=True,
                creado_en=ahora - timedelta(days=dias_aplicacion),
            )
            db.add(v)
            vacunas_creadas.append(v)

    db.commit()

    return {
        "pacientes": len(mascotas_creadas),
        "citas": len(citas_creadas),
        "consultas": len(consultas_creadas),
        "pagos": len(pagos_creados),
        "duenos": len(duenos_creados),
        "vacunas": len(vacunas_creadas),
        "mascotas": len(mascotas_creadas),
    }


def borrar_datos_demo(
    db: Session,
    consultorio_id: int,
) -> dict[str, int]:
    """Elimina estrictamente los registros marcados con demo=True del consultorio.

    Orden de borrado para respetar dependencias relacionales:
    1. Vacunas (FK a paciente)
    2. Consultas (FK a paciente)
    3. Citas (FK a paciente)
    4. Pagos (FK a paciente)
    5. Pacientes (FK a dueno)
    6. Dueños

    NUNCA modifica ni borra registros con demo=False.
    """
    # 1. Borrar vacunas demo
    vacunas_demo = db.exec(
        select(Vacuna).where(
            Vacuna.consultorio_id == consultorio_id,
            Vacuna.demo == True,
        )
    ).all()
    count_vacunas = len(vacunas_demo)
    for vac in vacunas_demo:
        db.delete(vac)

    # 2. Borrar consultas demo
    consultas_demo = db.exec(
        select(Consulta).where(
            Consulta.consultorio_id == consultorio_id,
            Consulta.demo == True,
        )
    ).all()
    count_consultas = len(consultas_demo)
    for con in consultas_demo:
        db.delete(con)

    # 3. Borrar citas demo
    citas_demo = db.exec(
        select(Cita).where(
            Cita.consultorio_id == consultorio_id,
            Cita.demo == True,
        )
    ).all()
    count_citas = len(citas_demo)
    for c in citas_demo:
        db.delete(c)

    # 4. Borrar pagos demo
    pagos_demo = db.exec(
        select(Pago).where(
            Pago.consultorio_id == consultorio_id,
            Pago.demo == True,
        )
    ).all()
    count_pagos = len(pagos_demo)
    for p in pagos_demo:
        db.delete(p)

    # 5. Borrar pacientes demo (mascotas o humanos)
    pacientes_demo = db.exec(
        select(Paciente).where(
            Paciente.consultorio_id == consultorio_id,
            Paciente.demo == True,
        )
    ).all()
    count_pacientes = len(pacientes_demo)
    for pac in pacientes_demo:
        db.delete(pac)

    # 6. Borrar dueños demo
    duenos_demo = db.exec(
        select(Dueno).where(
            Dueno.consultorio_id == consultorio_id,
            Dueno.demo == True,
        )
    ).all()
    count_duenos = len(duenos_demo)
    for d in duenos_demo:
        db.delete(d)

    db.commit()

    return {
        "consultas": count_consultas,
        "citas": count_citas,
        "pagos": count_pagos,
        "pacientes": count_pacientes,
        "vacunas": count_vacunas,
        "duenos": count_duenos,
    }


def contar_datos_demo(
    db: Session,
    consultorio_id: int,
) -> dict[str, int]:
    """Retorna el conteo actual de registros marcados como demo=True en el consultorio."""
    pacientes_count = db.exec(
        select(func.count(col(Paciente.id))).where(
            Paciente.consultorio_id == consultorio_id,
            Paciente.demo == True,
        )
    ).one() or 0

    mascotas_count = db.exec(
        select(func.count(col(Paciente.id))).where(
            Paciente.consultorio_id == consultorio_id,
            Paciente.tipo == "MASCOTA",
            Paciente.demo == True,
        )
    ).one() or 0

    citas_count = db.exec(
        select(func.count(col(Cita.id))).where(
            Cita.consultorio_id == consultorio_id,
            Cita.demo == True,
        )
    ).one() or 0

    consultas_count = db.exec(
        select(func.count(col(Consulta.id))).where(
            Consulta.consultorio_id == consultorio_id,
            Consulta.demo == True,
        )
    ).one() or 0

    pagos_count = db.exec(
        select(func.count(col(Pago.id))).where(
            Pago.consultorio_id == consultorio_id,
            Pago.demo == True,
        )
    ).one() or 0

    vacunas_count = db.exec(
        select(func.count(col(Vacuna.id))).where(
            Vacuna.consultorio_id == consultorio_id,
            Vacuna.demo == True,
        )
    ).one() or 0

    duenos_count = db.exec(
        select(func.count(col(Dueno.id))).where(
            Dueno.consultorio_id == consultorio_id,
            Dueno.demo == True,
        )
    ).one() or 0

    return {
        "pacientes": pacientes_count,
        "citas": citas_count,
        "consultas": consultas_count,
        "pagos": pagos_count,
        "vacunas": vacunas_count,
        "duenos": duenos_count,
        "mascotas": mascotas_count,
        "total": (pacientes_count + citas_count + consultas_count + pagos_count + vacunas_count + duenos_count),
    }
