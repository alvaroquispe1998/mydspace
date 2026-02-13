import hashlib
import mimetypes
import re
from pathlib import Path
from typing import List

from django.conf import settings

from appconfig.models import SystemConfig
from registry.models import ThesisFile, ThesisRecord

ORCID_RE = re.compile(r"^https?://orcid\.org/\d{4}-\d{4}-\d{4}-\d{4}$", re.IGNORECASE)


def compute_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def populate_file_metadata(obj: ThesisFile):
    if not obj.file:
        return
    obj.mime_type = mimetypes.guess_type(obj.original_name)[0] or ""
    abs_path = Path(settings.MEDIA_ROOT) / obj.file.name
    if abs_path.exists():
        obj.sha256 = compute_sha256(str(abs_path))
        obj.size_bytes = abs_path.stat().st_size
        obj.stored_path = obj.file.name
        obj.save(update_fields=["mime_type", "sha256", "size_bytes", "stored_path", "updated_at"])


def _validate_dni_if_present(value: str, field_name: str, errors: List[str]):
    if not value:
        return
    if not value.isdigit():
        errors.append(f"{field_name}: debe contener solo digitos.")
        return
    expected = settings.THESIS_DNI_DEFAULT_LENGTH
    if len(value) != expected:
        errors.append(f"{field_name}: debe tener {expected} digitos.")


def _get_bool_param(key: str, default: bool = False) -> bool:
    value = SystemConfig.objects.filter(key=key).values_list("value", flat=True).first()
    if value is None:
        return default
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "si", "yes", "y", "on"}


def validate_record_for_submission(record: ThesisRecord) -> List[str]:
    errors: List[str] = []

    if not record.career_id:
        errors.append("CARRERA es obligatoria.")
    elif not record.career.active:
        errors.append("La carrera esta inactiva.")
    elif not record.career.handle.strip():
        errors.append("La carrera no tiene handle configurado.")

    if not record.titulo.strip():
        errors.append("TITULO es obligatorio.")
    if not record.autor1_nombre.strip():
        errors.append("AUTOR1_APELLIDOS_NOMBRES es obligatorio.")
    if not record.autor1_dni.strip():
        errors.append("AUTOR1_DNI es obligatorio.")

    _validate_dni_if_present(record.autor1_dni.strip(), "AUTOR1_DNI", errors)
    _validate_dni_if_present(record.autor2_dni.strip(), "AUTOR2_DNI", errors)
    _validate_dni_if_present(record.asesor_dni.strip(), "ASESOR_DNI", errors)

    if record.asesor_orcid.strip() and not ORCID_RE.match(record.asesor_orcid.strip()):
        errors.append("ASESOR_ORCID no tiene formato valido (https://orcid.org/0000-0000-0000-0000).")

    files = record.files.all()
    has_thesis = files.filter(file_type__in=[ThesisFile.TYPE_TESIS_DOCX, ThesisFile.TYPE_TESIS_PDF]).exists()
    has_form = files.filter(file_type=ThesisFile.TYPE_FORMULARIO).exists()
    has_turnitin = files.filter(file_type=ThesisFile.TYPE_TURNITIN).exists()
    require_turnitin = _get_bool_param("INCLUDE_TURNITIN", default=True)

    if not has_thesis:
        errors.append("Debe subir una tesis en DOCX o PDF.")
    if not has_form:
        errors.append("Debe subir al menos un formulario PDF.")
    if require_turnitin and not has_turnitin:
        errors.append("Debe subir al menos un archivo turnitin PDF.")

    return errors


def validate_record_for_approval(record: ThesisRecord) -> List[str]:
    errors = validate_record_for_submission(record)
    for f in record.files.all():
        if not f.file:
            errors.append(f"Archivo {f.original_name} no tiene contenido.")
            continue
        abs_path = Path(settings.MEDIA_ROOT) / f.file.name
        if not abs_path.exists():
            errors.append(f"No existe el archivo fisico: {f.original_name}")
    return errors
