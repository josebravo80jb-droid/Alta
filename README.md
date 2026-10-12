# Alta — Gestión de consultorios

Software administrativo **offline-first** para profesionales de salud con consultorio propio.

## Dos marcas

| Marca | Para quién |
|-------|-----------|
| **AltaMed** | Médicos, odontólogos, psicólogos y otros profesionales de salud humana |
| **AltaPet** | Veterinarios y clínicas de animales |

Ambas comparten el mismo motor. Solo cambia el nombre y algunos textos de la interfaz.

---

## Características

- 📅 **Agenda** con vista semanal e indicadores de estado
- 🗂️ **Fichas de pacientes** con historial clínico completo
- 📝 **Registro de consultas** con notas cifradas (solo el médico puede verlas)
- 💰 **Control de ingresos** + recibos PDF descargables
- 👥 **Roles**: médico (acceso total) y asistente (sin notas clínicas)
- 🔒 **Cifrado Fernet** de notas, indicaciones y diagnósticos
- 🔗 **Auditoría inmutable** con cadena de hash SHA-256
- 🎭 **Modo Demo** con datos de ejemplo realistas (faker es_ES)
- 📴 Funciona **100% offline** — no requiere internet

---

## Instalación

### Requisitos

- Python 3.11 o superior
- Windows, macOS o Linux
- 200 MB de espacio libre (incluye dependencias)

### Pasos

```bash
# 1. Descargar o clonar el proyecto
git clone <url-del-repo>
cd alta

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Arrancar
python run.py
```

Abrir el navegador en **http://localhost:8000**.

En el primer inicio se crea automáticamente:
- `data/alta.db` — base de datos
- `data/clave.key` — clave de cifrado Fernet

---

## Uso diario

### Iniciar Alta

| Sistema | Método |
|---------|--------|
| Windows | Doble clic en `start.bat` |
| Mac / Linux | `./start.sh` en terminal |
| Cualquiera | `python run.py` |

### Detener Alta

`Ctrl + C` en la terminal donde corre Alta.

### Registrar un consultorio

Al abrir Alta por primera vez se muestra el formulario de registro. Llena:
- Nombre del consultorio o del profesional
- Email y contraseña (para el login)
- Dirección y teléfono
- Horario y duración de cita por defecto

### Registrar una consulta

1. Ir a **Pacientes**
2. Clic en la ficha del paciente
3. Clic en **+ Nueva consulta**
4. Llenar: motivo, nota clínica, indicaciones y diagnóstico
5. Guardar — la nota se cifra automáticamente

### Cobrar

1. Ir a **Ingresos**
2. Clic en **+ Registrar pago**
3. Seleccionar paciente, monto, método y estado
4. **Descargar recibo** en PDF desde la lista de pagos

### Modo Demo

En el **Dashboard** (solo rol Médico) hay una sección "Modo Demo":

- **▶ Cargar datos de ejemplo**: genera 20 pacientes, 50 citas, 30 consultas y 15 pagos ficticios con `demo=True`
- **✕ Borrar datos demo**: elimina **únicamente** los registros `demo=True`. Los datos reales nunca se tocan.

---

## ⚠️ ADVERTENCIAS CRÍTICAS

### Backup obligatorio

Toda la información de Alta vive en la carpeta `data/`:

```
data/
├── alta.db      ← base de datos (todos los registros)
└── clave.key    ← clave de cifrado
```

> **Si pierdes `data/clave.key`, pierdes TODAS las notas clínicas.**
> No hay forma de recuperarlas. No existe una copia maestra.

**Recomendación:** Copia de seguridad **semanal** de la carpeta `data/` completa en:
- Un pendrive dedicado
- Un disco externo
- La nube (Google Drive, Dropbox, etc.)

Los dos archivos deben ir **juntos**. Sin la clave, la base de datos no sirve.

### Restaurar desde backup

1. Detener Alta (`Ctrl + C`)
2. Reemplazar `data/alta.db` y `data/clave.key` con los archivos del backup
3. Reiniciar con `python run.py`

