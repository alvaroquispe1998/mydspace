from django.contrib.auth import get_user_model
from django.test import TestCase

from registry.forms import ThesisRecordForm
from registry.models import SustentationGroup, ThesisRecord


User = get_user_model()


class ThesisRecordValidationTests(TestCase):
    def test_can_edit_only_in_borrador_or_observado(self):
        u = User.objects.create(username="u1")
        g = SustentationGroup.objects.create(date="2026-02-13", name="SUSTENTACIÓN 13.02.2026")

        r = ThesisRecord.objects.create(group=g, status=ThesisRecord.STATUS_BORRADOR)
        self.assertTrue(r.can_edit(u))

        r.status = ThesisRecord.STATUS_OBSERVADO
        self.assertTrue(r.can_edit(u))

        r.status = ThesisRecord.STATUS_EN_AUDITORIA
        self.assertFalse(r.can_edit(u))

        r.status = ThesisRecord.STATUS_APROBADO
        self.assertFalse(r.can_edit(u))

        r.status = ThesisRecord.STATUS_POR_PUBLICAR
        self.assertFalse(r.can_edit(u))

    def test_auditor_cannot_edit_in_any_status(self):
        auditor = User.objects.create(username="aud1", role=User.ROLE_AUDITOR)
        g = SustentationGroup.objects.create(date="2026-02-13", name="SUSTENTACIÓN 13.02.2026")
        for st in [
            ThesisRecord.STATUS_BORRADOR,
            ThesisRecord.STATUS_OBSERVADO,
            ThesisRecord.STATUS_EN_AUDITORIA,
            ThesisRecord.STATUS_APROBADO,
            ThesisRecord.STATUS_POR_PUBLICAR,
            ThesisRecord.STATUS_PUBLICADO,
        ]:
            r = ThesisRecord.objects.create(group=g, status=st)
            self.assertFalse(r.can_edit(auditor))

    def test_dni_digits_only(self):
        form = ThesisRecordForm(
            data={
                "titulo": "X",
                "autor1_nombre": "APELLIDO, NOMBRE",
                "autor1_dni": "12A34567",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("autor1_dni", form.errors)
