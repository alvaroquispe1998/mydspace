from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CARGADOR = "cargador"
    ROLE_ASESOR = "asesor"
    ROLE_AUDITOR = "auditor"
    ROLE_CHOICES = [
        (ROLE_CARGADOR, "Cargador"),
        (ROLE_ASESOR, "Asesor"),
        (ROLE_AUDITOR, "Auditor"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CARGADOR)

    @property
    def is_auditor(self) -> bool:
        return self.role == self.ROLE_AUDITOR

# Create your models here.
