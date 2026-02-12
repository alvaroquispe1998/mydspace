
import os
import re
import csv
import shutil
import subprocess
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import pandas as pd


# =========================
# CONFIG
# =========================
BASE_DIR = Path(r".")  # carpeta donde ejecutarÃ¡s el script (mydspace)
INPUT_XLSX = BASE_DIR / "Plantilla_Tesis.xlsx"
CAREER_MAP_CSV = BASE_DIR / "career_map.csv"
LICENSE_FILE = BASE_DIR / "license.txt"

EVIDENCE_ROOT = BASE_DIR / "28.09.2025"          # tus carpetas 001..., 002...
OUT_SAF_ROOT = BASE_DIR / "out_saf"              # salida SAF
REPORT_PATH = BASE_DIR / "reporte_validacion.csv"

# LibreOffice: si estÃ¡ en PATH, dÃ©jalo None
SOFFICE_PATH = None  # ejemplo: r"C:\Program Files\LibreOffice\program\soffice.exe"
SOFFICE_FALLBACK_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]

# Si quieres subir Turnitin al repositorio (muchas U no lo publican)
INCLUDE_TURNITIN = True

# Palabras a evitar al elegir "tesis principal"
AVOID_NAME_HINTS = ["FORMULARIO", "TURNITIN", "ANEXO", "CONSTANCIA", "SOLICITUD"]

# BATs para importacion en servidor (se generan dentro de out_saf para copiar todo junto)
BAT_OUTPUT_DIR = OUT_SAF_ROOT / "_bats_import_dspace"
SERVER_BASE_DIR = r"C:\mydspace"
SERVER_DSPACE_BIN = r"C:\dspace\bin"
IMPORT_EPERSON = "repositorio@autonomadeica.edu.pe"
IMPORT_TARGETS = [
    ("ADMINISTRACION_Y_FINANZAS", "20.500.14441/85"),
    ("CONTABILIDAD", "20.500.14441/1037"),
    ("DERECHO", "20.500.14441/964"),
    ("INGENIERIA_CIVIL", "20.500.14441/1339"),
    ("INGENIERIA_DE_SISTEMAS", "20.500.14441/40"),
    ("INGENIERIA_EN_INDUSTRIAS_ALIMENTARIAS", "20.500.14441/105"),
    ("INGENIERIA_INDUSTRIAL", "20.500.14441/1112"),
    ("ENFERMERIA", "20.500.14441/4"),
    ("OBSTETRICIA", "20.500.14441/1003"),
    ("PSICOLOGIA", "20.500.14441/109"),
]

DEFAULT_METADATA_LANGUAGE = "es"
LANGUAGE_EXCLUDED_QUALIFIERS = {"dni", "uri", "date"}
URI_VALUE_PREFIXES = ("http://", "https://", "hdl:")
FORCED_LANGUAGE_FIELDS = {
    ("dc", "rights", "uri"),
    ("renati", "advisor", "orcid"),
    ("renati", "type", ""),
    ("renati", "level", ""),
    ("dc", "subject", "ocde"),
}
MetadataEntry = Tuple[str, str, str, str, str]


# =========================
# UTILS
# =========================
def norm_text(s: str) -> str:
    s = (s or "").strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s


def extract_nro_from_folder(folder_name: str) -> Optional[int]:
    """
    extrae el nro desde el prefijo: '001 ...' o '001_...' o '1 ...'
    """
    m = re.match(r"^\s*(\d{1,4})\b", folder_name)
    if not m:
        return None
    return int(m.group(1))


def pad_nro(n: int) -> str:
    return f"{n:03d}"


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def remove_empty_dir(p: Path):
    if not p.exists() or not p.is_dir():
        return
    try:
        next(p.iterdir())
        return
    except StopIteration:
        p.rmdir()


def resolve_soffice_binary() -> Optional[str]:
    candidates = []

    if SOFFICE_PATH:
        candidates.append(SOFFICE_PATH)

    for exe_name in ("soffice", "soffice.exe"):
        found = shutil.which(exe_name)
        if found:
            candidates.append(found)

    candidates.extend(SOFFICE_FALLBACK_PATHS)

    seen = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        if Path(c).exists():
            return c
    return None


