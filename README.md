# Plataforma Web SAF (Django + MySQL)

Aplicacion web para registrar tesis, auditar registros y generar lotes SAF para importacion en DSpace.

## Modulos implementados
- `accounts`: login, roles (`cargador`, `auditor`) y gestion de usuarios.
- `registry`: registro de tesis, archivos y flujo de auditoria.
- `appconfig`: configuracion de carreras, asesores, jurados, licencias versionadas y parametros.
- `saf`: lotes y generacion de paquetes SAF con ZIP de salida.

## Flujo funcional
1. Cargador crea un **grupo de sustentación** (1 por día) y dentro crea los registros.
2. Cargador sube archivos por registro (tesis, formulario(s), turnitin).
3. Cargador **envía el grupo** a auditoría (valida que todos estén listos).
4. Auditor revisa **por registro**: observa o aprueba.
5. Cuando **todos los registros del grupo están APROBADO**, el auditor crea el **lote SAF del grupo** y genera el ZIP.
6. Al generar SAF, los registros pasan a **POR PUBLICAR**.
7. En el servidor DSpace se importa el ZIP y luego se genera `dspace_links.json` desde los `mapfiles`.
8. En la web, el auditor sube `dspace_links.json` en el lote para marcar como **PUBLICADO** y habilitar "Ver publicación".

## Requisitos
- Python 3.12+
- LibreOffice (opcional; solo si necesitas convertir DOCX -> PDF durante la generacion SAF)
- MySQL (opcional; recomendado para produccion). Si no configuras MySQL, el proyecto usa SQLite automaticamente.

## Instalacion local rapida
```powershell
# 1) Ir a la carpeta del proyecto
cd <ruta>\mydspace

# 2) Crear y activar entorno virtual
py -m venv .venv

# Si PowerShell bloquea la activacion, ejecuta esto solo para esta sesion:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# 3) Instalar dependencias
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Primera vez (setup completo)
Si estas en una PC nueva y quieres dejarlo listo (migraciones + seed + servidor), puedes copiar y pegar esto en PowerShell:
```powershell
cd d:\SPIDER-DEV\UAI\mydspace  # cambia la ruta si tu carpeta es otra

py -m venv .venv
# Si PowerShell bloquea la activacion, ejecuta esto solo para esta sesion:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python manage.py migrate
python manage.py seed_career_config --career-map career_map.csv
python manage.py runserver
```

## Configuracion de base de datos
Si defines `MYSQL_DATABASE`, Django usara MySQL.
Si no defines variables, usara SQLite (solo desarrollo rapido).

## Usar MySQL (recomendado)
1) Crea la base de datos y usuario en MySQL (ejemplo):
```sql
CREATE DATABASE mydspace CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'mydspace_user'@'%' IDENTIFIED BY 'tu_password';
GRANT ALL PRIVILEGES ON mydspace.* TO 'mydspace_user'@'%';
FLUSH PRIVILEGES;
```

2) Define variables de entorno (PowerShell):
```powershell
$env:MYSQL_DATABASE="mydspace"
$env:MYSQL_USER="mydspace_user"
$env:MYSQL_PASSWORD="tu_password"
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
```

3) Aplica migraciones:
```powershell
python manage.py migrate
python manage.py seed_career_config --career-map career_map.csv
```

Notas:
- Si `MYSQL_DATABASE` esta definido, **no se usa** `db.sqlite3`.
- Asegurate que el servicio de MySQL este iniciado y el puerto `3306` accesible desde donde corre Django.

Variables recomendadas:
```powershell
$env:DJANGO_SECRET_KEY="cambia-esto-en-produccion"
$env:DJANGO_DEBUG="1"  # 0 en produccion
$env:DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"

$env:MYSQL_DATABASE="mydspace"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="tu_password"
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
$env:SOFFICE_PATH="C:\\Program Files\\LibreOffice\\program\\soffice.exe"

# Opcional: guardar uploads y SAF fuera del repo (por ejemplo, en un disco/compartido)
$env:DJANGO_MEDIA_ROOT="D:\\mydspace_data\\storage"
$env:SAF_OUTPUT_ROOT="D:\\mydspace_data\\generated_saf"
```

## Migraciones y seed inicial
```powershell
# Si usas MySQL, asegurate de haber creado la BD primero (por ejemplo: mydspace).

# Nota: no necesitas "makemigrations" para correr el proyecto (solo si cambias modelos).
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_career_config --career-map career_map.csv
```

El comando `seed_career_config`:
- Carga/actualiza `career_map.csv` en tabla `CareerConfig`.
- Crea usuario auditor por defecto:
  - usuario: `auditor`
  - password: `Auditor123!`
- Crea licencia inicial (usa `license.txt` si existe).

## Ejecutar aplicacion
```powershell
# Si el entorno virtual esta activado:
python manage.py runserver

# Alternativa (sin activar): usa el Python del entorno virtual (.venv), no el del sistema.
# .\.venv\Scripts\python.exe manage.py runserver
```

Ingresar en:
- `http://127.0.0.1:8000/` (redirige al login)
- `http://127.0.0.1:8000/auth/login/`

