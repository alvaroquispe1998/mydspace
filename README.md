# Plataforma Web SAF (Django + MySQL)

Aplicacion web para registrar tesis, auditar registros y generar lotes SAF para importacion en DSpace.

## Modulos implementados
- `accounts`: login, roles (`cargador`, `auditor`) y gestion de usuarios.
- `registry`: registro de tesis, archivos y flujo de auditoria.
- `appconfig`: configuracion de carreras (`career_map`), licencias versionadas y parametros.
- `saf`: lotes y generacion de paquetes SAF con ZIP de salida.

## Flujo funcional
1. Cargador crea registro y sube archivos (tesis, formulario(s), turnitin).
2. Cargador envia a auditoria.
3. Auditor observa o aprueba.
4. Auditor crea lote SAF desde aprobados y genera salida.
5. Descarga ZIP del lote para importacion en servidor DSpace.

## Requisitos
- Python 3.12+ (probado en 3.14)
- LibreOffice (para DOCX -> PDF durante generacion SAF)
- MySQL (recomendado para produccion)

## Instalacion local rapida
```powershell
cd D:\SPIDER-DEV\UAI\mydspace
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install django==5.1.6 pymysql==1.1.1 pandas openpyxl
```

## Configuracion de base de datos
Si defines `MYSQL_DATABASE`, Django usara MySQL.
Si no defines variables, usara SQLite (solo desarrollo rapido).

Variables recomendadas:
```powershell
$env:MYSQL_DATABASE="mydspace"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="tu_password"
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
$env:SOFFICE_PATH="C:\\Program Files\\LibreOffice\\program\\soffice.exe"
```

## Migraciones y seed inicial
```powershell
.\.venv\Scripts\python.exe manage.py makemigrations
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
.\.venv\Scripts\python.exe manage.py runserver
```

Ingresar en:
- `http://127.0.0.1:8000/auth/login/`

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

## Script legado
El archivo `build_saf.py` se mantiene para flujo Excel legado y referencia.
