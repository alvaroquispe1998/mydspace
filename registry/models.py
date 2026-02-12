import os
import uuid
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from appconfig.models import CareerConfig


def thesis_file_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    safe_ext = ext if ext else ".bin"
    return f"records/{instance.record_id}/{instance.file_type}_{uuid.uuid4().hex}{safe_ext}"


class ThesisRecord(models.Model):
    STATUS_BORRADOR = "BORRADOR"
    STATUS_EN_AUDITORIA = "EN_AUDITORIA"
    STATUS_OBSERVADO = "OBSERVADO"
    STATUS_APROBADO = "APROBADO"
    STATUS_INCLUIDO_EN_LOTE = "INCLUIDO_EN_LOTE"
    STATUS_CHOICES = [
        (STATUS_BORRADOR, "Borrador"),
        (STATUS_EN_AUDITORIA, "En auditoría"),
        (STATUS_OBSERVADO, "Observado"),
        (STATUS_APROBADO, "Aprobado"),
        (STATUS_INCLUIDO_EN_LOTE, "Incluido en lote"),
    ]

    nro = models.PositiveIntegerField(unique=True, editable=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_BORRADOR)
    career = models.ForeignKey(CareerConfig, on_delete=models.PROTECT, null=True, blank=True)

    titulo = models.CharField(max_length=500, blank=True)
    autor1_nombre = models.CharField(max_length=255, blank=True)
    autor1_dni = models.CharField(max_length=20, blank=True)
    autor2_nombre = models.CharField(max_length=255, blank=True)
    autor2_dni = models.CharField(max_length=20, blank=True)
    autor3_nombre = models.CharField(max_length=255, blank=True)
    autor3_dni = models.CharField(max_length=20, blank=True)
    asesor_nombre = models.CharField(max_length=255, blank=True)
    asesor_dni = models.CharField(max_length=20, blank=True)
    asesor_orcid = models.CharField(max_length=255, blank=True)
    jurado1 = models.CharField(max_length=255, blank=True)
    jurado2 = models.CharField(max_length=255, blank=True)
    jurado3 = models.CharField(max_length=255, blank=True)
    resumen = models.TextField(blank=True)
    keywords_raw = models.TextField(blank=True)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submitted_records",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_records",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nro:03d} - {self.titulo or 'Sin título'}"

    @property
    def authors_display(self) -> str:
        authors = [
            self.autor1_nombre.strip(),
            self.autor2_nombre.strip(),
            self.autor3_nombre.strip(),
        ]
        authors = [a for a in authors if a]
        return " - ".join(authors)

    @classmethod
    def next_nro(cls) -> int:
        with transaction.atomic():
            last = cls.objects.select_for_update().order_by("-nro").first()
            return (last.nro + 1) if last else 1

    def save(self, *args, **kwargs):
        if not self.nro:
            self.nro = self.next_nro()
        super().save(*args, **kwargs)

    def can_edit(self, user) -> bool:
        # Regla de negocio: una vez enviado a auditoria o aprobado/incluido en lote,
        # el registro no debe modificarse (metadatos ni archivos) para evitar inconsistencias.
        return self.status in [self.STATUS_BORRADOR, self.STATUS_OBSERVADO]

    def mark_submitted(self, user):
        self.status = self.STATUS_EN_AUDITORIA
        self.submitted_by = user
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])

    def mark_observed(self):
        self.status = self.STATUS_OBSERVADO
        self.save(update_fields=["status", "updated_at"])

    def mark_approved(self, user):
        self.status = self.STATUS_APROBADO
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])


class ThesisFile(models.Model):
    TYPE_TESIS_DOCX = "tesis_docx"
    TYPE_TESIS_PDF = "tesis_pdf"
    TYPE_FORMULARIO = "formulario"
    TYPE_TURNITIN = "turnitin"
    FILE_TYPES = [
        (TYPE_TESIS_DOCX, "Tesis DOCX"),
        (TYPE_TESIS_PDF, "Tesis PDF"),
        (TYPE_FORMULARIO, "Formulario"),
        (TYPE_TURNITIN, "Turnitin"),
    ]

    record = models.ForeignKey(ThesisRecord, on_delete=models.CASCADE, related_name="files")
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    original_name = models.CharField(max_length=255)
    stored_path = models.CharField(max_length=500, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    file = models.FileField(upload_to=thesis_file_upload_to)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.record.nro:03d} {self.file_type} {self.original_name}"

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = os.path.basename(self.file.name)
        super().save(*args, **kwargs)
        if self.file:
            self.stored_path = self.file.name
            self.size_bytes = self.file.size
            super().save(update_fields=["stored_path", "size_bytes", "updated_at"])


class AuditEvent(models.Model):
    ACTION_SEND = "send"
    ACTION_OBSERVE = "observe"
    ACTION_RESUBMIT = "resubmit"
    ACTION_APPROVE = "approve"
    ACTION_CHOICES = [
        (ACTION_SEND, "Enviar"),
        (ACTION_OBSERVE, "Observar"),
        (ACTION_RESUBMIT, "Reenviar"),
        (ACTION_APPROVE, "Aprobar"),
    ]

    record = models.ForeignKey(ThesisRecord, on_delete=models.CASCADE, related_name="audit_events")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    comment = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="audit_events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.record.nro:03d} {self.action}"
