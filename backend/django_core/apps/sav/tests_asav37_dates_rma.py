"""ASAV37 — `date_envoi_fournisseur` et `date_resolution` d'une réclamation
garantie sont posées par le serveur à la transition de statut (lecture seule).

Run :
    python manage.py test apps.sav.tests_asav37_dates_rma -v2
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.sav.models import Equipement, WarrantyClaim
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/sav/warranty-claims'


class DatesRmaTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav37-co', defaults={'nom': 'ASAV37 Co'})
        self.user = User.objects.create_user(
            username='asav37_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASAV37',
            prix_achat=0, prix_vente=100)
        self.equip = Equipement.objects.create(
            company=self.company, produit=produit)

    def _claim(self, **kw):
        return WarrantyClaim.objects.create(
            company=self.company, equipement=self.equip, created_by=self.user,
            **kw)

    def _patch(self, claim, corps):
        r = self.api.patch(f'{BASE}/{claim.pk}/', corps, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        claim.refresh_from_db()
        return claim

    def test_edition_garde_date_resolution(self):
        claim = self._claim(statut='resolu', date_resolution=date(2026, 9, 1))
        self._patch(claim, {'statut': 'resolu', 'rma_ref': 'RMA-2',
                            'date_resolution': '2026-10-08'})
        self.assertEqual(claim.date_resolution, date(2026, 9, 1))
        self.assertEqual(claim.rma_ref, 'RMA-2')

    def test_envoi_pose_date(self):
        claim = self._claim(statut='ouvert')
        self._patch(claim, {'statut': 'envoye'})
        self.assertEqual(claim.date_envoi_fournisseur, timezone.localdate())
        self.assertIsNone(claim.date_resolution)
        self._patch(claim, {'statut': 'refuse'})
        self.assertEqual(claim.date_resolution, timezone.localdate())

    def test_dates_lecture_seule(self):
        claim = self._claim(statut='ouvert')
        self._patch(claim, {'rma_ref': 'X', 'date_envoi_fournisseur':
                            '2020-01-01', 'date_resolution': '2020-01-02'})
        self.assertIsNone(claim.date_envoi_fournisseur)
        self.assertIsNone(claim.date_resolution)
