from datetime import datetime
from pathlib import Path
import json
import threading

from django.contrib import messages
from django.db import close_old_connections, models
from django.http import FileResponse, Http404, JsonResponse
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
    batches = SafBatch.objects.select_related("created_by", "group").order_by("-created_at", "-id")[:200]

    publish_groups = (
        SustentationGroup.objects.annotate(total_records=models.Count("records"))
        .filter(
            status__in=[
                SustentationGroup.STATUS_APROBADO,
                SustentationGroup.STATUS_POR_PUBLICAR,
                SustentationGroup.STATUS_PUBLICADO,
            ]
        )
        .order_by("-date", "-id")[:200]
    )
    group_ids = [g.id for g in publish_groups]
    latest_batch_by_group = {}
    if group_ids:
        for b in SafBatch.objects.select_related("created_by", "group").filter(group_id__in=group_ids).order_by(
            "-created_at",
            "-id",
        ):
            if b.group_id and b.group_id not in latest_batch_by_group:
                latest_batch_by_group[b.group_id] = b

    group_rows = [{"group": g, "batch": latest_batch_by_group.get(g.id)} for g in publish_groups]
    return render(
        request,
        "saf/batches_list.html",
        {"batches": list(batches), "publish_groups": group_rows},
    )


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


def _get_or_create_group_batch(group: SustentationGroup, user) -> SafBatch:
    batch = SafBatch.objects.filter(group=group).order_by("-created_at").first()
    if batch:
        return batch
    # One batch per group in the new flow (code is internal; UI should not show it).
    code = f"SAF_{group.date.strftime('%Y%m%d')}_G{group.id}"
    return SafBatch.objects.create(batch_code=code, created_by=user, group=group)


def _wants_json(request) -> bool:
    accept = (request.headers.get("Accept") or "").lower()
    xrw = (request.headers.get("X-Requested-With") or "").lower()
    return ("application/json" in accept) or (xrw == "xmlhttprequest")


