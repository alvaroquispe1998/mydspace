from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from registry.forms import ThesisRecordForm
from registry.models import AuditEvent, SustentationGroup, ThesisRecord


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

    def test_auditor_can_edit_only_in_borrador_or_observado(self):
        auditor = User.objects.create(username="aud1", role=User.ROLE_AUDITOR)
        g = SustentationGroup.objects.create(date="2026-02-13", name="SUSTENTACIÓN 13.02.2026")
        r = ThesisRecord.objects.create(group=g, status=ThesisRecord.STATUS_BORRADOR)
        self.assertTrue(r.can_edit(auditor))

        r.status = ThesisRecord.STATUS_OBSERVADO
        self.assertTrue(r.can_edit(auditor))

        r.status = ThesisRecord.STATUS_EN_AUDITORIA
        self.assertFalse(r.can_edit(auditor))

        r.status = ThesisRecord.STATUS_APROBADO
        self.assertFalse(r.can_edit(auditor))

        r.status = ThesisRecord.STATUS_POR_PUBLICAR
        self.assertFalse(r.can_edit(auditor))

        r.status = ThesisRecord.STATUS_PUBLICADO
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


class GroupBulkAuditTests(TestCase):
    def setUp(self):
        self.group = SustentationGroup.objects.create(date="2026-02-14", name="SUSTENTACION 14.02.2026")
        self.r1 = ThesisRecord.objects.create(group=self.group, status=ThesisRecord.STATUS_EN_AUDITORIA)
        self.r2 = ThesisRecord.objects.create(group=self.group, status=ThesisRecord.STATUS_EN_AUDITORIA)
        self.r3 = ThesisRecord.objects.create(group=self.group, status=ThesisRecord.STATUS_BORRADOR)
        self.url = reverse("registry:groups_audit_bulk", args=[self.group.id])

    def test_superuser_can_bulk_observe_selected_records(self):
        admin = User.objects.create_user(
            username="admin",
            password="secret123",
            is_superuser=True,
            is_staff=True,
        )
        self.client.login(username="admin", password="secret123")
        response = self.client.post(
            self.url,
            {
                "bulk_action": "observe",
                "record_ids": [str(self.r1.id), str(self.r2.id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.r1.refresh_from_db()
        self.r2.refresh_from_db()
        self.assertEqual(self.r1.status, ThesisRecord.STATUS_OBSERVADO)
        self.assertEqual(self.r2.status, ThesisRecord.STATUS_OBSERVADO)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.ACTION_OBSERVE).count(), 2)

    def test_bulk_observe_skips_records_not_in_auditoria(self):
        auditor = User.objects.create_user(username="auditor", password="secret123", role=User.ROLE_AUDITOR)
        self.client.login(username="auditor", password="secret123")
        response = self.client.post(
            self.url,
            {
                "bulk_action": "observe",
                "record_ids": [str(self.r1.id), str(self.r3.id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.r1.refresh_from_db()
        self.r3.refresh_from_db()
        self.assertEqual(self.r1.status, ThesisRecord.STATUS_OBSERVADO)
        self.assertEqual(self.r3.status, ThesisRecord.STATUS_BORRADOR)