### Migrar a otro equipo

1. Copiar la carpeta `data/` completa
2. Instalar Alta en el nuevo equipo (`pip install -r requirements.txt`)
3. Pegar `data/` en el directorio del proyecto
4. Ejecutar `python run.py`

---

## Roles y permisos

| Función | Médico | Asistente |
|---------|:------:|:---------:|
| Ver agenda | ✅ | ✅ |
| Crear / editar cita | ✅ | ✅ |
| Ver pacientes | ✅ | ✅ |
| Ver notas clínicas | ✅ | ❌ |
| Crear consulta | ✅ | ❌ |
| Registrar pago | ✅ | ✅ |
| Ver ingresos | ✅ | ✅ |
| Modo Demo | ✅ | ❌ |
| Ver auditoría | ✅ | ❌ |

El asistente ve el error **403 Forbidden** si intenta acceder a funciones reservadas al médico.

---

## Arquitectura

### Stack

| Componente | Tecnología |
|------------|------------|
| Servidor web | FastAPI |
| Base de datos | SQLModel + SQLite |
| Interfaz | Jinja2 + PicoCSS |
| Hashing contraseñas | pwdlib[argon2] |
| Tokens de sesión | pyjwt |
| Recibos PDF | fpdf2 + DejaVu |
| Cifrado clínico | cryptography (Fernet) |
| Auditoría | hashlib SHA-256 |
| Datos demo | Faker (es_ES) |

### Estructura del proyecto

```
alta/
├── run.py                  ← Script de arranque (python run.py)
├── start.bat               ← Arranque Windows (doble clic)
├── start.sh                ← Arranque Mac/Linux
├── requirements.txt
│
├── app/
│   ├── main.py             ← Punto de entrada FastAPI
│   ├── config.py           ← Variables de entorno
│   ├── database.py         ← Engine SQLite + sesión
│   ├── dependencies.py     ← get_current_user (JWT)
│   │
│   ├── models/             ← Modelos SQLModel (tablas)
│   │   ├── consultorio.py
│   │   ├── usuario.py
│   │   ├── paciente.py
│   │   ├── cita.py
│   │   ├── consulta.py
│   │   ├── pago.py
│   │   ├── auditoria.py
│   │   └── configuracion.py
│   │
│   ├── schemas/            ← Schemas Pydantic (validación)
│   │   ├── auth.py
│   │   ├── cita.py
│   │   ├── consulta.py
│   │   ├── paciente.py
│   │   ├── pago.py
│   │   └── dashboard.py
│   │
│   ├── routes/             ← Endpoints FastAPI
│   │   ├── auth.py         ← /api/auth/register, /login
│   │   ├── agenda.py       ← /api/citas, /api/agenda/semana
│   │   ├── pacientes.py    ← /api/pacientes
│   │   ├── consultas.py    ← /api/consultas
│   │   ├── pagos.py        ← /api/pagos, /api/ingresos
│   │   ├── auditoria.py    ← /api/auditoria
│   │   ├── dashboard.py    ← /api/dashboard
│   │   ├── demo.py         ← /api/demo/cargar, /borrar
│   │   ├── health.py       ← /health (sin auth)
│   │   └── vistas.py       ← Rutas HTML (Jinja2)
│   │
│   ├── services/           ← Lógica de negocio
│   │   ├── auth.py         ← JWT, hashing
│   │   ├── agenda.py       ← Validación de disponibilidad
│   │   ├── pacientes.py    ← CRUD pacientes
│   │   ├── consultas.py    ← Consultas clínicas
│   │   ├── pagos.py        ← Pagos e ingresos
│   │   ├── pdf.py          ← Generación de recibos
│   │   ├── cifrado.py      ← Fernet (cifrar/descifrar)
│   │   ├── auditoria.py    ← Hash-chain de auditoría
│   │   └── demo.py         ← Generación/borrado de datos demo
│   │
│   ├── templates/          ← HTML (Jinja2 + PicoCSS)
│   └── static/             ← CSS, fuentes DejaVu
│
├── tests/                  ← Suite de pruebas (pytest)
│   ├── test_auth.py
│   ├── test_agenda.py
│   ├── test_pacientes.py
│   ├── test_consultas.py
│   ├── test_pagos.py
│   ├── test_dashboard.py
│   ├── test_cifrado.py
│   ├── test_auditoria.py
│   ├── test_modelos.py
│   ├── test_demo.py
│   └── test_e2e.py         ← Flujo completo end-to-end
│
└── data/                   ← ⚠️ HACER BACKUP DE ESTA CARPETA
    ├── alta.db             ← Base de datos SQLite
    └── clave.key           ← Clave Fernet (CRÍTICA)
```

