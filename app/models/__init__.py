"""Registro de modelos SQLModel. Importar aquí para que create_all() los detecte."""

# Módulo 2
from app.models.configuracion import Configuracion  # noqa: F401
from app.models.consultorio import Consultorio  # noqa: F401
from app.models.usuario import Usuario  # noqa: F401

# Módulo 3 — orden importa: Dueno antes de Paciente
from app.models.auditoria import Auditoria  # noqa: F401
from app.models.cita import Cita  # noqa: F401
from app.models.consulta import Consulta  # noqa: F401
from app.models.dueno import Dueno  # noqa: F401
from app.models.paciente import Paciente  # noqa: F401
from app.models.pago import Pago  # noqa: F401
from app.models.vacuna import Vacuna  # noqa: F401

# Sistema de licencias local
from app.models.licencia import LicenciaLocal  # noqa: F401

