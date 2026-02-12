import csv
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.utils import timezone

from appconfig.models import LicenseVersion
from registry.models import ThesisFile, ThesisRecord
from saf.models import SafBatch, SafBatchItem

SOFFICE_FALLBACK_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]
DEFAULT_METADATA_LANGUAGE = "es"
LANGUAGE_EXCLUDED_QUALIFIERS = {"dni", "uri", "date"}
FORCED_LANGUAGE_FIELDS = {
    ("dc", "rights", "uri"),
    ("renati", "advisor", "orcid"),
    ("renati", "type", ""),
    ("renati", "level", ""),
    ("dc", "subject", "ocde"),
}
URI_VALUE_PREFIXES = ("http://", "https://", "hdl:")
MetadataEntry = Tuple[str, str, str, str, str]


def norm_text(s: str) -> str:
    s = (s or "").strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s


def resolve_soffice_binary() -> Optional[str]:
    candidates = []
    if settings.SOFFICE_PATH:
        candidates.append(settings.SOFFICE_PATH)
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


def convert_docx_to_pdf(docx_path: Path, out_pdf_path: Path) -> Tuple[bool, str]:
    soffice = resolve_soffice_binary()
    if not soffice:
        return False, "No se encontró soffice para convertir DOCX."
    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_pdf_path.parent),
        str(docx_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            return False, proc.stderr.strip() or proc.stdout.strip() or "Error de LibreOffice"
        generated = out_pdf_path.parent / f"{docx_path.stem}.pdf"
        if not generated.exists():
            return False, "LibreOffice no generó PDF."
        if generated != out_pdf_path:
            if out_pdf_path.exists():
                out_pdf_path.unlink()
            generated.rename(out_pdf_path)
        return True, "OK"
    except subprocess.TimeoutExpired:
        return False, "Timeout en conversión DOCX->PDF"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


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


def split_subjects(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    if ";" in raw or "|" in raw or "\n" in raw:
        parts = re.split(r"[;\|\n]+", raw)
    elif "," in raw:
        parts = raw.split(",")
    else:
        parts = [raw]
    out: List[str] = []
    seen = set()
    for p in parts:
        term = p.strip(" \t\r\n,;.")
        if not term:
            continue
        key = norm_text(term)
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
    return out


def escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def write_dublin_core_xml(out_path: Path, metadata: List[MetadataEntry]):
    dc_items = [(s, e, q, l, v) for s, e, q, l, v in metadata if s == "dc"]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<dublin_core>"]
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
    (out_dir / f"metadata_{schema}.xml").write_text("\n".join(lines), encoding="utf-8")


def write_contents_file(out_path: Path, lines: List[str]):
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def zip_directory(src: Path, zip_path: Path):
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for file_path in src.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(src))


def _pick_thesis_file(record: ThesisRecord) -> Optional[ThesisFile]:
    pdf = record.files.filter(file_type=ThesisFile.TYPE_TESIS_PDF).order_by("-created_at").first()
    if pdf:
        return pdf
    return record.files.filter(file_type=ThesisFile.TYPE_TESIS_DOCX).order_by("-created_at").first()


def _career_folder_name(record: ThesisRecord) -> str:
    base = record.career.carrera_norm if record.career else "SIN_CARRERA"
    return re.sub(r"\s+", "_", norm_text(base))


def generate_saf_batch(batch: SafBatch) -> Tuple[bool, str]:
    license_obj = LicenseVersion.objects.filter(is_active=True).first()
    if not license_obj:
        return False, "No hay licencia activa en configuración."

    output_root = Path(settings.SAF_OUTPUT_ROOT) / batch.batch_code
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    report_rows: List[List[str]] = []
    log_lines = []
    has_errors = False
    current_year = str(datetime.now().year)

    batch.status = SafBatch.STATUS_RUNNING
    batch.log_text = "Iniciando generación SAF..."
    batch.save(update_fields=["status", "log_text", "updated_at"])

    items = batch.items.select_related("record__career").prefetch_related("record__files").all()
    for item in items:
        record = item.record
        item_folder = f"item_{record.nro:03d}"
        item.item_folder_name = item_folder
        try:
            if record.status not in [ThesisRecord.STATUS_APROBADO, ThesisRecord.STATUS_INCLUIDO_EN_LOTE]:
                raise ValueError("Registro no está aprobado para SAF.")

            thesis_src = _pick_thesis_file(record)
            if not thesis_src:
                raise ValueError("No existe tesis en PDF o DOCX.")

            career_dir = output_root / _career_folder_name(record)
            item_dir = career_dir / item_folder
            item_dir.mkdir(parents=True, exist_ok=True)

            thesis_out = item_dir / "tesis.pdf"
            thesis_src_path = Path(thesis_src.file.path)
            if not thesis_src_path.exists():
                raise ValueError(f"No existe archivo de tesis: {thesis_src.original_name}")
            if thesis_src.file_type == ThesisFile.TYPE_TESIS_PDF:
                shutil.copy2(thesis_src_path, thesis_out)
                thesis_status = "OK (PDF copiado)"
            else:
                ok, msg = convert_docx_to_pdf(thesis_src_path, thesis_out)
                if not ok:
                    raise ValueError(f"Fallo DOCX->PDF: {msg}")
                thesis_status = "OK (DOCX convertido)"

            # Adjuntos
            attached = []
            forms = list(record.files.filter(file_type=ThesisFile.TYPE_FORMULARIO).order_by("original_name", "id"))
            for idx, f in enumerate(forms, start=1):
                dst_name = f"formulario_{idx}.pdf"
                shutil.copy2(f.file.path, item_dir / dst_name)
                attached.append(dst_name)

            turns = list(record.files.filter(file_type=ThesisFile.TYPE_TURNITIN).order_by("original_name", "id"))
            for idx, f in enumerate(turns, start=1):
                dst_name = "turnitin.pdf" if len(turns) == 1 else f"turnitin_{idx}.pdf"
                shutil.copy2(f.file.path, item_dir / dst_name)
                attached.append(dst_name)

            # Licencia
            license_path = item_dir / "license.txt"
            license_path.write_text(license_obj.text_content or "", encoding="utf-8")

            md: List[MetadataEntry] = []
            add = lambda s, e, q, v, lang=None: md.append(make_metadata_entry(s, e, q, v, lang))
            add("dc", "title", "", record.titulo)
            add("dc", "date", "issued", current_year)
            add("dc", "language", "iso", "spa")
            add("dc", "format", "", "application/pdf")
            add("dc", "type", "", "info:eu-repo/semantics/bachelorThesis")
            add("dc", "rights", "", "info:eu-repo/semantics/openAccess")

            for i in [1, 2, 3]:
                author = getattr(record, f"autor{i}_nombre", "").strip()
                dni = normalize_integer_like(getattr(record, f"autor{i}_dni", ""))
                if author:
                    add("dc", "contributor", "author", author)
                if dni:
                    add("renati", "author", "dni", dni)

            if record.asesor_nombre.strip():
                add("dc", "contributor", "advisor", record.asesor_nombre.strip())
            if record.asesor_dni.strip():
                add("renati", "advisor", "dni", normalize_integer_like(record.asesor_dni.strip()))
            if record.asesor_orcid.strip():
                add("renati", "advisor", "orcid", record.asesor_orcid.strip())

            for field_name in ["jurado1", "jurado2", "jurado3"]:
                value = getattr(record, field_name, "").strip()
                if value:
                    add("renati", "juror", "", value)

            if record.resumen.strip():
                add("dc", "description", "abstract", record.resumen.strip())

            for sub in split_subjects(record.keywords_raw):
                add("dc", "subject", "", sub)

            add("renati", "type", "", "https://purl.org/pe-repo/renati/type#tesis")
            add("dc", "type", "version", "info:eu-repo/semantics/publishedVersion")
            add("dc", "publisher", "", "Universidad Autónoma de Ica")
            add("dc", "publisher", "country", "PE")
            add("dc", "rights", "uri", "https://creativecommons.org/licenses/by/4.0")

            if record.career:
                if record.career.thesis_degree_name:
                    add("thesis", "degree", "name", record.career.thesis_degree_name)
                if record.career.thesis_degree_discipline:
                    add("thesis", "degree", "discipline", record.career.thesis_degree_discipline)
                if record.career.thesis_degree_grantor:
                    add("thesis", "degree", "grantor", record.career.thesis_degree_grantor)
                if record.career.renati_level:
                    add("renati", "level", "", record.career.renati_level)
                if record.career.renati_discipline:
                    add("renati", "discipline", "", record.career.renati_discipline)
                if record.career.ocde_url:
                    add("dc", "subject", "ocde", record.career.ocde_url)

            write_dublin_core_xml(item_dir / "dublin_core.xml", md)
            for schema in sorted(set(s for s, _, _, _, _ in md if s != "dc")):
                write_metadata_schema_xml(item_dir, schema, md)

            contents = [
                "license.txt\tbundle:LICENSE",
                "tesis.pdf\tbundle:ORIGINAL\tprimary:true",
            ]
            for name in attached:
                contents.append(f"{name}\tbundle:ORIGINAL")
            write_contents_file(item_dir / "contents", contents)

            item.result = SafBatchItem.RESULT_OK
            item.detail = f"{thesis_status} | adjuntos={len(attached)}"
            item.save(update_fields=["item_folder_name", "result", "detail"])

            record.status = ThesisRecord.STATUS_INCLUIDO_EN_LOTE
            record.save(update_fields=["status", "updated_at"])
            report_rows.append([f"{record.nro:03d}", "OK", item.detail])
            log_lines.append(f"[OK] {record.nro:03d}")
        except Exception as exc:  # noqa: BLE001
            has_errors = True
            item.result = SafBatchItem.RESULT_ERROR
            item.detail = str(exc)
            item.save(update_fields=["item_folder_name", "result", "detail"])
            report_rows.append([f"{record.nro:03d}", "ERROR", str(exc)])
            log_lines.append(f"[ERROR] {record.nro:03d} - {exc}")

    report_path = output_root / "reporte_validacion.csv"
    with report_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["NRO", "STATUS", "DETAIL"])
        writer.writerows(report_rows)

    zip_path = output_root.parent / f"{batch.batch_code}.zip"
    if zip_path.exists():
        zip_path.unlink()
    zip_directory(output_root, zip_path)

    batch.generated_at = timezone.now()
    batch.output_path = str(output_root)
    batch.report_path = str(report_path)
    batch.zip_path = str(zip_path)
    batch.log_text = "\n".join(log_lines)
    batch.status = SafBatch.STATUS_FAILED if has_errors else SafBatch.STATUS_DONE
    batch.save(update_fields=["generated_at", "output_path", "report_path", "zip_path", "log_text", "status", "updated_at"])

    if has_errors:
        return False, "Lote generado con errores."
    return True, "Lote generado correctamente."
