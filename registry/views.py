from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from registry.forms import AuditCommentForm, ThesisFileUploadForm, ThesisRecordForm
from registry.models import AuditEvent, ThesisFile, ThesisRecord
from registry.services import populate_file_metadata, validate_record_for_approval, validate_record_for_submission


@login_required
def records_list_view(request):
    qs = ThesisRecord.objects.select_related("career").all()
    status = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        filters = (
            Q(titulo__icontains=q)
            | Q(autor1_nombre__icontains=q)
            | Q(autor2_nombre__icontains=q)
            | Q(autor3_nombre__icontains=q)
        )
        if q.isdigit():
            filters = filters | Q(nro=int(q))
        qs = qs.filter(filters)
    records = qs.order_by("-created_at")
    return render(
        request,
        "records/list.html",
        {
            "records": records,
            "status_filter": status,
            "q": q,
            "status_choices": ThesisRecord.STATUS_CHOICES,
        },
    )


@login_required
def records_create_view(request):
    if request.method == "POST":
        form = ThesisRecordForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Registro {obj.nro:03d} creado.")
            return redirect("registry:records_detail", record_id=obj.id)
    else:
        form = ThesisRecordForm()
    return render(request, "records/form.html", {"form": form, "title": "Nuevo registro"})


@login_required
def records_edit_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if not record.can_edit(request.user):
        messages.error(request, "No puedes editar este registro en su estado actual.")
        return redirect("registry:records_detail", record_id=record.id)

    if request.method == "POST":
        form = ThesisRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, "Registro actualizado.")
            return redirect("registry:records_detail", record_id=record.id)
    else:
        form = ThesisRecordForm(instance=record)
    return render(request, "records/form.html", {"form": form, "record": record, "title": f"Editar registro {record.nro:03d}"})


@login_required
def records_detail_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    upload_form = ThesisFileUploadForm()
    comment_form = AuditCommentForm()
    files = record.files.order_by("file_type", "original_name")
    events = record.audit_events.select_related("user").all()
    can_edit = record.can_edit(request.user)
    can_audit = request.user.role == User.ROLE_AUDITOR
    return render(
        request,
        "records/detail.html",
        {
            "record": record,
            "files": files,
            "events": events,
            "upload_form": upload_form,
            "comment_form": comment_form,
            "can_edit": can_edit,
            "can_audit": can_audit,
        },
    )


@login_required
@require_POST
def records_upload_file_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if not record.can_edit(request.user):
        messages.error(request, "No puedes subir archivos en este estado.")
        return redirect("registry:records_detail", record_id=record.id)

    form = ThesisFileUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, f"Error al subir archivo: {form.errors.as_text()}")
        return redirect("registry:records_detail", record_id=record.id)

    file_type = form.cleaned_data["file_type"]
    in_file = form.cleaned_data["file"]

    if file_type in [ThesisFile.TYPE_TESIS_DOCX, ThesisFile.TYPE_TESIS_PDF]:
        for old in record.files.filter(file_type=file_type):
            old.file.delete(save=False)
            old.delete()

    obj = ThesisFile(record=record, file_type=file_type, original_name=in_file.name, file=in_file)
    obj.save()
    populate_file_metadata(obj)
    messages.success(request, f"Archivo {in_file.name} cargado.")
    return redirect("registry:records_detail", record_id=record.id)


@login_required
@require_POST
def records_delete_file_view(request, record_id: int, file_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if not record.can_edit(request.user):
        messages.error(request, "No puedes eliminar archivos en este estado.")
        return redirect("registry:records_detail", record_id=record.id)

    file_obj = get_object_or_404(ThesisFile, pk=file_id, record=record)
    file_name = file_obj.original_name
    file_obj.file.delete(save=False)
    file_obj.delete()
    messages.success(request, f"Archivo eliminado: {file_name}")
    return redirect("registry:records_detail", record_id=record.id)


@login_required
@require_POST
def records_submit_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if not record.can_edit(request.user):
        messages.error(request, "No puedes enviar este registro en su estado actual.")
        return redirect("registry:records_detail", record_id=record.id)
    errors = validate_record_for_submission(record)
    if errors:
        for err in errors:
            messages.error(request, err)
        return redirect("registry:records_detail", record_id=record.id)

    action = AuditEvent.ACTION_RESUBMIT if record.status == ThesisRecord.STATUS_OBSERVADO else AuditEvent.ACTION_SEND
    record.mark_submitted(request.user)
    AuditEvent.objects.create(record=record, action=action, user=request.user, comment="Enviado a auditoría.")
    messages.success(request, "Registro enviado a auditoría.")
    return redirect("registry:records_detail", record_id=record.id)


@login_required
@require_POST
def records_resubmit_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if record.status != ThesisRecord.STATUS_OBSERVADO:
        messages.error(request, "Solo se puede reenviar un registro observado.")
        return redirect("registry:records_detail", record_id=record.id)
    return records_submit_view(request, record_id)


@role_required(User.ROLE_AUDITOR)
@require_POST
def records_observe_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if record.status != ThesisRecord.STATUS_EN_AUDITORIA:
        messages.error(request, "Solo se pueden observar registros en auditoría.")
        return redirect("registry:records_detail", record_id=record.id)
    comment_form = AuditCommentForm(request.POST)
    comment_form.is_valid()
    comment = comment_form.cleaned_data.get("comment", "").strip()
    if not comment:
        messages.error(request, "Debes ingresar observación.")
        return redirect("registry:records_detail", record_id=record.id)
    record.mark_observed()
    AuditEvent.objects.create(record=record, action=AuditEvent.ACTION_OBSERVE, user=request.user, comment=comment)
    messages.success(request, "Registro observado y devuelto al cargador.")
    return redirect("registry:records_detail", record_id=record.id)


@role_required(User.ROLE_AUDITOR)
@require_POST
def records_approve_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if record.status != ThesisRecord.STATUS_EN_AUDITORIA:
        messages.error(request, "Solo se pueden aprobar registros en auditoría.")
        return redirect("registry:records_detail", record_id=record.id)
    errors = validate_record_for_approval(record)
    if errors:
        for err in errors:
            messages.error(request, err)
        return redirect("registry:records_detail", record_id=record.id)
    comment_form = AuditCommentForm(request.POST)
    comment_form.is_valid()
    comment = comment_form.cleaned_data.get("comment", "").strip()
    record.mark_approved(request.user)
    AuditEvent.objects.create(
        record=record,
        action=AuditEvent.ACTION_APPROVE,
        user=request.user,
        comment=comment or "Aprobado para lote SAF.",
    )
    messages.success(request, "Registro aprobado.")
    return redirect("registry:records_detail", record_id=record.id)

# Create your views here.
