"""Servicio de generación de recibos en formato PDF con fpdf2 y DejaVu — Módulo 8."""

import os
from typing import Optional

from fpdf import FPDF

from app.models.consulta import Consulta
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.pago import Pago


def generar_recibo(
    pago: Pago,
    consultorio: Consultorio,
    paciente: Paciente,
    consulta: Optional[Consulta] = None,
) -> bytes:
    """Genera un recibo en PDF utilizando fpdf2 y la fuente DejaVu (soporte UTF-8 completo).

    Guarda una copia en data/recibos/recibo_{pago.id}.pdf y retorna los bytes del PDF.
    """
    os.makedirs("data/recibos", exist_ok=True)

    pdf = FPDF(format="A5", orientation="P")  # Formato A5 ideal para recibos médicos
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Cargar fuentes DejaVu
    font_path = "app/static/fonts/DejaVuSans.ttf"
    font_bold_path = "app/static/fonts/DejaVuSans-Bold.ttf"

    usa_dejavu = os.path.exists(font_path) and os.path.exists(font_bold_path)
    if usa_dejavu:
        pdf.add_font("DejaVu", "", font_path)
        pdf.add_font("DejaVu", "B", font_bold_path)
        family = "DejaVu"
    else:
        family = "Helvetica"

    # 1. Encabezado de la institución
    pdf.set_font(family, "B", 18)
    pdf.cell(0, 8, "Alta", ln=True, align="C")

    pdf.set_font(family, "B", 13)
    pdf.cell(0, 6, consultorio.nombre, ln=True, align="C")

    pdf.set_font(family, "", 9)
    if consultorio.direccion:
        pdf.cell(0, 5, f"Dirección: {consultorio.direccion}", ln=True, align="C")
    if consultorio.telefono:
        pdf.cell(0, 5, f"Teléfono: {consultorio.telefono}", ln=True, align="C")

    pdf.ln(5)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(15, pdf.get_y(), 133, pdf.get_y())
    pdf.ln(5)

    # 2. Número de recibo y Fecha
    # Formato REC-YYYYMMDD-XXXX
    codigo_recibo = f"REC-{pago.fecha.strftime('%Y%m%d')}-{pago.id:04d}"

    pdf.set_font(family, "B", 10)
    pdf.cell(70, 6, f"Recibo N°: {codigo_recibo}")
    pdf.set_font(family, "", 10)
    pdf.cell(0, 6, f"Fecha: {pago.fecha.strftime('%d/%m/%Y %H:%M')}", ln=True, align="R")

    pdf.ln(3)

    # 3. Datos del Paciente
    pdf.set_font(family, "B", 10)
    pdf.cell(0, 6, "DATOS DEL PACIENTE", ln=True)

    pdf.set_font(family, "", 9)
    pdf.cell(30, 5, "Nombre:")
    pdf.set_font(family, "B", 9)
    pdf.cell(0, 5, paciente.nombre, ln=True)

    pdf.set_font(family, "", 9)
    pdf.cell(30, 5, "Cédula / Doc:")
    pdf.cell(0, 5, paciente.cedula or "No registrada", ln=True)

    if paciente.tipo == "MASCOTA":
        pdf.cell(30, 5, "Tipo:")
        pdf.cell(0, 5, f"Mascota ({paciente.especie or 'Animal'})", ln=True)

    pdf.ln(5)

    # 4. Detalle y Concepto
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font(family, "B", 9)
    pdf.cell(85, 7, " Concepto", fill=True, border=1)
    pdf.cell(33, 7, " Monto", fill=True, border=1, ln=True, align="R")

    pdf.set_font(family, "", 9)
    concepto = "Atención médica / Consulta"
    if consulta and consulta.motivo:
        concepto = f"Consulta: {consulta.motivo}"

    monto_fmt = f"{pago.moneda} {pago.monto:,.2f}"
    pdf.cell(85, 8, f" {concepto}", border=1)
    pdf.cell(33, 8, f" {monto_fmt} ", border=1, ln=True, align="R")

    # 5. Total y Método
    pdf.set_font(family, "B", 10)
    pdf.cell(85, 8, " TOTAL PAGADO:", border=1, align="R")
    pdf.cell(33, 8, f" {monto_fmt} ", border=1, ln=True, align="R")

    # Si hay tasa BCV aplicada, mostrar conversión de moneda complementaria
    tasa_aplicada = getattr(pago, "tasa_bcv_aplicada", None)
    if tasa_aplicada and tasa_aplicada > 0:
        pdf.set_font(family, "", 8)
        if pago.moneda == "USD":
            monto_equiv = pago.monto * tasa_aplicada
            pdf.cell(0, 5, f"Equivalente: VES {monto_equiv:,.2f}  (Tasa oficial BCV: {tasa_aplicada:,.2f} Bs/USD)", ln=True, align="R")
        elif pago.moneda in ("VES", "BS"):
            monto_equiv = pago.monto / tasa_aplicada
            pdf.cell(0, 5, f"Equivalente: USD ${monto_equiv:,.2f}  (Tasa oficial BCV: {tasa_aplicada:,.2f} Bs/USD)", ln=True, align="R")

    pdf.ln(3)
    pdf.set_font(family, "", 8)
    metodo_str = pago.metodo.capitalize() if pago.metodo else "Efectivo"
    estado_str = pago.estado.upper()
    pdf.cell(0, 5, f"Método de pago: {metodo_str}  |  Estado: {estado_str}", ln=True)

    # 6. Pie de página
    pdf.ln(10)
    pdf.set_font(family, "", 9)
    pdf.cell(0, 5, "Gracias por su preferencia", ln=True, align="C")

    # Guardar archivo en disco
    ruta_archivo = f"data/recibos/recibo_{pago.id}.pdf"
    pdf.output(ruta_archivo)

    # Devolver bytes
    return bytes(pdf.output())
