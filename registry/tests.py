from django.contrib.auth import get_user_model
from django.test import TestCase

from registry.forms import ThesisRecordForm
from registry.models import ThesisRecord


User = get_user_model()


class ThesisRecordValidationTests(TestCase):
    def test_can_edit_only_in_borrador_or_observado(self):
        u = User.objects.create(username="u1")

        r = ThesisRecord.objects.create(status=ThesisRecord.STATUS_BORRADOR)
        self.assertTrue(r.can_edit(u))

        r.status = ThesisRecord.STATUS_OBSERVADO
        self.assertTrue(r.can_edit(u))

        r.status = ThesisRecord.STATUS_EN_AUDITORIA
        self.assertFalse(r.can_edit(u))

        r.status = ThesisRecord.STATUS_APROBADO
        self.assertFalse(r.can_edit(u))

        r.status = ThesisRecord.STATUS_INCLUIDO_EN_LOTE
        self.assertFalse(r.can_edit(u))

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
