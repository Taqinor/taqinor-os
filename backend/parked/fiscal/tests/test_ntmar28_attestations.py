"""NTMAR28 — Attestations fiscales & sociales du tenant avec expirations.

Critère : une attestation fiscale expirant dans 30 j apparaît dans la liste
des expirantes."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.fiscal.models import AttestationTenant
from apps.fiscal.selectors import attestations_expirantes

from ._fixtures import make_company


class AttestationsExpirantesTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-att', 'Fiscal Att')

    def test_expiring_within_30_days_is_listed(self):
        today = timezone.localdate()
        att = AttestationTenant.objects.create(
            company=self.company,
            type_attestation=AttestationTenant.Type.FISCALE_REGULARITE,
            numero='ATT-001', date_expiration=today + timedelta(days=20))
        qs = attestations_expirantes(self.company, within=30, today=today)
        self.assertIn(att, list(qs))

    def test_far_future_expiration_not_listed(self):
        today = timezone.localdate()
        AttestationTenant.objects.create(
            company=self.company,
            type_attestation=AttestationTenant.Type.SOCIALE_CNSS,
            numero='ATT-002', date_expiration=today + timedelta(days=365))
        qs = attestations_expirantes(self.company, within=30, today=today)
        self.assertEqual(list(qs), [])

    def test_already_expired_not_in_expiring_list(self):
        today = timezone.localdate()
        AttestationTenant.objects.create(
            company=self.company,
            type_attestation=AttestationTenant.Type.RC,
            numero='ATT-003', date_expiration=today - timedelta(days=5))
        qs = attestations_expirantes(self.company, within=30, today=today)
        self.assertEqual(list(qs), [])
