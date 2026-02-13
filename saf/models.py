from django.conf import settings
from django.db import models

from registry.models import ThesisRecord


class SafBatch(models.Model):
    STATUS_CREATED = "CREATED"
    STATUS_RUNNING = "RUNNING"
    STATUS_DONE = "DONE"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_CREATED, "Creado"),
        (STATUS_RUNNING, "En proceso"),
        (STATUS_DONE, "Completado"),
        (STATUS_FAILED, "Fallido"),
    ]

    batch_code = models.CharField(max_length=100, unique=True)
    group = models.ForeignKey(
        "registry.SustentationGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="batches",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="saf_batches")
    generated_at = models.DateTimeField(null=True, blank=True)
    output_path = models.CharField(max_length=500, blank=True)
    report_path = models.CharField(max_length=500, blank=True)
    zip_path = models.CharField(max_length=500, blank=True)
    log_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.batch_code


class SafBatchItem(models.Model):
    RESULT_OK = "OK"
    RESULT_ERROR = "ERROR"
    RESULT_PENDING = "PENDING"
    RESULT_CHOICES = [
        (RESULT_PENDING, "Pendiente"),
        (RESULT_OK, "OK"),
        (RESULT_ERROR, "Error"),
    ]

    batch = models.ForeignKey(SafBatch, on_delete=models.CASCADE, related_name="items")
    record = models.ForeignKey(ThesisRecord, on_delete=models.PROTECT, related_name="batch_items")
    item_folder_name = models.CharField(max_length=120, blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default=RESULT_PENDING)
    detail = models.TextField(blank=True)

    class Meta:
        unique_together = [("batch", "record")]
        ordering = ["record__nro"]

    def __str__(self):
        return f"{self.batch.batch_code} - {self.record.nro:03d}"
