"""Tests para el servicio y modelos de Licencias y Founder."""

from datetime import datetime, timedelta, timezone
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.config as config
from app.models.licencia import LicenciaLocal
from app.services.hardware import obtener_hardware_id
from app.services.licencia import (
    activar_licencia,
    calcular_prorrateo,
    dias_restantes_licencia,
    dias_restantes_mes,
    dias_restantes_trial,
    dias_totales_mes,
    estado_actual,
    info_licencia,
    iniciar_si_no_existe,
    obtener_banner_licencia,
    primer_dia_mes_siguiente,
    puede_escribir,
    renovar_mes,
    ultimo_dia_mes,
    validar_formato_clave,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_dias_fechas():
    f = datetime(2026, 10, 15, tzinfo=timezone.utc)
    assert dias_totales_mes(f) == 31
    assert dias_restantes_mes(f) == 17  # 31 - 15 + 1
    fin = ultimo_dia_mes(f)
    assert fin.day == 31
    assert fin.month == 10
    assert fin.year == 2026
    siguiente = primer_dia_mes_siguiente(f)
    assert siguiente.day == 1
    assert siguiente.month == 11
    assert siguiente.year == 2026


def test_calculo_prorrateo():
    # 15 de octubre en mes de 31 dias: 17 días restantes
    # 50 * (17 / 31) = 27.419... -> 27.42
    f15 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    assert calcular_prorrateo(50.0, f15) == 27.42

    # 1 de octubre: 31 días restantes de 31 -> 50.0
    f1 = datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert calcular_prorrateo(50.0, f1) == 50.0


def test_validar_formato_clave():
    assert validar_formato_clave("ALTA-ZKMA-PQ6T-F79R-SMXN") is True
    assert validar_formato_clave("alta-zkma-pq6t-f79r-smxn") is True
    assert validar_formato_clave("INVALID-KEY") is False
    assert validar_formato_clave("ALTA-1111-2222-3333-4444") is False  # 1 no permitido en patron


def test_iniciar_si_no_existe_y_trial(db_session):
    iniciar_si_no_existe(db_session)
    lic = db_session.get(LicenciaLocal, 1)
    assert lic is not None
    assert lic.estado == "trial"
    assert puede_escribir(db_session) is True
    assert estado_actual(db_session) == "trial"


def test_activar_licencia_ok(db_session):
    iniciar_si_no_existe(db_session)
    res = activar_licencia(db_session, "ALTA-ABCD-EFGH-JKLM-NPQR")
    assert res["ok"] is True
    assert res["estado"] == "activa"
    assert estado_actual(db_session) == "activa"
    assert puede_escribir(db_session) is True


def test_activar_licencia_formato_invalido(db_session):
    iniciar_si_no_existe(db_session)
    res = activar_licencia(db_session, "CLAVE_MAL")
    assert res["ok"] is False
    assert "Formato" in res["mensaje"]


def test_renovar_licencia(db_session):
    iniciar_si_no_existe(db_session)
    activar_licencia(db_session, "ALTA-ABCD-EFGH-JKLM-NPQR")
    res = renovar_mes(db_session)
    assert res["ok"] is True
    assert res["estado"] == "activa"


def test_founder_permanente(db_session):
    config.FOUNDER_EMAILS.append("test_founder@alta.med")
    iniciar_si_no_existe(db_session, email="test_founder@alta.med")
    lic = db_session.get(LicenciaLocal, 1)
    assert lic.es_founder is True
    assert estado_actual(db_session) == "founder"
    assert puede_escribir(db_session) is True
    # Founder activando o renovando no altera su estado permanente
    res = activar_licencia(db_session, "ALTA-ABCD-EFGH-JKLM-NPQR")
    assert res["estado"] == "founder"
    res_renovar = renovar_mes(db_session)
    assert res_renovar["estado"] == "founder"
    # Limpieza
    config.FOUNDER_EMAILS.remove("test_founder@alta.med")


def test_estado_expirada_bloquea_escritura(db_session):
    iniciar_si_no_existe(db_session)
    lic = db_session.get(LicenciaLocal, 1)
    # Forzar trial vencido
    lic.fecha_expiracion_trial = datetime.now(timezone.utc) - timedelta(days=5)
    lic.clave = None
    lic.estado = "expirada"
    db_session.add(lic)
    db_session.commit()

    assert estado_actual(db_session) == "expirada"
    assert puede_escribir(db_session) is False
    banner = obtener_banner_licencia(db_session)
    assert banner is not None
    assert banner["tipo"] == "error"


def test_anticopia_hardware_id_bloqueada(db_session, monkeypatch):
    iniciar_si_no_existe(db_session)
    lic = db_session.get(LicenciaLocal, 1)
    lic.hardware_id = "HW_ORIGINAL_123"
    db_session.add(lic)
    db_session.commit()

    monkeypatch.setattr("app.services.licencia.obtener_hardware_id", lambda: "HW_DISTINTO_456")
    assert estado_actual(db_session) == "bloqueada"
    assert puede_escribir(db_session) is False
