from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from appconfig.models import CareerConfig
from registry.forms import AuditCommentForm, SustentationGroupForm, ThesisFileUploadForm, ThesisRecordForm
from registry.models import AuditEvent, SustentationGroup, ThesisFile, ThesisRecord
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
def groups_list_view(request):
    groups = SustentationGroup.objects.all()
    form = SustentationGroupForm(initial={"date": timezone.localdate()})
    return render(request, "groups/list.html", {"groups": groups, "form": form})


@login_required
def groups_create_view(request):
    if request.method == "POST":
        form = SustentationGroupForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data["date"]
            obj, created = SustentationGroup.objects.get_or_create(
                date=d,
                defaults={"name": SustentationGroup.name_for_date(d), "created_by": request.user},
            )
            if created:
                messages.success(request, f"Grupo creado: {obj.name}.")
            else:
                messages.warning(request, f"Ya existe un grupo para esa fecha: {obj.name}.")
            return redirect("registry:groups_detail", group_id=obj.id)
    else:
        form = SustentationGroupForm()
    return render(request, "groups/form.html", {"form": form, "title": "Nuevo grupo de sustentación"})


@login_required
def groups_detail_view(request, group_id: int):
    group = get_object_or_404(SustentationGroup, pk=group_id)
    records_qs = group.records.select_related("career").order_by("nro")
    career_filter = (request.GET.get("career") or "").strip()
    careers = (
        CareerConfig.objects.filter(id__in=records_qs.values_list("career_id", flat=True))
        .distinct()
        .order_by("carrera_excel")
    )
    if career_filter.isdigit():
        records_qs = records_qs.filter(career_id=int(career_filter))
    can_manage = request.user.role == User.ROLE_CARGADOR
    can_submit = can_manage and group.status in [SustentationGroup.STATUS_ARMADO, SustentationGroup.STATUS_OBSERVADO]
    can_add_records = can_manage and group.status == SustentationGroup.STATUS_ARMADO
    return render(
        request,
        "groups/detail.html",
        {
            "group": group,
            "records": list(records_qs),
            "careers": careers,
            "career_filter": career_filter,
            "can_submit": can_submit,
            "can_add_records": can_add_records,
        },
    )


@login_required
@require_POST
def groups_submit_view(request, group_id: int):
    group = get_object_or_404(SustentationGroup, pk=group_id)
    if request.user.role != User.ROLE_CARGADOR:
        messages.error(request, "No tienes permisos para enviar este grupo a auditoría.")
        return redirect("registry:groups_detail", group_id=group.id)
    if group.status not in [SustentationGroup.STATUS_ARMADO, SustentationGroup.STATUS_OBSERVADO]:
        messages.error(request, "Este grupo no se puede enviar a auditoría en su estado actual.")
        return redirect("registry:groups_detail", group_id=group.id)

    records = list(group.records.all())
    if not records:
        messages.error(request, "El grupo no tiene registros.")
        return redirect("registry:groups_detail", group_id=group.id)

    has_errors = False
    for r in records:
        errs = validate_record_for_submission(r)
        if errs:
            has_errors = True
            messages.error(request, f"Registro {r.nro:03d}: " + " | ".join(errs))
    if has_errors:
        return redirect("registry:groups_detail", group_id=group.id)

    sent = 0
    for r in records:
        if r.status in [ThesisRecord.STATUS_BORRADOR, ThesisRecord.STATUS_OBSERVADO]:
            action = AuditEvent.ACTION_RESUBMIT if r.status == ThesisRecord.STATUS_OBSERVADO else AuditEvent.ACTION_SEND
            r.mark_submitted(request.user)
            comment = "Reenviado a auditoría (grupo)." if action == AuditEvent.ACTION_RESUBMIT else "Enviado a auditoría (grupo)."
            AuditEvent.objects.create(record=r, action=action, user=request.user, comment=comment)
            sent += 1

    group.recompute_status(save=True)
    messages.success(request, f"Grupo enviado a auditoría. Registros enviados: {sent}.")
    return redirect("registry:groups_detail", group_id=group.id)


@login_required
def records_create_view(request):
    group_id = (request.GET.get("group") or "").strip()
    if not group_id.isdigit():
        messages.error(request, "Debes crear/seleccionar un grupo de sustentación antes de crear registros.")
        return redirect("registry:groups_list")
    group = get_object_or_404(SustentationGroup, pk=int(group_id))
    if group.status != SustentationGroup.STATUS_ARMADO:
        messages.error(request, "No puedes agregar registros a un grupo que ya fue enviado a auditoría.")
        return redirect("registry:groups_detail", group_id=group.id)
    if request.method == "POST":
        form = ThesisRecordForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.group = group
            obj.save()
            messages.success(request, f"Registro {obj.nro:03d} creado.")
            return redirect("registry:records_detail", record_id=obj.id)
    else:
        form = ThesisRecordForm()
    return render(
        request,
        "records/form.html",
        {"form": form, "title": "Nuevo registro", "group": group},
    )


@login_required
def records_edit_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    # Auditor siempre ve en solo lectura. Cargador puede editar solo en estados permitidos,
    # pero puede ver metadatos en cualquier estado.
    can_edit = record.can_edit(request.user)
    read_only = (request.user.role == User.ROLE_AUDITOR) or (not can_edit)
    if request.method == "POST" and not can_edit:
        messages.error(request, "No puedes guardar cambios en este registro en su estado actual.")
        return redirect("registry:records_detail", record_id=record.id)

    if request.method == "POST":
        form = ThesisRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, "Registro actualizado.")
            return redirect("registry:records_detail", record_id=record.id)
    else:
        form = ThesisRecordForm(instance=record)
        if read_only:
            for field in form.fields.values():
                field.disabled = True
    title = (f"Ver registro {record.nro:03d}") if read_only else (f"Editar registro {record.nro:03d}")
    return render(
        request,
        "records/form.html",
        {"form": form, "record": record, "title": title, "read_only": read_only},
    )


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
            "group": record.group,
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
    messages.warning(request, "El envío a auditoría se realiza por grupo. Usa 'Enviar grupo a auditoría'.")
    return redirect("registry:groups_detail", group_id=record.group_id)


@login_required
@require_POST
def records_resubmit_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    messages.warning(request, "El reenvío a auditoría se realiza por grupo. Usa 'Enviar grupo a auditoría'.")
    return redirect("registry:groups_detail", group_id=record.group_id)


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
    if record.group_id:
        record.group.recompute_status(save=True)
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
    if record.group_id:
        record.group.recompute_status(save=True)
    messages.success(request, "Registro aprobado.")
    return redirect("registry:records_detail", record_id=record.id)

# Create your views here.
