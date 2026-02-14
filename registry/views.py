from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
import json

from accounts.decorators import role_required
from accounts.models import User
from appconfig.models import CareerConfig
from registry.forms import AuditCommentForm, SustentationGroupForm, ThesisFileUploadForm, ThesisRecordForm
from registry.models import AuditEvent, SustentationGroup, ThesisFile, ThesisRecord
from registry.services import populate_file_metadata, validate_record_for_approval, validate_record_for_submission


@login_required
def records_list_view(request):
    messages.info(request, "Los registros se gestionan dentro de Sustentaciones (grupos).")
    return redirect("registry:groups_list")


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
    total_records = group.records.count()
    ready_records = group.records.filter(status=ThesisRecord.STATUS_LISTO).count()
    can_submit_visible = (
        can_manage
        and group.status in [SustentationGroup.STATUS_ARMADO, SustentationGroup.STATUS_OBSERVADO]
        and total_records > 0
    )
    can_submit_now = can_submit_visible and ready_records == total_records
    can_add_records = can_manage and group.status == SustentationGroup.STATUS_ARMADO

    pub_batch = None
    links_form = None
    if request.user.role == User.ROLE_AUDITOR:
        # SAF se gestiona por grupo (el grupo actua como lote de publicacion).
        from saf.forms import DspaceLinksUploadForm
        from saf.models import SafBatch

        pub_batch = SafBatch.objects.filter(group=group).order_by("-created_at").first()
        links_form = DspaceLinksUploadForm()
    return render(
        request,
        "groups/detail.html",
        {
            "group": group,
            "records": list(records_qs),
            "careers": careers,
            "career_filter": career_filter,
            "can_submit_visible": can_submit_visible,
            "can_submit_now": can_submit_now,
            "total_records": total_records,
            "ready_records": ready_records,
            "can_add_records": can_add_records,
            "pub_batch": pub_batch,
            "links_form": links_form,
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

    not_ready = [r.nro for r in records if r.status != ThesisRecord.STATUS_LISTO]
    if not_ready:
        pretty = ", ".join(f"{n:03d}" for n in sorted(not_ready))
        messages.error(request, f"Para enviar a auditoría, todos los registros deben estar en LISTO. Faltan: {pretty}.")
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
        r.mark_submitted(request.user)
        AuditEvent.objects.create(
            record=r,
            action=AuditEvent.ACTION_SEND,
            user=request.user,
            comment="Enviado a auditoría (grupo).",
        )
        sent += 1

    group.recompute_status(save=True)
    messages.success(request, f"Grupo enviado a auditoría. Registros enviados: {sent}.")
    return redirect("registry:groups_detail", group_id=group.id)


@login_required
@require_POST
def records_mark_ready_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if request.user.role != User.ROLE_CARGADOR:
        messages.error(request, "No tienes permisos para esta acción.")
        return redirect("registry:records_detail", record_id=record.id)
    if record.group.status not in [SustentationGroup.STATUS_ARMADO, SustentationGroup.STATUS_OBSERVADO]:
        messages.error(request, "No puedes marcar listo un registro en un grupo que ya fue enviado a auditoría.")
        return redirect("registry:records_detail", record_id=record.id)
    if record.status not in [ThesisRecord.STATUS_BORRADOR, ThesisRecord.STATUS_OBSERVADO]:
        messages.error(request, "Este registro no se puede marcar como listo en su estado actual.")
        return redirect("registry:records_detail", record_id=record.id)

    errors = validate_record_for_submission(record)
    if errors:
        for err in errors:
            messages.error(request, err)
        return redirect("registry:records_detail", record_id=record.id)

    record.status = ThesisRecord.STATUS_LISTO
    record.save(update_fields=["status", "updated_at"])
    record.group.recompute_status(save=True)
    messages.success(request, "Registro marcado como LISTO para auditoría.")
    return redirect("registry:records_detail", record_id=record.id)


@login_required
@require_POST
def records_unready_view(request, record_id: int):
    record = get_object_or_404(ThesisRecord, pk=record_id)
    if request.user.role != User.ROLE_CARGADOR:
        messages.error(request, "No tienes permisos para esta acción.")
        return redirect("registry:records_detail", record_id=record.id)
    if record.group.status not in [SustentationGroup.STATUS_ARMADO, SustentationGroup.STATUS_OBSERVADO]:
        messages.error(request, "No puedes editar un registro en un grupo que ya fue enviado a auditoría.")
        return redirect("registry:records_detail", record_id=record.id)
    if record.status != ThesisRecord.STATUS_LISTO:
        messages.error(request, "Este registro no está en estado LISTO.")
        return redirect("registry:records_detail", record_id=record.id)

    record.status = ThesisRecord.STATUS_BORRADOR
    record.save(update_fields=["status", "updated_at"])
    record.group.recompute_status(save=True)
    messages.success(request, "Registro devuelto a BORRADOR para edición.")
    return redirect("registry:records_detail", record_id=record.id)


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

    advisor_qs = form.fields["asesor_ref"].queryset
    advisors_map = {
        str(a.id): {"nombre": a.nombre or "", "dni": a.dni or "", "orcid": a.orcid or ""}
        for a in advisor_qs
    }
    juror_ids = set()
    for f in ["jurado1_ref", "jurado2_ref", "jurado3_ref"]:
        juror_ids.update(form.fields[f].queryset.values_list("id", flat=True))
    jurors_map = {str(j.id): {"nombre": j.nombre or ""} for j in form.fields["jurado1_ref"].queryset.model.objects.filter(id__in=juror_ids)}
    return render(
        request,
        "records/form.html",
        {
            "form": form,
            "title": "Nuevo registro",
            "group": group,
            "advisors_map_json": json.dumps(advisors_map, ensure_ascii=False),
            "jurors_map_json": json.dumps(jurors_map, ensure_ascii=False),
        },
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

    advisor_qs = form.fields["asesor_ref"].queryset
    advisors_map = {
        str(a.id): {"nombre": a.nombre or "", "dni": a.dni or "", "orcid": a.orcid or ""}
        for a in advisor_qs
    }
    juror_ids = set()
    for f in ["jurado1_ref", "jurado2_ref", "jurado3_ref"]:
        juror_ids.update(form.fields[f].queryset.values_list("id", flat=True))
    jurors_map = {str(j.id): {"nombre": j.nombre or ""} for j in form.fields["jurado1_ref"].queryset.model.objects.filter(id__in=juror_ids)}
    return render(
        request,
        "records/form.html",
        {
            "form": form,
            "record": record,
            "title": title,
            "read_only": read_only,
            "advisors_map_json": json.dumps(advisors_map, ensure_ascii=False),
            "jurors_map_json": json.dumps(jurors_map, ensure_ascii=False),
        },
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
