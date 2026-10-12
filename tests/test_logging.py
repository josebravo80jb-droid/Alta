"""Pruebas unitarias para enmascaramiento seguro en logs (Opaque Logger)."""

from app.services.logging_config import enmascarar_datos_sensibles


def test_log_enmascara_cedula():
    """Comprueba que cédulas venezolanas sean enmascaradas en el formato V-****5678."""
    texto = "Atendiendo paciente con cédula V-12345678 en consulta"
    enmascarado = enmascarar_datos_sensibles(texto)
    assert "V-****5678" in enmascarado
    assert "12345678" not in enmascarado


def test_log_enmascara_rif():
    """Comprueba que RIFs sean enmascarados en el formato J-****789."""
    texto = "Registrando consultorio con RIF J-123456789"
    enmascarado = enmascarar_datos_sensibles(texto)
    assert "J-****789" in enmascarado
    assert "123456789" not in enmascarado


def test_log_enmascara_telefono():
    """Comprueba que teléfonos venezolanos sean enmascarados en el formato +58****4567."""
    texto = "Enviando mensaje a teléfono +584121234567"
    enmascarado = enmascarar_datos_sensibles(texto)
    assert "+58****4567" in enmascarado
    assert "4121234567" not in enmascarado


def test_log_enmascara_email():
    """Comprueba que emails sean enmascarados en el formato d****@ejemplo.com."""
    texto = "Notificación enviada a doctor@ejemplo.com con éxito"
    enmascarado = enmascarar_datos_sensibles(texto)
    assert "d****@ejemplo.com" in enmascarado
    assert "doctor@ejemplo.com" not in enmascarado
