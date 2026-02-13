from datetime import datetime
from pathlib import Path
import json

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from registry.models import AuditEvent, SustentationGroup, ThesisRecord
from saf.forms import DspaceLinksUploadForm
from saf.models import SafBatch, SafBatchItem
from saf.services import generate_batch_scripts_only, generate_saf_batch


@role_required(User.ROLE_AUDITOR)
def batches_list_view(request):
    if request.method == "POST":
        messages.warning(request, "Los lotes SAF se crean desde un grupo de sustentación.")
        return redirect("saf:batches_list")

    batches = SafBatch.objects.select_related("created_by", "group").all()
    return render(request, "saf/batches_list.html", {"batches": batches})


@role_required(User.ROLE_AUDITOR)
def batches_detail_view(request, batch_id: int):
    batch = get_object_or_404(SafBatch.objects.select_related("created_by", "group"), pk=batch_id)
    items = batch.items.select_related("record", "record__career").all()
    return render(
        request,
        "saf/batch_detail.html",
        {"batch": batch, "items": items, "links_form": DspaceLinksUploadForm()},
    )


@role_required(User.ROLE_AUDITOR)
@require_POST
def batches_generate_view(request, batch_id: int):
    batch = get_object_or_404(SafBatch, pk=batch_id)
    if batch.status == SafBatch.STATUS_RUNNING:
        messages.warning(request, "El lote ya está en proceso. Espera a que termine.")
        return redirect("saf:batches_detail", batch_id=batch.id)
    if batch.status == SafBatch.STATUS_DONE and batch.zip_path:
        messages.warning(request, "Este lote ya fue generado. No se puede generar nuevamente.")
        return redirect("saf:batches_detail", batch_id=batch.id)
    ok, msg = generate_saf_batch(batch)
    if ok:
        messages.success(request, msg)
    else:
        messages.warning(request, msg)
    if batch.group_id:
        batch.group.recompute_status(save=True)
    return redirect("saf:batches_detail", batch_id=batch.id)


@role_required(User.ROLE_AUDITOR)
def batches_download_view(request, batch_id: int):
    batch = get_object_or_404(SafBatch, pk=batch_id)
    if not batch.zip_path:
        raise Http404("El lote aún no tiene ZIP generado.")
    zip_path = Path(batch.zip_path)
    if not zip_path.exists():
        raise Http404("No se encontró el ZIP en disco.")
    return FileResponse(open(zip_path, "rb"), as_attachment=True, filename=zip_path.name)


@role_required(User.ROLE_AUDITOR)
@require_POST
def batches_scripts_view(request, batch_id: int):
    batch = get_object_or_404(SafBatch, pk=batch_id)
    ok, msg = generate_batch_scripts_only(batch)
    if ok:
        messages.success(request, msg)
    else:
        messages.warning(request, msg)
    return redirect("saf:batches_detail", batch_id=batch.id)

# Create your views here.


@role_required(User.ROLE_AUDITOR)
@require_POST
def batches_upload_links_view(request, batch_id: int):
    batch = get_object_or_404(SafBatch, pk=batch_id)
    form = DspaceLinksUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Debes adjuntar un archivo JSON válido.")
        return redirect("saf:batches_detail", batch_id=batch.id)

    up = form.cleaned_data["links_file"]
    try:
        payload = json.loads(up.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        messages.error(request, "No se pudo leer el JSON. Verifica el formato y la codificación UTF-8.")
        return redirect("saf:batches_detail", batch_id=batch.id)

    # Normalize to list of (nro_str, url, handle)
    rows = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            nro = str(k).strip()
            if isinstance(v, str):
                rows.append((nro, v.strip(), ""))
            elif isinstance(v, dict):
                rows.append((nro, str(v.get("url", "")).strip(), str(v.get("handle", "")).strip()))
    elif isinstance(payload, list):
        for it in payload:
            if not isinstance(it, dict):
                continue
            nro = str(it.get("nro", "")).strip()
            rows.append((nro, str(it.get("url", "")).strip(), str(it.get("handle", "")).strip()))
    else:
        messages.error(request, "JSON no soportado. Usa un objeto o una lista.")
        return redirect("saf:batches_detail", batch_id=batch.id)

    from django.conf import settings

    base = (getattr(settings, "DSPACE_BASE_URL", "") or "").strip().rstrip("/")
    updated = 0
    errors = 0

    # Only allow updating records that are in this batch.
    batch_records = {i.record.nro: i.record for i in batch.items.select_related("record").all()}

    for nro_raw, url, handle in rows:
        if not nro_raw:
            continue
        nro_clean = nro_raw.zfill(3) if nro_raw.isdigit() else nro_raw
        if not nro_clean.isdigit():
            errors += 1
            continue
        nro_int = int(nro_clean)
        rec = batch_records.get(nro_int)
        if not rec:
            errors += 1
            continue

        h = handle
        u = url
        if not u and h and base:
            u = f"{base}/handle/{h.lstrip('/')}"
        if not u and not h:
            errors += 1
            continue

        changed = False
        if h and rec.dspace_handle != h:
            rec.dspace_handle = h
            changed = True
        if u and rec.dspace_url != u:
            rec.dspace_url = u
            changed = True
        if rec.status != ThesisRecord.STATUS_PUBLICADO:
            rec.status = ThesisRecord.STATUS_PUBLICADO
            changed = True
        if changed:
            rec.save(update_fields=["dspace_handle", "dspace_url", "status", "updated_at"])
            AuditEvent.objects.create(
                record=rec,
                action=AuditEvent.ACTION_PUBLISH,
                user=request.user,
                comment=(f"Publicado: {rec.dspace_url}" if rec.dspace_url else "Publicado."),
            )
            updated += 1

    if updated:
        messages.success(request, f"Enlaces aplicados: {updated}. Errores: {errors}.")
    else:
        messages.warning(request, f"No se aplicaron cambios. Errores: {errors}.")
    if batch.group_id:
        batch.group.recompute_status(save=True)
    return redirect("saf:batches_detail", batch_id=batch.id)


@role_required(User.ROLE_AUDITOR)
@require_POST
def batches_create_from_group_view(request, group_id: int):
    group = get_object_or_404(SustentationGroup, pk=group_id)
    if SafBatch.objects.filter(group=group).exists():
        messages.warning(request, "Este grupo ya tiene un lote creado.")
        batch = SafBatch.objects.filter(group=group).order_by("-created_at").first()
        return redirect("saf:batches_detail", batch_id=batch.id)  # type: ignore[arg-type]

    records = list(group.records.order_by("nro"))
    if not records:
        messages.error(request, "El grupo no tiene registros.")
        return redirect("registry:groups_detail", group_id=group.id)
    not_ok = [r.nro for r in records if r.status != ThesisRecord.STATUS_APROBADO]
    if not_ok:
        messages.error(request, "Para crear el lote SAF, todos los registros del grupo deben estar APROBADO.")
        return redirect("registry:groups_detail", group_id=group.id)

    batch_code = datetime.now().strftime(f"LOTE_{group.date.strftime('%Y%m%d')}_%H%M%S")
    batch = SafBatch.objects.create(batch_code=batch_code, created_by=request.user, group=group)
    for record in records:
        SafBatchItem.objects.create(batch=batch, record=record)
    messages.success(request, f"Lote {batch.batch_code} creado con {batch.items.count()} registros.")
    return redirect("saf:batches_detail", batch_id=batch.id)
