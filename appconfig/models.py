from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CareerConfig(TimeStampedModel):
    carrera_excel = models.CharField(max_length=255)
    carrera_norm = models.CharField(max_length=255, unique=True)
    facultad = models.CharField(max_length=255, blank=True)
    handle = models.CharField(max_length=255)
    thesis_degree_name = models.CharField(max_length=255, blank=True)
    thesis_degree_discipline = models.CharField(max_length=255, blank=True)
    thesis_degree_grantor = models.CharField(max_length=500, blank=True)
    renati_level = models.CharField(max_length=255, blank=True)
    renati_discipline = models.CharField(max_length=255, blank=True)
    ocde_url = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["carrera_excel"]

    def __str__(self):
        return f"{self.carrera_excel} ({self.handle})"


class LicenseVersion(TimeStampedModel):
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=64)
    text_content = models.TextField()
    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_licenses",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-is_active", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_license",
            ),
        ]

    def clean(self):
        if not self.text_content.strip():
            raise ValidationError("La licencia no puede estar vacía.")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_active:
                LicenseVersion.objects.exclude(pk=self.pk).filter(is_active=True).update(is_active=False)
            super().save(*args, **kwargs)

    def __str__(self):
        status = "Activa" if self.is_active else "Inactiva"
        return f"{self.name} v{self.version} [{status}]"


class SystemConfig(TimeStampedModel):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=1000)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key
