"""NTMAR29 — Étend FG225 : réutilisation des pièces administratives.

Critère : ouvrir un dossier de soumission pré-remplit les pièces disponibles
à partir des attestations valides du tenant — ici, la SOURCE réutilisable
exposée par ``apps.fiscal`` (le pré-remplissage ``apps.ao`` lui-même est hors
périmètre de ce lot, voir selectors.py)."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.fiscal.models import AttestationTenant
from apps.fiscal.selectors import pieces_reutilisables_attestations

from ._fixtures import make_company


class PiecesReutilisablesTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-pieces', 'Fiscal Pieces')

    def test_valid_attestation_is_available(self):
        today = timezone.localdate()
        AttestationTenant.objects.create(
            company=self.company,
            type_attestation=AttestationTenant.Type.FISCALE_REGULARITE,
            numero='ATT-100', date_expiration=today + timedelta(days=60),
            fichier_key='fiscal/1/attestation.pdf')
        pieces = pieces_reutilisables_attestations(self.company, today=today)
        self.assertIn(
            AttestationTenant.Type.FISCALE_REGULARITE, pieces)
        self.assertEqual(
            pieces[AttestationTenant.Type.FISCALE_REGULARITE]['numero'],
            'ATT-100')

    def test_expired_attestation_is_not_available(self):
        today = timezone.localdate()
        AttestationTenant.objects.create(
            company=self.company,
            type_attestation=AttestationTenant.Type.RC,
            numero='ATT-101', date_expiration=today - timedelta(days=1))
        pieces = pieces_reutilisables_attestations(self.company, today=today)
        self.assertNotIn(AttestationTenant.Type.RC, pieces)

    def test_no_expiration_date_is_always_available(self):
        AttestationTenant.objects.create(
            company=self.company,
            type_attestation=AttestationTenant.Type.AGREMENT,
            numero='ATT-102', date_expiration=None)
        pieces = pieces_reutilisables_attestations(self.company)
        self.assertIn(AttestationTenant.Type.AGREMENT, pieces)
