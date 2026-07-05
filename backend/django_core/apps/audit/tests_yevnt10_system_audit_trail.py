"""Tests YEVNT10 — une bascule de devis par le cron `expire_stale_devis`
(hors requête HTTP) laisse une trace d'audit attribuée « système » (user=None)
nommant le job."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.audit.models import AuditLog
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.services import expire_stale_devis


def make_company(slug='yevnt10-co', nom='YEVNT10 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestExpireStaleDevisAuditTrail(TestCase):
    def setUp(self):
        self.company = make_company()
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='E10',
            email='yevnt10@example.com', telephone='+212600000013')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-YEVNT10-0001',
            client=self.cl, statut=Devis.Statut.ENVOYE,
            date_validite=date.today() - timedelta(days=1),
            taux_tva=Decimal('20'))

    def test_expiration_leaves_system_attributed_audit_entry(self):
        # No request context at all (direct call, like a cron/beat job).
        expire_stale_devis()
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Devis)
        entries = AuditLog.objects.filter(
            content_type=ct, object_id=str(self.devis.id),
            action=AuditLog.Action.STATUS)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertIsNone(entry.user)
        self.assertIn('expire_stale_devis', entry.detail)
        self.assertEqual(entry.company_id, self.company.id)

    def test_devis_not_expired_leaves_no_new_audit_entry(self):
        Devis.objects.filter(pk=self.devis.pk).update(
            date_validite=date.today() + timedelta(days=30))
        expire_stale_devis()
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Devis)
        entries = AuditLog.objects.filter(
            content_type=ct, object_id=str(self.devis.id),
            action=AuditLog.Action.STATUS)
        self.assertEqual(entries.count(), 0)
