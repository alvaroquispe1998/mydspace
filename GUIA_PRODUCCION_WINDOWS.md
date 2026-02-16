# Guia de produccion en Windows Server (DSpace + SAF Web)

## 1) Objetivo de esta guia
Esta guia es para publicar **tu sistema actual** en produccion, sin cambiar tu flujo funcional:
- DSpace en el mismo Windows Server.
- Tu sistema Django en el mismo Windows Server.
- MySQL en otro servidor.
- Publicacion a DSpace sigue manual con los `.bat` generados por SAF.

## 2) Arquitectura recomendada (estado actual)
- `Windows Server`: DSpace + app Django (SAF Web).
- `Servidor MySQL remoto`: base de datos de SAF Web.
- SAF Web genera ZIP SAF y scripts `.bat` en `generated_saf/`.
- Auditor ejecuta importacion manual en DSpace con `importar_todo.bat` y luego `export_links.bat`.

## 3) Prerrequisitos
- Windows Server con acceso a DSpace local.
- Python 3.12+ instalado.
- Acceso al MySQL remoto (host, puerto, usuario, password, db).
- PowerShell con permisos administrativos para crear servicio.
- (Recomendado) Certificado HTTPS si publicaras por dominio.

## 4) Preparar carpeta de produccion
Ejemplo de ruta (ajusta si usas otra):

```powershell
New-Item -ItemType Directory -Force C:\apps\mydspace
New-Item -ItemType Directory -Force C:\apps\mydspace\logs
New-Item -ItemType Directory -Force C:\apps\mydspace\storage
New-Item -ItemType Directory -Force C:\apps\mydspace\generated_saf
```

Copia el proyecto a `C:\apps\mydspace` (incluyendo `manage.py`, apps Django, `requirements.txt`).

## 5) Instalar entorno Python en produccion
En `C:\apps\mydspace`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install waitress
```

`waitress` se usa para servir Django en Windows de forma estable (no usar `runserver` en produccion).

## 6) Configurar variables de entorno (importante)
Tu `settings.py` usa estas variables para produccion:
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`
- `DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`
- `SAF_OUTPUT_ROOT`
- `DSPACE_BASE_URL`
- `SOFFICE_PATH` (opcional)

Ejemplo rapido en la sesion actual (para pruebas):

```powershell
$env:DJANGO_SECRET_KEY = "cambia-esta-clave"
$env:DJANGO_DEBUG = "0"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,tu-dominio-o-ip"

$env:MYSQL_DATABASE = "saf_db"
$env:MYSQL_USER = "saf_user"
$env:MYSQL_PASSWORD = "cambia-este-password"
$env:MYSQL_HOST = "10.10.10.20"
$env:MYSQL_PORT = "3306"

$env:DJANGO_STATIC_ROOT = "C:\apps\mydspace\staticfiles"
$env:DJANGO_MEDIA_ROOT = "C:\apps\mydspace\storage"
$env:SAF_OUTPUT_ROOT = "C:\apps\mydspace\generated_saf"
$env:DSPACE_BASE_URL = "https://repositorio.autonomadeica.edu.pe"
```

## 7) Inicializar base y recursos Django
En `C:\apps\mydspace`:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Si es una instalacion nueva y necesitas catalogos iniciales:

```powershell
python manage.py seed_career_config --career-map career_map.csv
```

## 8) Probar app en modo produccion (manual)
En `C:\apps\mydspace`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m waitress --listen=0.0.0.0:9000 saf_platform.wsgi:application
```

Prueba en navegador: `http://IP_DEL_SERVIDOR:9000`.

## 9) Dejar la app como servicio de Windows
Forma practica: usar `nssm` (Non-Sucking Service Manager).

1. Instala `nssm`.
2. Crea script `C:\apps\mydspace\start_web.cmd`:

```bat
@echo off
set DJANGO_SECRET_KEY=cambia-esta-clave
set DJANGO_DEBUG=0
set DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,tu-dominio-o-ip
set MYSQL_DATABASE=saf_db
set MYSQL_USER=saf_user
set MYSQL_PASSWORD=cambia-este-password
set MYSQL_HOST=10.10.10.20
set MYSQL_PORT=3306
set DJANGO_STATIC_ROOT=C:\apps\mydspace\staticfiles
set DJANGO_MEDIA_ROOT=C:\apps\mydspace\storage
set SAF_OUTPUT_ROOT=C:\apps\mydspace\generated_saf
set DSPACE_BASE_URL=https://repositorio.autonomadeica.edu.pe

cd /d C:\apps\mydspace
C:\apps\mydspace\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:9000 saf_platform.wsgi:application
```

3. Registra servicio:

```powershell
nssm install SAF-Web C:\apps\mydspace\start_web.cmd
nssm set SAF-Web AppDirectory C:\apps\mydspace
nssm set SAF-Web AppStdout C:\apps\mydspace\logs\web.out.log
nssm set SAF-Web AppStderr C:\apps\mydspace\logs\web.err.log
nssm start SAF-Web
```

## 10) Publicar por HTTPS (recomendado)
Opciones:
- IIS + URL Rewrite/ARR como reverse proxy a `127.0.0.1:9000`.
- O proxy existente en tu servidor (si ya usas otro).

Minimo recomendado:
- Exponer solo HTTPS (443).
- Dejar `waitress` en localhost (`127.0.0.1:9000`), no publico.
- Configurar `DJANGO_ALLOWED_HOSTS` con dominio/IP real.

## 11) Conexion segura a MySQL remoto
En el servidor MySQL:
- Permitir `3306` solo desde la IP del Windows Server.
- Crear usuario exclusivo para la app (no root).
- Dar permisos al schema de la app.

Ejemplo SQL base:

```sql
CREATE USER 'saf_user'@'IP_WINDOWS_SERVER' IDENTIFIED BY 'password-seguro';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX ON saf_db.* TO 'saf_user'@'IP_WINDOWS_SERVER';
FLUSH PRIVILEGES;
```

## 12) Flujo DSpace actual (sin automatizar aun)
Este flujo **se mantiene igual**:
1. En la web, auditor genera SAF del grupo.
2. Se descarga ZIP generado.
3. En servidor DSpace, extraer ZIP y ejecutar `importar_todo.bat`.
4. Ejecutar `export_links.bat <baseUrlRepositorio>`.
5. Subir `dspace_links.json` en la pantalla de Publicacion del grupo.

No cambies `assetstore` ni BD de DSpace manualmente.

## 13) Checklist de salida a produccion
- `DJANGO_DEBUG=0`.
- `DJANGO_ALLOWED_HOSTS` sin `*`.
- Servicio `SAF-Web` inicia al reiniciar servidor.
- `collectstatic` ejecutado.
- Carpeta `storage/` y `generated_saf/` con permisos correctos.
- Conexion estable a MySQL remoto.
- Prueba completa: login, creacion de grupo, carga de archivos, generar SAF, publicar con JSON.
- Backup definido:
  - Base MySQL remota.
  - Carpeta `storage/`.
  - Carpeta `generated_saf/` (si aplica por politica interna).

## 14) Operacion diaria minima
- Ver logs:
  - `C:\apps\mydspace\logs\web.out.log`
  - `C:\apps\mydspace\logs\web.err.log`
- Reiniciar servicio si hiciste cambios:

```powershell
nssm restart SAF-Web
```

- Para actualizar codigo:
1. Detener servicio.
2. Reemplazar codigo.
3. Instalar dependencias nuevas (si hubo cambios).
4. `migrate` y `collectstatic`.
5. Iniciar servicio.