def list_files_recursive(root: Path) -> List[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def find_candidate_thesis_files(folder: Path) -> List[Path]:
    """
    Busca posibles tesis (en raÃ­z de carpeta, NO dentro de FORMULARIO/TURNITIN).
    Acepta PDF y DOCX.
    """
    candidates = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in [".pdf", ".docx"]:
            continue
        name_norm = norm_text(p.name)
        if any(h in name_norm for h in AVOID_NAME_HINTS):
            continue
        candidates.append(p)
    return candidates


def pick_main_thesis_file(candidates: List[Path]) -> Optional[Path]:
    """
    Regla:
    1) si hay PDFs, escoge el PDF mÃ¡s grande
    2) si no, DOCX mÃ¡s grande
    """
    if not candidates:
        return None
    pdfs = [p for p in candidates if p.suffix.lower() == ".pdf"]
    if pdfs:
        return max(pdfs, key=lambda p: p.stat().st_size)
    return max(candidates, key=lambda p: p.stat().st_size)


def convert_docx_to_pdf(docx_path: Path, out_pdf_path: Path) -> Tuple[bool, str]:
    """
    Convierte con LibreOffice headless.
    """
    soffice = resolve_soffice_binary()
    if not soffice:
        return False, (
            "No se encontro 'soffice'. Instala LibreOffice o configura SOFFICE_PATH "
            "(ejemplo: C:\\Program Files\\LibreOffice\\program\\soffice.exe)."
        )

    out_dir = out_pdf_path.parent
    ensure_dir(out_dir)

    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(docx_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode != 0:
            return False, f"LibreOffice error: {res.stderr.strip() or res.stdout.strip()}"
        # LibreOffice genera nombre basado en docx
        generated = out_dir / (docx_path.stem + ".pdf")
        if not generated.exists():
            return False, "No se encontrÃ³ el PDF generado por LibreOffice."
        # renombrar a out_pdf_path (tesis.pdf)
        if generated != out_pdf_path:
            if out_pdf_path.exists():
                out_pdf_path.unlink()
            generated.rename(out_pdf_path)
        return True, "OK"
    except FileNotFoundError:
        return False, f"No se pudo ejecutar soffice en: {soffice}"
    except subprocess.TimeoutExpired:
        return False, "Timeout convirtiendo DOCX a PDF."
    except Exception as e:
        return False, f"ExcepciÃ³n convertiendo DOCX: {e}"


def infer_metadata_language(schema: str, element: str, qualifier: str, value: str) -> str:
    schema_norm = (schema or "").strip().lower()
    qualifier_norm = (qualifier or "").strip().lower()
    element_norm = (element or "").strip().lower()
    value_norm = (value or "").strip().lower()
    if not value_norm:
        return ""
    if (schema_norm, element_norm, qualifier_norm) in FORCED_LANGUAGE_FIELDS:
        return DEFAULT_METADATA_LANGUAGE
    if element_norm == "date":
        return ""
    if qualifier_norm in LANGUAGE_EXCLUDED_QUALIFIERS:
        return ""
    if value_norm.startswith(URI_VALUE_PREFIXES):
        return ""
    return DEFAULT_METADATA_LANGUAGE


def make_metadata_entry(
    schema: str,
    element: str,
    qualifier: str,
    value: str,
    language: Optional[str] = None,
) -> MetadataEntry:
    val = ("" if value is None else str(value)).strip()
    lang = infer_metadata_language(schema, element, qualifier, val) if language is None else (language or "").strip()
    return (schema, element, qualifier, lang, val)


def normalize_integer_like(value: str) -> str:
    text = ("" if value is None else str(value)).strip()
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def split_subjects(keywords: str) -> List[str]:
    text = (keywords or "").strip()
    if not text:
        return []

    if ";" in text or "|" in text or "\n" in text:
        raw_parts = re.split(r"[;\|\n]+", text)
    elif "," in text:
        raw_parts = text.split(",")
    else:
        raw_parts = [text]

    subjects: List[str] = []
    seen = set()
    for raw in raw_parts:
        term = raw.strip(" \t\r\n,;.")
        if not term:
            continue
        key = norm_text(term)
        if key in seen:
            continue
        seen.add(key)
        subjects.append(term)
    return subjects


def write_dublin_core_xml(out_path: Path, metadata: List[MetadataEntry]):
    """
    Escribe SOLO los campos dc en dublin_core.xml.
    metadata: lista de (schema, element, qualifier, language, value)
    """
    dc_items = [(s, e, q, l, v) for s, e, q, l, v in metadata if s == "dc"]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<dublin_core>']
    for _, element, qualifier, language, value in dc_items:
        value = (value or "").strip()
        if not value:
            continue
        q_attr = f' qualifier="{qualifier}"' if qualifier else ""
        l_attr = f' language="{language}"' if language else ""
        lines.append(f'  <dcvalue element="{element}"{q_attr}{l_attr}>{escape_xml(value)}</dcvalue>')
    lines.append("</dublin_core>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_metadata_schema_xml(out_dir: Path, schema: str, metadata: List[MetadataEntry]):
    """
    Escribe metadata_<schema>.xml para esquemas distintos a dc (renati, thesis, etc.).
    DSpace SAF requiere archivos separados por cada schema no-dc.
    """
    items = [(s, e, q, l, v) for s, e, q, l, v in metadata if s == schema]
    if not items:
        return
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<dublin_core schema="{schema}">']
    for _, element, qualifier, language, value in items:
        value = (value or "").strip()
        if not value:
            continue
        q_attr = f' qualifier="{qualifier}"' if qualifier else ""
        l_attr = f' language="{language}"' if language else ""
        lines.append(f'  <dcvalue element="{element}"{q_attr}{l_attr}>{escape_xml(value)}</dcvalue>')
    lines.append("</dublin_core>")
    out_path = out_dir / f"metadata_{schema}.xml"
    out_path.write_text("\n".join(lines), encoding="utf-8")


def escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )


def write_contents_file(out_path: Path, files: List[str]):
    out_path.write_text("\n".join(files) + "\n", encoding="utf-8")


def render_general_bat() -> str:
    lines = [
        "@echo off",
        "setlocal EnableExtensions EnableDelayedExpansion",
        "",
        f'set "DSPACE_BIN={SERVER_DSPACE_BIN}"',
        f'set "BASE_DIR={SERVER_BASE_DIR}"',
        f'set "EPERSON={IMPORT_EPERSON}"',
        "",
        'set "CAREER=%~1"',
        'set "HANDLE=%~2"',
        'set "LOTEDATE=%~3"',
        "",
        'if "%CAREER%"=="" (',
        '  echo ERROR: Falta CAREER. Uso: import_general.bat CARRERA HANDLE [YYYYMMDD]',
        "  exit /b 1",
        ")",
        'if "%HANDLE%"=="" (',
        '  echo ERROR: Falta HANDLE. Uso: import_general.bat CARRERA HANDLE [YYYYMMDD]',
        "  exit /b 1",
        ")",
        "",
        'set "SOURCE_DIR=%BASE_DIR%\\out_saf\\%CAREER%"',
        'set "MAP_DIR=%BASE_DIR%\\mapfiles"',
        'set "LOG_DIR=%BASE_DIR%\\logs"',
        "",
        'if not exist "%SOURCE_DIR%" (',
        '  echo ERROR: No existe carpeta SAF de carrera: "%SOURCE_DIR%"',
        "  exit /b 1",
        ")",
        "",
        'if not exist "%MAP_DIR%" mkdir "%MAP_DIR%"',
        "if errorlevel 1 (",
        '  echo ERROR: No se pudo crear/verificar mapfiles: "%MAP_DIR%"',
        "  exit /b 1",
        ")",
        "",
        'if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"',
        "if errorlevel 1 (",
        '  echo ERROR: No se pudo crear/verificar logs: "%LOG_DIR%"',
        "  exit /b 1",
        ")",
        "",
        'set "LDT="',
        "for /f \"tokens=2 delims==\" %%I in ('wmic os get LocalDateTime /value 2^>nul ^| find \"=\"') do set \"LDT=%%I\"",
        "if not defined LDT (",
        "  for /f %%I in ('powershell -NoProfile -Command \"Get-Date -Format yyyyMMddHHmmss\" 2^>nul') do set \"LDT=%%I\"",
        ")",
        'if "%LOTEDATE%"=="" (',
        "  if not defined LDT (",
        "    echo ERROR: No se pudo obtener fecha ^(YYYYMMDD^). Pasa parametro [YYYYMMDD].",
        "    exit /b 1",
        "  )",
        '  set "LOTEDATE=!LDT:~0,8!"',
        ")",
        "",
        "if not defined LDT (",
        '  set "LDT=%LOTEDATE%000000"',
        ")",
        'set "STAMP=!LDT:~0,8!_!LDT:~8,4!"',
        'set "MAP_FILE=%MAP_DIR%\\map_%CAREER%_%LOTEDATE%.map"',
        'set "LOG_FILE=%LOG_DIR%\\import_%CAREER%_%STAMP%.log"',
        "",
        'if exist "%MAP_FILE%" (',
        '  set "MODE=--resume"',
        ") else (",
        '  set "MODE=--add"',
        ")",
        "",
        'echo ============================================================>> "%LOG_FILE%"',
        'echo [%date% %time%] Inicio importacion carrera=%CAREER% modo=%MODE%>> "%LOG_FILE%"',
        'echo Source: "%SOURCE_DIR%">> "%LOG_FILE%"',
        'echo Handle: "%HANDLE%">> "%LOG_FILE%"',
        'echo Mapfile: "%MAP_FILE%">> "%LOG_FILE%"',
        "",
        'cd /d "%DSPACE_BIN%"',
        "if errorlevel 1 (",
        '  echo ERROR: No se pudo entrar a "%DSPACE_BIN%">> "%LOG_FILE%"',
        "  exit /b 1",
        ")",
        "",
        'call dspace import %MODE% --eperson "%EPERSON%" --collection "%HANDLE%" --source "%SOURCE_DIR%" --mapfile "%MAP_FILE%" >> "%LOG_FILE%" 2>&1',
        "if errorlevel 1 (",
        '  echo ERROR: Fallo importacion de %CAREER%. Revisa "%LOG_FILE%"',
        "  exit /b 1",
        ")",
        "",
        'echo OK: Importacion completada de %CAREER%. Log: "%LOG_FILE%"',
        "exit /b 0",
        "",
    ]
    return "\n".join(lines)


def render_all_careers_bat(targets: List[Tuple[str, str]]) -> str:
    lines = [
        "@echo off",
        "setlocal EnableExtensions EnableDelayedExpansion",
        "",
        f'set "BASE_DIR={SERVER_BASE_DIR}"',
        'set "LOG_DIR=%BASE_DIR%\\logs"',
        'set "SCRIPTS_DIR=%~dp0"',
        "",
        'if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"',
        "if errorlevel 1 (",
        '  echo ERROR: No se pudo crear/verificar logs: "%LOG_DIR%"',
        "  exit /b 1",
        ")",
        "",
        'set "LOTEDATE=%~1"',
        'set "LDT="',
        "for /f \"tokens=2 delims==\" %%I in ('wmic os get LocalDateTime /value 2^>nul ^| find \"=\"') do set \"LDT=%%I\"",
        "if not defined LDT (",
        "  for /f %%I in ('powershell -NoProfile -Command \"Get-Date -Format yyyyMMddHHmmss\" 2^>nul') do set \"LDT=%%I\"",
        ")",
        'if "%LOTEDATE%"=="" (',
        "  if not defined LDT (",
        "    echo ERROR: No se pudo obtener fecha ^(YYYYMMDD^). Pasa parametro [YYYYMMDD].",
        "    exit /b 1",
        "  )",
        '  set "LOTEDATE=!LDT:~0,8!"',
        ")",
        "",
        "if not defined LDT (",
        '  set "LDT=%LOTEDATE%000000"',
        ")",
        'set "STAMP=!LDT:~0,8!_!LDT:~8,4!"',
        'set "MASTER_LOG=%LOG_DIR%\\import_todas_%STAMP%.log"',
        "set /a OK_COUNT=0",
        "",
        'echo ============================================================>> "%MASTER_LOG%"',
        'echo [%date% %time%] Inicio importacion masiva lote=%LOTEDATE%>> "%MASTER_LOG%"',
        "",
    ]
    for career_folder, handle in targets:
        lines.extend([
            f'echo Ejecutando carrera {career_folder}...>> "%MASTER_LOG%"',
            f'call "%SCRIPTS_DIR%import_general.bat" "{career_folder}" "{handle}" "%LOTEDATE%"',
            "if errorlevel 1 (",
            f'  echo ERROR: Fallo carrera {career_folder}. Se detiene el proceso.>> "%MASTER_LOG%"',
            '  echo ERROR: Fallo importacion masiva. Revisa "%MASTER_LOG%"',
            "  exit /b 1",
            ")",
            "set /a OK_COUNT+=1",
            "",
        ])
    lines.extend([
        'echo [%date% %time%] FIN OK. Carreras importadas: %OK_COUNT%>> "%MASTER_LOG%"',
        'echo OK: Importacion masiva completada. Carreras importadas: %OK_COUNT%',
        'echo Log master: "%MASTER_LOG%"',
        "exit /b 0",
        "",
    ])
    return "\n".join(lines)


def render_import_guide_md(targets: List[Tuple[str, str]]) -> str:
    lines = [
        "# Guia rapida - Importacion DSpace con BATs",
        "",
        "Esta guia se genera automaticamente cada vez que ejecutas `build_saf.py`.",
        "",
        "## Archivos",
        "- `import_general.bat`: importa una sola carrera.",
        "- `import_todas.bat`: importa todas las carreras configuradas.",
        "",
        "## Requisitos en servidor",
        f"- Carpeta base: `{SERVER_BASE_DIR}`",
        "- SAF en: `C:\\mydspace\\out_saf\\<CARRERA>`",
        f"- DSpace bin en: `{SERVER_DSPACE_BIN}`",
        "",
        "## 1) Importar una sola carrera",
        "```bat",
        "cd /d C:\\mydspace\\out_saf\\_bats_import_dspace",
        "import_general.bat CARRERA HANDLE [YYYYMMDD]",
        "```",
        "",
        "Ejemplo:",
        "```bat",
        "import_general.bat INGENIERIA_DE_SISTEMAS 20.500.14441/40 20260209",
        "```",
        "",
        "## 2) Importar todas las carreras",
        "```bat",
        "cd /d C:\\mydspace\\out_saf\\_bats_import_dspace",
        "import_todas.bat [YYYYMMDD]",
        "```",
        "",
        "## Donde revisar resultados",
        "- Logs: `C:\\mydspace\\logs`",
        "- Mapfiles: `C:\\mydspace\\mapfiles`",
        "",
        "## Regla add/resume",
        "- Si no existe mapfile: usa `--add`.",
        "- Si el mapfile ya existe: usa `--resume`.",
        "",
        "## Carreras configuradas en import_todas.bat",
    ]
    for career_folder, handle in targets:
        lines.append(f"- `{career_folder}` -> `{handle}`")
    lines.extend([
        "",
        "## Errores comunes",
        "- `No existe carpeta SAF de carrera`: falta `C:\\mydspace\\out_saf\\<CARRERA>`.",
        f"- `No se pudo entrar a {SERVER_DSPACE_BIN}`: revisar ruta de DSpace.",
        "- Si falla importacion: revisar el `.log` en `C:\\mydspace\\logs`.",
        "",
    ])
    return "\n".join(lines)


def render_career_bat(career: str, handle: str) -> str:
    """BAT autocontenido para una carrera: doble clic y listo."""
    lines = [
        "@echo off",
        "setlocal EnableExtensions EnableDelayedExpansion",
        "",
        f'set "DSPACE_BIN={SERVER_DSPACE_BIN}"',
        f'set "BASE_DIR={SERVER_BASE_DIR}"',
        f'set "EPERSON={IMPORT_EPERSON}"',
        f'set "CAREER={career}"',
        f'set "HANDLE={handle}"',
        "",
        'set "SOURCE_DIR=%BASE_DIR%\\out_saf\\%CAREER%"',
        'set "MAP_DIR=%BASE_DIR%\\mapfiles"',
        'set "LOG_DIR=%BASE_DIR%\\logs"',
        "",
        'if not exist "%MAP_DIR%" mkdir "%MAP_DIR%"',
        'if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"',
        "",
        'set "LDT="',
        "for /f \"tokens=2 delims==\" %%I in ('wmic os get LocalDateTime /value 2^>nul ^| find \"=\"') do set \"LDT=%%I\"",
        "if not defined LDT (",
        "  for /f %%I in ('powershell -NoProfile -Command \"Get-Date -Format yyyyMMddHHmmss\" 2^>nul') do set \"LDT=%%I\"",
        ")",
        "if not defined LDT (",
        "  echo ERROR: No se pudo obtener fecha.",
        "  pause",
        "  exit /b 1",
        ")",
        'set "LOTEDATE=!LDT:~0,8!"',
        'set "STAMP=!LDT:~0,8!_!LDT:~8,4!"',
        'set "MAP_FILE=%MAP_DIR%\\map_%CAREER%_%LOTEDATE%.map"',
        'set "LOG_FILE=%LOG_DIR%\\import_%CAREER%_%STAMP%.log"',
        "",
        'if exist "%MAP_FILE%" (',
        '  set "MODE=--resume"',
        ") else (",
        '  set "MODE=--add"',
        ")",
        "",
        "echo.",
        f"echo  === IMPORTACION: {career} ===",
        'echo  Modo:    %MODE%',
        f'echo  Handle:  {handle}',
        'echo  Log:     "%LOG_FILE%"',
        "echo.",
        "",
        'echo ============================================================>> "%LOG_FILE%"',
        'echo [%date% %time%] Inicio importacion carrera=%CAREER% modo=%MODE%>> "%LOG_FILE%"',
        "",
        'cd /d "%DSPACE_BIN%"',
        "if errorlevel 1 (",
        '  echo ERROR: No se pudo entrar a "%DSPACE_BIN%"',
        "  pause",
        "  exit /b 1",
        ")",
        "",
        "echo  Importando... (puede tardar unos minutos)",
        "echo.",
        'call dspace import %MODE% --eperson "%EPERSON%" --collection "%HANDLE%" --source "%SOURCE_DIR%" --mapfile "%MAP_FILE%" >> "%LOG_FILE%" 2>&1',
        "if errorlevel 1 (",
        "  echo.",
        f'  echo  [ERROR] Fallo importacion de {career}.',
        '  echo  Revisa: "%LOG_FILE%"',
        "  echo.",
        "  pause",
        "  exit /b 1",
        ")",
        "",
        "echo.",
        f"echo  [OK] Importacion completada: {career}",
        'echo  Log: "%LOG_FILE%"',
        "echo.",
        "pause",
        "exit /b 0",
        "",
    ]
    return "\r\n".join(lines)


def render_importar_todo_bat(targets: list) -> str:
    """BAT general en out_saf: importa todas las carreras con doble clic."""
    lines = [
        "@echo off",
        "setlocal EnableExtensions EnableDelayedExpansion",
        "",
        f'set "DSPACE_BIN={SERVER_DSPACE_BIN}"',
        f'set "BASE_DIR={SERVER_BASE_DIR}"',
        f'set "EPERSON={IMPORT_EPERSON}"',
        'set "MAP_DIR=%BASE_DIR%\\mapfiles"',
        'set "LOG_DIR=%BASE_DIR%\\logs"',
        "",
        'if not exist "%MAP_DIR%" mkdir "%MAP_DIR%"',
        'if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"',
        "",
        'set "LDT="',
        "for /f \"tokens=2 delims==\" %%I in ('wmic os get LocalDateTime /value 2^>nul ^| find \"=\"') do set \"LDT=%%I\"",
        "if not defined LDT (",
        "  for /f %%I in ('powershell -NoProfile -Command \"Get-Date -Format yyyyMMddHHmmss\" 2^>nul') do set \"LDT=%%I\"",
        ")",
        "if not defined LDT (",
        "  echo ERROR: No se pudo obtener fecha.",
        "  pause",
        "  exit /b 1",
        ")",
        'set "LOTEDATE=!LDT:~0,8!"',
        'set "STAMP=!LDT:~0,8!_!LDT:~8,4!"',
        'set "MASTER_LOG=%LOG_DIR%\\import_TODAS_%STAMP%.log"',
        "set /a TOTAL=0",
        "set /a OK_COUNT=0",
        "set /a FAIL_COUNT=0",
        "",
        "echo.",
        f"echo  === IMPORTACION MASIVA - {len(targets)} CARRERAS ===",
        "echo.",
        "",
        'echo ============================================================>> "%MASTER_LOG%"',
        'echo [%date% %time%] Inicio importacion masiva>> "%MASTER_LOG%"',
        "",
    ]
    for career, handle in targets:
        lines.extend([
            f'set "CAREER={career}"',
            f'set "HANDLE={handle}"',
            'set "SOURCE_DIR=%BASE_DIR%\\out_saf\\%CAREER%"',
            'set "MAP_FILE=%MAP_DIR%\\map_%CAREER%_%LOTEDATE%.map"',
            'set "LOG_FILE=%LOG_DIR%\\import_%CAREER%_%STAMP%.log"',
            "",
            'if not exist "%SOURCE_DIR%" (',
            f'  echo  [SKIP] {career}: no existe carpeta SAF',
            f'  echo  [SKIP] {career}: carpeta no encontrada>> "%MASTER_LOG%"',
            "  goto :next_" + career.lower(),
            ")",
            "",
            'if exist "%MAP_FILE%" (',
            '  set "MODE=--resume"',
            ") else (",
            '  set "MODE=--add"',
            ")",
            "set /a TOTAL+=1",
            "",
            f'echo  [%TOTAL%] Importando {career} (modo=%MODE%)...',
            f'echo  [%date% %time%] {career} modo=%MODE%>> "%MASTER_LOG%"',
            "",
            'cd /d "%DSPACE_BIN%"',
            'call dspace import %MODE% --eperson "%EPERSON%" --collection "%HANDLE%" --source "%SOURCE_DIR%" --mapfile "%MAP_FILE%" >> "%LOG_FILE%" 2>&1',
            "if errorlevel 1 (",
            f"  echo  [ERROR] {career}",
            f'  echo  [ERROR] {career}>> "%MASTER_LOG%"',
            "  set /a FAIL_COUNT+=1",
            ") else (",
            f"  echo  [OK]    {career}",
            f'  echo  [OK] {career}>> "%MASTER_LOG%"',
            "  set /a OK_COUNT+=1",
            ")",
            "",
            ":" + "next_" + career.lower(),
            "",
        ])
    lines.extend([
        "echo.",
        "echo  ============================================",
        "echo  RESUMEN: %OK_COUNT% OK / %FAIL_COUNT% ERROR / %TOTAL% TOTAL",
        "echo  ============================================",
        'echo  Log master: "%MASTER_LOG%"',
        "echo.",
        'echo [%date% %time%] FIN: %OK_COUNT% OK, %FAIL_COUNT% ERROR, %TOTAL% TOTAL>> "%MASTER_LOG%"',
        "pause",
        "exit /b 0",
        "",
    ])
    return "\r\n".join(lines)


def generate_import_bats(out_dir: Path):
    ensure_dir(out_dir)

    for old_bat in out_dir.glob("*.bat"):
        old_bat.unlink()

    general_path = out_dir / "import_general.bat"
    general_path.write_text(render_general_bat(), encoding="ascii")

    all_path = out_dir / "import_todas.bat"
    all_path.write_text(render_all_careers_bat(IMPORT_TARGETS), encoding="ascii")

    guide_path = out_dir / "GUIA_USO_IMPORTACION.md"
    guide_path.write_text(render_import_guide_md(IMPORT_TARGETS), encoding="utf-8")

    # --- BAT por carrera (doble clic) dentro de cada carpeta ---
    for career, handle in IMPORT_TARGETS:
        career_dir = OUT_SAF_ROOT / career
        if career_dir.exists() and career_dir.is_dir():
            bat_path = career_dir / "importar.bat"
            bat_path.write_bytes(render_career_bat(career, handle).encode("ascii"))

    # --- BAT general importar_todo.bat en out_saf ---
    # solo incluye carreras que tienen carpeta SAF generada
    existing = [(c, h) for c, h in IMPORT_TARGETS
                if (OUT_SAF_ROOT / c).exists() and (OUT_SAF_ROOT / c).is_dir()]
    if existing:
        todo_path = OUT_SAF_ROOT / "importar_todo.bat"
        todo_path.write_bytes(render_importar_todo_bat(existing).encode("ascii"))


# =========================
# LOAD INPUTS
# =========================
def load_career_map(path: Path) -> Dict[str, Dict[str, str]]:
    """
    key: carrera_norm
    """
    out = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cn = norm_text(row.get("carrera_norm", ""))
            if not cn:
                continue
            out[cn] = {k: (v or "").strip() for k, v in row.items()}
    return out


def load_xlsx_rows(path: Path) -> List[Dict[str, str]]:
    df = pd.read_excel(path, sheet_name="TESIS")
    # quitar filas vacÃ­as
    df = df[df["NRO"].notna()]
    rows = []
    current_year = str(datetime.now().year)
    for _, r in df.iterrows():
        row = {k: ("" if pd.isna(v) else v) for k, v in r.to_dict().items()}
        # normalizar nro
        row["NRO"] = int(float(row["NRO"]))
        # normalizar carrera para matching
        row["CARRERA_NORM"] = norm_text(str(row.get("CARRERA", "")))
        # fecha emitida: solo anio actual (nuevo formato de plantilla sin fecha)
        row["FECHA_ISSUED"] = current_year
        rows.append(row)
    return rows


# =========================
# MAIN
# =========================
def main():
    if not INPUT_XLSX.exists():
        raise FileNotFoundError(f"No existe: {INPUT_XLSX}")
    if not CAREER_MAP_CSV.exists():
        raise FileNotFoundError(f"No existe: {CAREER_MAP_CSV}")
    if not EVIDENCE_ROOT.exists():
        raise FileNotFoundError(f"No existe: {EVIDENCE_ROOT}")

    resolved_soffice = resolve_soffice_binary()
    if resolved_soffice:
        print(f"SOFFICE detectado: {resolved_soffice}")
    else:
        print("ADVERTENCIA: no se detecto soffice. Los DOCX no podran convertirse.")
    if LICENSE_FILE.exists():
        print(f"LICENCIA detectada: {LICENSE_FILE}")
    else:
        print(f"ADVERTENCIA: no se encontro licencia en {LICENSE_FILE}.")

    career_map = load_career_map(CAREER_MAP_CSV)
    rows = load_xlsx_rows(INPUT_XLSX)

    # index folders by nro
    folders_by_nro: Dict[int, Path] = {}
    for p in EVIDENCE_ROOT.iterdir():
        if not p.is_dir():
            continue
        n = extract_nro_from_folder(p.name)
        if n is None:
            continue
        folders_by_nro[n] = p

    ensure_dir(OUT_SAF_ROOT)

    report = []
    for row in rows:
        nro = row["NRO"]
        nro_pad = pad_nro(nro)
        carrera_norm = row["CARRERA_NORM"]

        # career mapping
        cmap = career_map.get(carrera_norm)
        if not cmap:
            report.append([nro_pad, "ERROR", f"CARRERA sin mapeo en career_map.csv: {row.get('CARRERA','')}"])
            continue

        handle = cmap.get("handle", "").strip()
        if not handle:
            report.append([nro_pad, "ERROR", "Handle vacÃ­o en career_map.csv"])
            continue

        folder = folders_by_nro.get(nro)
        if not folder:
            report.append([nro_pad, "ERROR", f"No existe carpeta para NRO={nro_pad} en {EVIDENCE_ROOT}"])
            continue

        # detect thesis
        candidates = find_candidate_thesis_files(folder)
        thesis_src = pick_main_thesis_file(candidates)
        if not thesis_src:
            report.append([nro_pad, "ERROR", f"No se encontrÃ³ tesis (.pdf/.docx) en raÃ­z de {folder.name}"])
            continue

        # Prepare output SAF dir (by carrera_norm and item_###).
        # DSpace itemimport expects item directories named like item_000, item_001, etc.
        carrera_dir = OUT_SAF_ROOT / carrera_norm.replace(" ", "_")
        item_dir = carrera_dir / f"item_{nro_pad}"

        # Copy/convert thesis to tesis.pdf
        thesis_out_pdf = item_dir / "tesis.pdf"
        if thesis_src.suffix.lower() == ".pdf":
            ensure_dir(item_dir)
            shutil.copy2(thesis_src, thesis_out_pdf)
            thesis_status = "OK (PDF copiado)"
        else:
            ok, msg = convert_docx_to_pdf(thesis_src, thesis_out_pdf)
            if not ok:
                # si falla DOCX->PDF, no dejar carpetas SAF vacias
                remove_empty_dir(item_dir)
                remove_empty_dir(carrera_dir)
                report.append([nro_pad, "ERROR", f"Fallo conversion DOCX->PDF: {msg}"])
                continue
            thesis_status = "OK (DOCX convertido a PDF)"

        # Collect attachments
        attached_files = []

        # Formularios
        form_dir = folder / "FORMULARIO"
        if form_dir.exists() and form_dir.is_dir():
            form_pdfs = sorted([p for p in form_dir.glob("*.pdf") if p.is_file()], key=lambda p: p.name.lower())
            for i, fp in enumerate(form_pdfs, start=1):
                out_name = f"formulario_{i}.pdf"
                shutil.copy2(fp, item_dir / out_name)
                attached_files.append(out_name)

        # Turnitin
        if INCLUDE_TURNITIN:
            tdir = folder / "TURNITIN"
            if tdir.exists() and tdir.is_dir():
                t_pdfs = sorted([p for p in tdir.glob("*.pdf") if p.is_file()], key=lambda p: p.name.lower())
                for i, tp in enumerate(t_pdfs, start=1):
                    out_name = f"turnitin_{i}.pdf" if len(t_pdfs) > 1 else "turnitin.pdf"
                    shutil.copy2(tp, item_dir / out_name)
                    attached_files.append(out_name)

        # Licencia del item (bundle LICENSE)
        has_license = False
        if LICENSE_FILE.exists():
            shutil.copy2(LICENSE_FILE, item_dir / LICENSE_FILE.name)
            has_license = True

        # Build dublin_core.xml metadata
        md: List[MetadataEntry] = []

        def add_md(schema: str, element: str, qualifier: str, value: str, language: Optional[str] = None):
            md.append(make_metadata_entry(schema, element, qualifier, value, language))

        # Core dc
        add_md("dc", "title", "", str(row.get("TITULO", "")).strip())
        add_md("dc", "date", "issued", row.get("FECHA_ISSUED", ""))
        add_md("dc", "language", "iso", "spa")
        add_md("dc", "format", "", "application/pdf")
        add_md("dc", "type", "", "info:eu-repo/semantics/bachelorThesis")
        add_md("dc", "rights", "", "info:eu-repo/semantics/openAccess")

        # Authors (hasta 3)
        for idx in [1,2,3]:
            a = str(row.get(f"AUTOR{idx}_APELLIDOS_NOMBRES", "")).strip()
            if a:
                add_md("dc", "contributor", "author", a)
            dni = normalize_integer_like(row.get(f"AUTOR{idx}_DNI", ""))
            if dni:
                add_md("renati", "author", "dni", dni)

        # Advisor
        adv = str(row.get("ASESOR_APELLIDOS_NOMBRES","")).strip()
        if adv:
            add_md("dc", "contributor", "advisor", adv)
        adv_dni = normalize_integer_like(row.get("ASESOR_DNI",""))
        if adv_dni:
            add_md("renati", "advisor", "dni", adv_dni)
        orcid = str(row.get("ASESOR_ORCID","")).strip()
        if orcid:
            add_md("renati", "advisor", "orcid", orcid)

        # Jurados como renati.juror (cada uno por separado)
        for jkey in ["JURADO1_APELLIDOS_NOMBRES", "JURADO2_APELLIDOS_NOMBRES", "JURADO3_APELLIDOS_NOMBRES"]:
            jval = str(row.get(jkey, "")).strip()
            if jval:
                add_md("renati", "juror", "", jval)

        # Resumen/keywords
        resumen = str(row.get("RESUMEN","")).strip()
        if resumen:
            add_md("dc", "description", "abstract", resumen)
        keywords = ""
        for key_name in ["KEYWORDS (separar con ';')", "KEYWORDS", "PALABRAS_CLAVE", "SUBJECT", "SUBJECTS"]:
            candidate = str(row.get(key_name, "")).strip()
            if candidate:
                keywords = candidate
                break
        if keywords:
            for subject in split_subjects(keywords):
                add_md("dc", "subject", "", subject)

        # Campos fijos RENATI/DC
        add_md("renati", "type", "", "https://purl.org/pe-repo/renati/type#tesis")
        add_md("dc", "type", "version", "info:eu-repo/semantics/publishedVersion")
        add_md("dc", "publisher", "", "Universidad Autónoma de Ica")
        add_md("dc", "publisher", "country", "PE")
        add_md("dc", "rights", "uri", "https://creativecommons.org/licenses/by/4.0")

        # Degree + RENATI + OCDE (from career_map if present)
        if cmap.get("thesis_degree_name"):
            add_md("thesis", "degree", "name", cmap["thesis_degree_name"])
        if cmap.get("thesis_degree_discipline"):
            add_md("thesis", "degree", "discipline", cmap["thesis_degree_discipline"])
        if cmap.get("thesis_degree_grantor"):
            add_md("thesis", "degree", "grantor", cmap["thesis_degree_grantor"])
        if cmap.get("renati_level"):
            add_md("renati", "level", "", cmap["renati_level"])
        if cmap.get("renati_discipline"):
            add_md("renati", "discipline", "", cmap["renati_discipline"])
        if cmap.get("ocde_url"):
            add_md("dc", "subject", "ocde", cmap["ocde_url"])

        # Write SAF files (split by schema)
        write_dublin_core_xml(item_dir / "dublin_core.xml", md)
        # Schemas no-dc van en archivos separados: metadata_renati.xml, metadata_thesis.xml
        extra_schemas = sorted(set(s for s, _, _, _, _ in md if s != "dc"))
        for schema in extra_schemas:
            write_metadata_schema_xml(item_dir, schema, md)

        # contents: licencia + tesis primaria + adjuntos
        contents_list = []
        if has_license:
            contents_list.append(f"{LICENSE_FILE.name}\tbundle:LICENSE")
        contents_list.append("tesis.pdf\tbundle:ORIGINAL\tprimary:true")
        for attached_name in attached_files:
            contents_list.append(f"{attached_name}\tbundle:ORIGINAL")
        write_contents_file(item_dir / "contents", contents_list)

        report.append([
            nro_pad,
            "OK",
            f"{folder.name} | {thesis_status} | adjuntos={len(attached_files)} | licencia={'SI' if has_license else 'NO'} | carrera={carrera_norm}",
        ])

    # write report (si Excel lo tiene abierto, guardar en nombre alterno)
    report_out = REPORT_PATH
    try:
        with report_out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["NRO", "STATUS", "DETAIL"])
            w.writerows(report)
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_out = BASE_DIR / f"reporte_validacion_{ts}.csv"
        with report_out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["NRO", "STATUS", "DETAIL"])
            w.writerows(report)
        print(f"ADVERTENCIA: {REPORT_PATH} estaba bloqueado. Se guardo en: {report_out}")

    generate_import_bats(BAT_OUTPUT_DIR)

    print(f"OK. SAF generado en: {OUT_SAF_ROOT}")
    print(f"Reporte: {report_out}")
    print(f"BATs de importacion: {BAT_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
