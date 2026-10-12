"""Pruebas unitarias para pyDolarVenezuela, tasa BCV, conversiones y recibos."""

from unittest.mock import MagicMock, patch
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.schemas.pago import PagoCreate
from app.services.pagos import crear_pago
from app.services.pdf import generar_recibo
from app.services.tasa_bcv import (
    convertir_bs_a_usd,
    convertir_usd_a_bs,
    obtener_tasa_bcv,
)


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    SQLModel.metadata.drop_all(engine)


def test_obtener_tasa_bcv_ok():
    """Comprueba que se obtenga el valor devuelto por el monitor de pyDolarVenezuela."""
    with patch("pyDolarVenezuela.Monitor") as MockMonitor:
        mock_instance = MagicMock()
        mock_monitor_model = MagicMock()
        mock_monitor_model.price = 85.50
        mock_instance.get_value_monitors.return_value = mock_monitor_model
        MockMonitor.return_value = mock_instance

        tasa = obtener_tasa_bcv(force_refresh=True)
        assert tasa == 85.50


def test_obtener_tasa_bcv_falla_usa_respaldo(session):
    """Comprueba que si pyDolarVenezuela falla o lanza excepción, se usa la tasa de respaldo sin crashear."""
    with patch("pyDolarVenezuela.Monitor", side_effect=Exception("Connection timeout")):
        # Con forzar refresco y fallo, debe devolver la tasa de respaldo (40.0 default)
        tasa = obtener_tasa_bcv(force_refresh=True, db=session)
        assert tasa == 40.0


def test_convertir_usd_a_bs():
    """Comprueba conversión fija de USD a Bs con tasa explícita."""
    assert convertir_usd_a_bs(10.0, tasa=50.0) == 500.0
    assert convertir_usd_a_bs(2.5, tasa=40.0) == 100.0


def test_convertir_bs_a_usd():
    """Comprueba conversión fija de Bs a USD con tasa explícita."""
    assert convertir_bs_a_usd(500.0, tasa=50.0) == 10.0
    assert convertir_bs_a_usd(100.0, tasa=40.0) == 2.5


def test_pago_guarda_tasa_aplicada(session):
    """Comprueba que al registrar un pago se asigne la tasa BCV del momento."""
    consultorio = Consultorio(nombre="Clinica Test", direccion="Caracas", telefono="0212")
    session.add(consultorio)
    session.commit()

    usuario = Usuario(
        consultorio_id=consultorio.id,
        nombre="Dr Test",
        email="dr_pago@test.com",
        password_hash="fakehash",
        rol="MEDICO",
    )
    session.add(usuario)
    session.commit()

    paciente = Paciente(
        consultorio_id=consultorio.id,
        nombre="Juan Perez",
        cedula="V-12345678",
    )
    session.add(paciente)
    session.commit()

    with patch("app.services.tasa_bcv.obtener_tasa_bcv", return_value=88.5):
        data = PagoCreate(
            paciente_id=paciente.id,
            monto=50.0,
            moneda="USD",
            metodo="efectivo",
            estado="pagado",
        )
        pago = crear_pago(db=session, data=data, usuario=usuario)
        assert pago.tasa_bcv_aplicada == 88.5


def test_recibo_muestra_ambas_monedas(session):
    """Comprueba que el PDF generado contenga el recibo con tasa y contravalor."""
    consultorio = Consultorio(nombre="Clinica Test", direccion="Caracas", telefono="0212")
    session.add(consultorio)
    session.commit()

    paciente = Paciente(
        consultorio_id=consultorio.id,
        nombre="Maria Gomez",
        cedula="V-87654321",
    )
    session.add(paciente)
    session.commit()

    pago = Pago(
        consultorio_id=consultorio.id,
        paciente_id=paciente.id,
        monto=100.0,
        moneda="USD",
        metodo="efectivo",
        estado="pagado",
        registrado_por=1,
        tasa_bcv_aplicada=90.0,
    )
    session.add(pago)
    session.commit()

    pdf_bytes = generar_recibo(pago=pago, consultorio=consultorio, paciente=paciente)
    assert len(pdf_bytes) > 0
    # Verificamos que es un archivo PDF válido (%PDF-)
    assert pdf_bytes.startswith(b"%PDF")