## Despliegue (produccion) en Windows Server + MySQL
Recomendacion: publicar Django en un servidor (idealmente en la intranet/VPN) y usar MySQL para datos. **No uses `runserver` en produccion**.

### 1) Preparar servidor
Instala en el servidor:
- Python 3.12+
- Git
- MySQL (o acceso a un MySQL ya instalado)

### 2) Clonar e instalar
```powershell
cd D:\apps
git clone <tu_repo_git> mydspace
cd mydspace

py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3) Variables de entorno (produccion)
Define estas variables a nivel de sistema o en el servicio que ejecute la app:
```powershell
$env:DJANGO_DEBUG="0"
$env:DJANGO_SECRET_KEY="pon-un-valor-largo-y-secreto"
$env:DJANGO_ALLOWED_HOSTS="tu-dominio-o-ip"

$env:MYSQL_DATABASE="mydspace"
$env:MYSQL_USER="mydspace_user"
$env:MYSQL_PASSWORD="tu_password"
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"

# Rutas persistentes (recomendado fuera del repo)
$env:DJANGO_MEDIA_ROOT="D:\\mydspace_data\\storage"
$env:SAF_OUTPUT_ROOT="D:\\mydspace_data\\generated_saf"
$env:DJANGO_STATIC_ROOT="D:\\mydspace_data\\staticfiles"
```

### 4) Migraciones, seed y estaticos
```powershell
python manage.py migrate
python manage.py seed_career_config --career-map career_map.csv
python manage.py collectstatic --noinput
```

### 5) Ejecutar en produccion (ejemplo con Waitress)
En Windows es simple usar Waitress como servidor WSGI:
```powershell
python -m pip install waitress
python -m waitress --listen=0.0.0.0:8000 saf_platform.wsgi:application
```

Luego publica el puerto (firewall) o pon un reverse proxy (IIS/Nginx) con HTTPS.

## Publicar actualizaciones
Flujo recomendado en el servidor:
```powershell
cd D:\apps\mydspace
git pull
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Finalmente reinicia el proceso/servicio que ejecuta Waitress (si lo tienes como servicio/tarea programada).

## Solucion de problemas
### `no such table: accounts_user` (u otra tabla)
Esto pasa cuando ejecutas el servidor sin haber aplicado migraciones. En una PC nueva es normal porque:
- `db.sqlite3` es local y esta ignorada por Git (ver `.gitignore`), asi que no se "baja" con el repo.
- Si usabas MySQL en otra PC y aqui no definiste `MYSQL_DATABASE`, el proyecto cae a SQLite automaticamente.

Arreglo (en PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py seed_career_config --career-map career_map.csv
python manage.py runserver
```

### "Quiero usar la misma BD en otra PC"
Se puede, pero **no es recomendable commitear** `db.sqlite3` al repo (puede contener datos sensibles/PII y genera conflictos). Mejor opcion:
- Copiar el archivo `db.sqlite3` manualmente (zip/USB/etc.) a la raiz del proyecto en la otra PC (misma version de codigo).
- Luego correr `python manage.py migrate` por si faltan migraciones.

## Validaciones clave implementadas
- Para enviar a auditoria:
  - `career`, `titulo`, `autor1_nombre`, `autor1_dni`.
  - tesis (`DOCX` o `PDF`), >=1 formulario (`PDF`), >=1 turnitin (`PDF`).
  - DNI numerico de longitud configurable (default 8).
  - ORCID valido si se registra.
  - carrera activa y con `handle`.
- Para aprobar:
  - todo lo anterior + existencia fisica de archivos.
- Para generar SAF:
  - solo registros aprobados.
  - licencia activa disponible.
  - conversion DOCX->PDF con LibreOffice cuando aplique.

## Salida SAF
Por lote se genera en:
- `generated_saf/<BATCH_CODE>/`
- `generated_saf/<BATCH_CODE>.zip`

Por item:
- `license.txt` en bundle `LICENSE`
- `tesis.pdf` en `ORIGINAL` y `primary:true`
- formularios y turnitin en `ORIGINAL`
- `dublin_core.xml`, `metadata_renati.xml`, `metadata_thesis.xml`
- `contents` con orden fijo

## Nota sobre `source` en bitstreams
El campo `Source` no es controlable via `contents` de SAF estandar; DSpace lo define internamente durante importacion/carga.

## Donde se guardan los archivos (uploads)
Los archivos que subes (tesis, formularios, turnitin) se guardan en disco en `storage/` (ver `MEDIA_ROOT` en `saf_platform/settings.py`):
- Carpeta base: `storage/`
- Ruta tipica: `storage/records/<record_id>/<file_type>_<uuid>.<ext>`

En desarrollo (`DEBUG=1`), Django los expone por `MEDIA_URL=/media/`.

## Script legado
El archivo `build_saf.py` se mantiene para flujo Excel legado y referencia.
