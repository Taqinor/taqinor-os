"""ATOT32 — deux factures de licence ne portent jamais le même numéro.

Numérotation par ``core.numbering.create_with_reference`` (savepoint + nouvel
essai) et contrainte unique ``(company, reference)`` en base (brouillons à
référence vide exclus).
"""
from datetime import date
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser
from core import numbering

from ..models import FactureLicence

URL = '/api/django/adminops/facturation-licences/'


class LicUniqueTests(TestCase):
    def setUp(self):
        self.tenant = Company.objects.create(nom='Tenant LIC', slug='atot-lic')
        self.fondateur = CustomUser.objects.create_superuser(
            username='atot32_fondateur', password='x', email='f@atot32.ma')
        self.api = APIClient()
        self.api.force_authenticate(self.fondateur)

    def _emettre(self):
        resp = self.api.post(URL, {'company': self.tenant.pk,
                                   'periode': '2026-10', 'statut': 'emise'},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['reference']

    def test_deux_emissions_meme_mois_references_distinctes(self):
        r1, r2 = self._emettre(), self._emettre()
        self.assertNotEqual(r1, r2)
        self.assertTrue(r1.endswith('-0001'), r1)
        self.assertTrue(r2.endswith('-0002'), r2)
        refs = list(FactureLicence.objects.filter(company=self.tenant)
                    .values_list('reference', flat=True))
        self.assertEqual(len(refs), len(set(refs)))

    def test_creation_concurrente_simulee(self):
        """Une émission concurrente a pris le numéro calculé : la contrainte
        refuse le doublon et ``create_with_reference`` réessaie."""
        premiere = self._emettre()
        reel = numbering.next_reference
        appels = []

        def course(*args, **kwargs):
            appels.append(1)
            if len(appels) == 1:
                return premiere  # numéro déjà pris par l'émission concurrente
            return reel(*args, **kwargs)

        with mock.patch.object(numbering, 'next_reference', side_effect=course):
            seconde = self._emettre()
        self.assertNotEqual(seconde, premiere)
        self.assertGreaterEqual(len(appels), 2)

    def test_doublon_direct_leve_integrity_error(self):
        FactureLicence.objects.create(
            company=self.tenant, periode=date(2026, 10, 1),
            reference='LIC-202610-0007')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FactureLicence.objects.create(
                    company=self.tenant, periode=date(2026, 10, 1),
                    reference='LIC-202610-0007')

    def test_brouillons_sans_reference_multiples(self):
        for _ in range(2):
            FactureLicence.objects.create(
                company=self.tenant, periode=date(2026, 10, 1), reference='')
        self.assertEqual(
            FactureLicence.objects.filter(reference='').count(), 2)
