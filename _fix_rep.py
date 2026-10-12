with open('app/services/reportes.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
old = """    # Citas del período
    citas = db.exec(
        select(Cita).where(
            Cita.consultorio_id == consultorio_id,
            Cita.demo == False,
            Cita.fecha >= inicio,
            Cita.fecha <= fin,
        )
    ).all() if hasattr(Cita, "demo") else []"""

new = """    # Citas del período (excluye solicitudes de horario libre)
    citas = db.exec(
        select(Cita).where(
            Cita.consultorio_id == consultorio_id,
            Cita.demo == False,
            Cita.origen != "solicitud",
            Cita.fecha_hora >= inicio,
            Cita.fecha_hora <= fin,
        )
    ).all() if hasattr(Cita, "demo") else []"""

assert old in text, "Old citas query not found"
found_text = text.replace(old, new)

with open('app/services/reportes.py', 'w', encoding='utf-8') as f:
    f.write(found_text)

print('Reportes successfully updated')
