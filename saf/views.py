from datetime import datetime
from pathlib import Path

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from registry.models import ThesisRecord
from saf.forms import BatchCreateForm
from saf.models import SafBatch, SafBatchItem
from saf.services import generate_saf_batch


@role_required(User.ROLE_AUDITOR)
def batches_list_view(request):
    if request.method == "POST":
        form = BatchCreateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Debes seleccionar al menos un registro aprobado.")
            return redirect("saf:batches_list")
        batch_code = datetime.now().strftime("LOTE_%Y%m%d_%H%M%S")
        batch = SafBatch.objects.create(batch_code=batch_code, created_by=request.user)
        for record in form.cleaned_data["records"]:
            SafBatchItem.objects.create(batch=batch, record=record)
        messages.success(request, f"Lote {batch.batch_code} creado con {batch.items.count()} registros.")
        return redirect("saf:batches_detail", batch_id=batch.id)

    batches = SafBatch.objects.select_related("created_by").all()
    form = BatchCreateForm()
    return render(request, "saf/batches_list.html", {"batches": batches, "form": form})


@role_required(User.ROLE_AUDITOR)
@require_POST
def batches_create_view(request):
    form = BatchCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Debes seleccionar al menos un registro aprobado.")
        return redirect("saf:batches_list")

    batch_code = datetime.now().strftime("LOTE_%Y%m%d_%H%M%S")
    batch = SafBatch.objects.create(batch_code=batch_code, created_by=request.user)
    for record in form.cleaned_data["records"]:
        SafBatchItem.objects.create(batch=batch, record=record)
    messages.success(request, f"Lote {batch.batch_code} creado con {batch.items.count()} registros.")
    return redirect("saf:batches_detail", batch_id=batch.id)


@role_required(User.ROLE_AUDITOR)
def batches_detail_view(request, batch_id: int):
    batch = get_object_or_404(SafBatch.objects.select_related("created_by"), pk=batch_id)
    items = batch.items.select_related("record", "record__career").all()
    return render(request, "saf/batch_detail.html", {"batch": batch, "items": items})


@role_required(User.ROLE_AUDITOR)
@require_POST
def batches_generate_view(request, batch_id: int):
    batch = get_object_or_404(SafBatch, pk=batch_id)
    ok, msg = generate_saf_batch(batch)
    if ok:
        messages.success(request, msg)
    else:
        messages.warning(request, msg)
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
def approved_records_view(request):
    records = ThesisRecord.objects.filter(status=ThesisRecord.STATUS_APROBADO).order_by("nro")
    return render(request, "saf/approved_records.html", {"records": records})

# Create your views here.