@role_required(User.ROLE_AUDITOR)
@require_POST
def groups_generate_view(request, group_id: int):
    group = get_object_or_404(SustentationGroup, pk=group_id)
    records = list(group.records.order_by("nro"))
    if not records:
        msg = "El grupo no tiene registros."
        if _wants_json(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("registry:groups_detail", group_id=group.id)

    # Allow generating when the group is APROBADO or already moved to POR_PUBLICAR due to a previous attempt.
    if group.status not in [SustentationGroup.STATUS_APROBADO, SustentationGroup.STATUS_POR_PUBLICAR]:
        msg = "Este grupo no está listo para generar SAF en su estado actual."
        if _wants_json(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("registry:groups_detail", group_id=group.id)

    not_ok = [r.nro for r in records if r.status not in [ThesisRecord.STATUS_APROBADO, ThesisRecord.STATUS_POR_PUBLICAR]]
    if not_ok:
        pretty = ", ".join(f"{n:03d}" for n in sorted(not_ok))
        msg = f"Para generar SAF, todos los registros deben estar APROBADO (o POR PUBLICAR). Revisa: {pretty}."
        if _wants_json(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("registry:groups_detail", group_id=group.id)

    batch = _get_or_create_group_batch(group, request.user)
    if batch.status == SafBatch.STATUS_RUNNING:
        msg = "El SAF ya está en proceso. Espera a que termine."
        if _wants_json(request):
            return JsonResponse({"ok": True, "message": msg, "status": batch.status, "batch_id": batch.id})
        messages.warning(request, msg)
        return redirect("registry:groups_detail", group_id=group.id)
    if batch.status == SafBatch.STATUS_DONE and batch.zip_path:
        msg = "Este SAF ya fue generado. No se puede generar nuevamente."
        if _wants_json(request):
            return JsonResponse({"ok": False, "message": msg, "status": batch.status, "batch_id": batch.id}, status=400)
        messages.warning(request, msg)
        return redirect("registry:groups_detail", group_id=group.id)

    # Ensure every record is present as an item.
    existing = set(batch.items.values_list("record_id", flat=True))
    to_create = [SafBatchItem(batch=batch, record=r) for r in records if r.id not in existing]
    if to_create:
        SafBatchItem.objects.bulk_create(to_create)

    # Mark as running and start in background thread so the UI can poll progress.
    batch.status = SafBatch.STATUS_RUNNING
    batch.log_text = "Iniciando generación SAF..."
    batch.save(update_fields=["status", "log_text", "updated_at"])

    batch_id = batch.id
    group_pk = group.id

    def _run():
        close_old_connections()
        try:
            b = SafBatch.objects.get(pk=batch_id)
            generate_saf_batch(b)
            g = SustentationGroup.objects.get(pk=group_pk)
            g.recompute_status(save=True)
        except Exception as exc:  # noqa: BLE001
            try:
                b = SafBatch.objects.get(pk=batch_id)
                b.status = SafBatch.STATUS_FAILED
                b.log_text = f"Error: {exc}"
                b.save(update_fields=["status", "log_text", "updated_at"])
            except Exception:  # noqa: BLE001
                pass
        finally:
            close_old_connections()

    threading.Thread(target=_run, daemon=True).start()

    msg = "Generación SAF iniciada."
    if _wants_json(request):
        return JsonResponse({"ok": True, "message": msg, "status": SafBatch.STATUS_RUNNING, "batch_id": batch_id})
    messages.success(request, msg)
    return redirect("registry:groups_detail", group_id=group.id)


@role_required(User.ROLE_AUDITOR)
def groups_progress_view(request, group_id: int):
    group = get_object_or_404(SustentationGroup, pk=group_id)
    batch = SafBatch.objects.filter(group=group).order_by("-created_at").first()
    if not batch:
        return JsonResponse({"ok": False, "message": "Sin SAF para este grupo."}, status=404)

    total = batch.items.count()
    done = batch.items.exclude(result=SafBatchItem.RESULT_PENDING).count()
    percent = int((done * 100) / total) if total else 0
    return JsonResponse(
        {
            "ok": True,
            "batch_id": batch.id,
            "status": batch.status,
            "total": total,
            "done": done,
            "percent": percent,
            "zip_ready": bool(batch.zip_path),
            "message": (batch.log_text or "").strip(),
        }
    )


@role_required(User.ROLE_AUDITOR)
def groups_download_view(request, group_id: int):
    group = get_object_or_404(SustentationGroup, pk=group_id)
    batch = SafBatch.objects.filter(group=group).order_by("-created_at").first()
    if not batch or not batch.zip_path:
        raise Http404("El grupo aún no tiene ZIP generado.")
    zip_path = Path(batch.zip_path)
    if not zip_path.exists():
        raise Http404("No se encontró el ZIP en disco.")
    return FileResponse(open(zip_path, "rb"), as_attachment=True, filename=zip_path.name)


@role_required(User.ROLE_AUDITOR)
@require_POST
def groups_upload_links_view(request, group_id: int):
    group = get_object_or_404(SustentationGroup, pk=group_id)
    if group.status not in [SustentationGroup.STATUS_POR_PUBLICAR, SustentationGroup.STATUS_PUBLICADO]:
        messages.error(request, "Aún no puedes aplicar enlaces en este grupo.")
        return redirect("registry:groups_detail", group_id=group.id)

    form = DspaceLinksUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Debes adjuntar un archivo JSON válido.")
        return redirect("registry:groups_detail", group_id=group.id)

    up = form.cleaned_data["links_file"]
    try:
        payload = json.loads(up.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        messages.error(request, "No se pudo leer el JSON. Verifica el formato y la codificación UTF-8.")
        return redirect("registry:groups_detail", group_id=group.id)

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
        return redirect("registry:groups_detail", group_id=group.id)

    from django.conf import settings

    base = (getattr(settings, "DSPACE_BASE_URL", "") or "").strip().rstrip("/")
    updated = 0
    errors = 0

    group_records = {r.nro: r for r in group.records.all()}

    for nro_raw, url, handle in rows:
        if not nro_raw:
            continue
        nro_clean = nro_raw.zfill(3) if nro_raw.isdigit() else nro_raw
        if not nro_clean.isdigit():
            errors += 1
            continue
        nro_int = int(nro_clean)
        rec = group_records.get(nro_int)
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

    group.recompute_status(save=True)
    return redirect("registry:groups_detail", group_id=group.id)