### Flujo de datos — nota clínica

```
Médico escribe nota
       ↓
cifrar(nota)  →  Fernet AES-128  →  token cifrado
       ↓
Guardado en Consulta.nota (texto cifrado)
       ↓
descifrar(nota)  →  texto original (solo rol MEDICO)
```

### Auditoría hash-chain

Cada acción relevante (crear consulta, pago, etc.) genera un registro en `Auditoria`:

```
hash_actual = SHA-256(hash_anterior + accion + entidad_id + timestamp)
```

Modificar un registro rompe la cadena. Verificable en `/api/auditoria/verificar`.

---

## Testing

### Correr todos los tests

```bash
pytest tests/ -v
```

### Correr un módulo específico

```bash
pytest tests/test_consultas.py -v
pytest tests/test_e2e.py -v
```

### Suite actual

| Archivo | Cobertura |
|---------|-----------|
| `test_auth.py` | Registro, login, JWT |
| `test_agenda.py` | CRUD citas, disponibilidad |
| `test_pacientes.py` | CRUD pacientes, fichas |
| `test_consultas.py` | Consultas, roles, filtros |
| `test_pagos.py` | Pagos, PDF, CSV |
| `test_dashboard.py` | Métricas del día |
| `test_cifrado.py` | Fernet, clave, rotación |
| `test_auditoria.py` | Hash-chain, integridad |
| `test_modelos.py` | Modelos SQLModel |
| `test_demo.py` | Modo Demo, integridad de reales |
| `test_e2e.py` | Flujo completo del médico |

> **Todos los tests deben pasar antes de cada release.**
> Si alguno falla, no entregar.

---

## Endpoint de salud

```
GET /health
```

No requiere autenticación. Verifica DB, clave de cifrado y versión.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "db": "ok",
  "clave_cifrado": "ok"
}
```

Útil para monitoreo, scripts de arranque y verificación rápida.

---

## Variables de entorno (`.env`)

Copia `.env.example` como `.env` y ajusta si es necesario:

```env
APP_NAME=Alta
APP_ENV=development
SECRET_KEY=cambiar_esto_en_produccion
DATABASE_URL=sqlite:///./data/alta.db
ENCRYPTION_KEY_FILE=data/clave.key
```

> En producción, usa un `SECRET_KEY` de al menos 32 caracteres aleatorios.

---

## Roadmap

| Fase | Estado | Descripción |
|------|--------|-------------|
| **MVP (actual)** | ✅ Completo | Agenda, fichas, consultas, pagos, cifrado, auditoría, demo |
| Fase 2 | 🔜 Pendiente | Firma digital de PDFs, QR en recibos, plantillas de consulta |
| Fase 3 | ⏸️ Suspendida | IA: dictado por voz, resúmenes automáticos |
| Fase 4 | ⏸️ Suspendida | Telesalud, FHIR, multi-país |

> **Regla del proyecto:** No avanzar a Fase 3 ni 4 hasta que 20 médicos usen el MVP activamente.

---

## Reglas del proyecto

- Cambio mínimo por archivo en cada PR
- Los tests deben pasar antes de cada cambio
- El asistente **NUNCA** ve notas clínicas — es una regla de negocio, no solo técnica
- Nada de refactor sin tests que lo justifiquen
- No añadir dependencias sin evaluar el impacto en el instalador offline

---

## Licencia

MIT

---

## Contacto

[Tu nombre / email]
