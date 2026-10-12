"""Pruebas unitarias para validación matemática de RIF y Cédula venezolana."""

import pytest
from app.services.validacion import (
    normalizar_cedula,
    normalizar_rif,
    validar_cedula_ve,
    validar_rif_ve,
)
from app.schemas.paciente import PacienteCreate


def test_validar_cedula_valida():
    """Comprueba que formatos válidos de cédula sean aceptados."""
    assert validar_cedula_ve("V-12345678") is True
    assert validar_cedula_ve("E-12345678") is True
    assert validar_cedula_ve("12345678") is True
    assert validar_cedula_ve("V12345678") is True
    assert validar_cedula_ve("123456") is True
    assert validar_cedula_ve("123456789") is True


def test_validar_cedula_invalida():
    """Comprueba que formatos y valores inválidos sean rechazados."""
    assert validar_cedula_ve("") is False
    assert validar_cedula_ve(None) is False
    assert validar_cedula_ve("00000000") is False
    assert validar_cedula_ve("000000") is False
    assert validar_cedula_ve("12345") is False  # Menos de 6 dígitos
    assert validar_cedula_ve("1234567890") is False  # Más de 9 dígitos
    assert validar_cedula_ve("ABC12345") is False
    assert validar_cedula_ve("X-12345678") is False


def test_validar_rif_valido():
    """Comprueba que RIFs con dígito verificador matemático correcto sean aceptados."""
    assert validar_rif_ve("J-10000000-7") is True
    assert validar_rif_ve("J100000007") is True
    assert validar_rif_ve("J000000000") is True


def test_validar_rif_invalido():
    """Comprueba que RIFs con dígito verificador incorrecto o formato inválido sean rechazados."""
    assert validar_rif_ve("J-12345678-9") is False
    assert validar_rif_ve("J123456789") is False
    assert validar_rif_ve("invalido") is False
    assert validar_rif_ve("") is False
    assert validar_rif_ve(None) is False


def test_normalizar_cedula():
    """Comprueba la normalización estándar de cédula a V- o E-."""
    assert normalizar_cedula("12345678") == "V-12345678"
    assert normalizar_cedula("v-12345678") == "V-12345678"
    assert normalizar_cedula("e-12345678") == "E-12345678"


def test_crear_paciente_con_cedula_invalida_falla():
    """Comprueba que el schema Pydantic de PacienteCreate rechace cédulas inválidas."""
    with pytest.raises(ValueError):
        PacienteCreate(nombre="Carlos Perez", cedula="00000000")

    with pytest.raises(ValueError):
        PacienteCreate(nombre="Carlos Perez", cedula="123")

    # Cédula válida debe crearse y normalizarse
    p = PacienteCreate(nombre="Carlos Perez", cedula="12345678")
    assert p.cedula == "V-12345678"
