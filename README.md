# Repositorio Tesis UAI (SAF Platform)

Aplicacion web (Django) para registrar tesis por **grupo de sustentacion**, auditar registros y generar paquetes **SAF (ZIP)** para importacion en DSpace. La publicacion se gestiona **desde el grupo** (no hay modulo separado de "lotes").

## Modulos
- `accounts`: login, roles y gestion de usuarios.
- `registry`: grupos de sustentacion, registros de tesis, archivos y flujo de auditoria.
- `appconfig`: catalogos (carreras, asesores, jurados), licencias y parametros.
- `saf`: generacion de SAF + scripts de importacion/exportacion de enlaces.

## Roles (resumen)
- `cargador` / `asesor`:
  - Crea grupos (1 por dia) y registros dentro del grupo.
  - Sube/elimina archivos mientras el registro este editable.
  - Marca cada registro como **LISTO**.
  - Envia el **grupo** a auditoria (solo si todos estan LISTO).
- `auditor`:
  - Revisa **por registro** (observar/aprobar).
  - Genera SAF del grupo aprobado, descarga ZIP y luego aplica `dspace_links.json` para marcar como PUBLICADO.
  - Puede ver metadatos en modo lectura (no puede guardar cambios).

## Flujo funcional (end-to-end)
1. `cargador/asesor` crea un **grupo de sustentacion** (1 por dia).
2. Dentro del grupo crea los registros (tesis) y completa metadatos.
3. Sube archivos por registro (tesis, formulario(s), turnitin segun parametros).
4. Marca cada registro como **LISTO**.
5. Cuando **todos** estan LISTO, envia el **grupo** a **EN AUDITORIA**.
6. `auditor` revisa **cada registro**:
   - Observa (pasa a OBSERVADO) o aprueba (pasa a APROBADO).
7. Cuando todos los registros del grupo estan **APROBADO**, el `auditor` genera el **SAF** desde el grupo:
   - Se genera un ZIP en `generated_saf/`.
   - Los registros pasan a **POR PUBLICAR**.
8. En el servidor DSpace se importa el ZIP y se genera `dspace_links.json`.
9. En la web, el `auditor` sube `dspace_links.json` en el grupo para marcar registros como **PUBLICADO** y habilitar "Ver publicacion".

## Estados
Estados del **registro**:
- `BORRADOR`: editable por cargador/asesor.
- `LISTO`: marcado por cargador/asesor, listo para enviar a auditoria.
- `EN_AUDITORIA`: en revision del auditor.
- `OBSERVADO`: requiere correccion (editable por cargador/asesor).
- `APROBADO`: listo para generar SAF.
- `POR_PUBLICAR`: SAF generado (pendiente de cargar enlaces finales).
- `PUBLICADO`: ya tiene enlace/handle de DSpace.

Estados del **grupo** (se calculan desde los registros):
- `ARMADO`, `EN_AUDITORIA`, `OBSERVADO`, `APROBADO`, `POR_PUBLICAR`, `PUBLICADO`.

## Publicacion en DSpace (scripts del ZIP)
Al generar SAF, el ZIP incluye:
- `importar_todo.bat`: importa todas las carreras del grupo (una por una).
- `<CARRERA>\\importar.bat`: importa solo una carrera (opcional).
- `export_links.bat <baseUrl>`: genera `dspace_links.json` a partir de los `mapfiles`.
- `export_links_uai.bat`: igual que `export_links.bat` pero con base URL UAI por defecto.

DSpace:
1. Copia el contenido del ZIP a una carpeta de trabajo (ej. `C:\\mydspace\\SAF_YYYYMMDD_GX\\`).
2. Ejecuta `importar_todo.bat` (usa `C:\\dspace\\bin` por defecto si asi esta configurado en los scripts).
3. Se generan `mapfiles\\map_<CARRERA>.map`.
4. Ejecuta `export_links.bat https://repositorio.autonomadeica.edu.pe` (o `export_links_uai.bat`).
5. Se genera `dspace_links.json`. Sube ese JSON en la pagina del grupo (Publicacion) para marcar como **PUBLICADO**.

## Requisitos
- Windows (flujo DSpace + scripts .bat).
- Python 3.12+
- LibreOffice (opcional: solo si conviertes DOCX -> PDF al generar SAF).
- MySQL (opcional pero recomendado en produccion). Si no configuras MySQL, se usa SQLite.

## Instalacion local (rapida)
```powershell
cd d:\SPIDER-DEV\UAI\mydspace

py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python manage.py migrate
python manage.py seed_career_config --career-map career_map.csv
python manage.py runserver
```

## Base de datos
Por defecto (dev): SQLite (`db.sqlite3`).

Para MySQL (ejemplo, ajustar a tu entorno) en `saf_platform/settings.py` o variables de entorno:
- `DB_ENGINE=mysql`
- `DB_NAME=...`
- `DB_USER=...`
- `DB_PASSWORD=...`
- `DB_HOST=...`
- `DB_PORT=3306`

Puedes administrar MySQL con **MySQL Workbench** (sirve para ver tablas y datos).

## Variables utiles (settings/env)
- `SAF_OUTPUT_ROOT`: carpeta de salida SAF (default: `generated_saf/`).
- `DSPACE_BASE_URL`: base URL para construir enlaces si el JSON trae solo `handle`.
- `SOFFICE_PATH`: ruta a `soffice.exe` si no esta en PATH.

## Notas
- El modulo `build_saf.py` se mantiene como script legado (flujo Excel anterior) y referencia.
