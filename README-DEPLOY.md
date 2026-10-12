# Guía de Despliegue en Koyeb + Neon — Alta

Esta guía detalla el despliegue de Alta en la nube 24/7 sin coste alguno ($0/mes) usando PostgreSQL en **Neon** y hosting en **Koyeb**.

---

## 1. Crear Base de Datos en Neon (Gratis, sin tarjeta)

1. Ingresa a [neon.tech](https://neon.tech) y crea una cuenta o inicia sesión con GitHub/Google.
2. Crea un nuevo proyecto con el nombre: `alta`.
3. Selecciona la región más cercana (ejemplo: `US East (Ohio)` o `US East (N. Virginia)`).
4. Guarda las credenciales mostradas en pantalla y copia la cadena de conexión completa (**Connection String** / `DATABASE_URL`). Tendrá un formato similar a:
   ```text
   postgresql://neondb_owner:npg_xxxxxx@ep-cool-pond-xxxxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

---

## 2. Generar Claves Criptográficas de Producción

En tu terminal local ejecuta:

```bash
python scripts/preparar_deploy.py
```

Esto generará el archivo `.env.production.example` con los valores listos para copiar:
- `APP_ENV=production`
- `SECRET_KEY=<clave_aleatoria_generada>`
- `ENCRYPTION_KEY=<clave_fernet_generada>`

> **IMPORTANTE**: Si ya tienes datos clínicos cifrados en local con `data/clave.key` y vas a migrarlos, debes usar el contenido de `data/clave.key` como tu `ENCRYPTION_KEY` para que puedan descifrarse correctamente en la nube.

---

## 3. Desplegar en Koyeb (Gratis, sin tarjeta)

1. Ingresa a [koyeb.com](https://www.koyeb.com) y crea tu cuenta (puedes ingresar con GitHub).
2. Haz clic en **Create Service** (o **New App**).
3. Selecciona origen: **GitHub**.
4. Conecta y selecciona tu repositorio de Alta.
5. Configura los parámetros de compilación:
   - **Builder**: `Dockerfile`
   - **Dockerfile location**: `Dockerfile` (en la raíz del proyecto)
   - **Port**: `8000`
   - **Protocol**: `HTTP`
6. En la sección **Environment variables**, añade:
   - `APP_ENV` = `production`
   - `SECRET_KEY` = *(el valor generado en el paso 2)*
   - `ENCRYPTION_KEY` = *(la clave Fernet del paso 2 o de data/clave.key)*
   - `DATABASE_URL` = *(tu cadena de conexión de Neon obtenida en el paso 1)*
7. Haz clic en **Deploy**.
8. Koyeb construirá el contenedor, instalará dependencias e iniciará Gunicorn con 2 workers.

---

## 4. Obtener URL Pública Permanente

Una vez completado el despliegue (en ~2 minutos), Koyeb asignará una URL permanente protegida con HTTPS automático:
```text
https://alta-<tu-organizacion>.koyeb.app
```

---

## 5. Migrar Datos Existentes de Local a la Nube (Opcional)

Si vienes usando Alta en SQLite local (`data/alta.db`) y quieres transferir pacientes, consultas, pagos y citas a Neon:

```bash
python scripts/migrar_sqlite_a_postgres.py --source data/alta.db --target "postgresql://neondb_owner:PASSWORD@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require"
```

El script migra todas las tablas relacionales preservando los IDs primarios y los datos clínicos cifrados sin alteración.

---

## 6. Configurar Dominio Propio (Opcional)

Si dispones de un dominio propio (por ejemplo en Cloudflare):
1. En Koyeb ve a la sección **Custom Domains** de tu servicio.
2. Agrega tu subdominio (ej: `app.miclinica.com`).
3. En Cloudflare DNS agrega un registro `CNAME`:
   - Nombre: `app`
   - Destino: la dirección de CNAME proporcionada por Koyeb.

---

## 7. Verificación del Despliegue

Verifica que el servicio esté operativo:

1. **Health Check**:
   Abre en el navegador `https://alta-<tu-organizacion>.koyeb.app/health`.
   Debe responder:
   ```json
   {
     "status": "ok",
     "version": "1.0.0",
     "db": "ok",
     "clave_cifrado": "ok"
   }
   ```
2. **Entrada y Login**:
   Navega a `/entrada` para visualizar la pantalla inicial de selección AltaMed / AltaPet.
3. **Agenda Pública**:
   Verifica que los enlaces de agenda pública `/agenda/{slug}` funcionen sin autenticación previa.
4. **Persistencia**:
   Crea un registro de prueba y verifica su disponibilidad recargando la aplicación.
