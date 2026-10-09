"""ACHT48 (C-ACHT-047) — corriger la `date_reception` d'un chantier déjà
réceptionné recale le parc SAV (même transaction) et le trace au chatter ;
notes seules ou chantier non réceptionné : aucun recalage.

Rejoue CREC-5.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht48_recalage_garanties"
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import Installation, InstallationActivity
from apps.sav.models import Equipement
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/installations/chantiers'
RECEPTION = date(2026, 10, 8)
CORRIGEE = date(2026, 1, 15)


class RecalageGarantiesTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht48', defaults={'nom': 'Co ACHT48'})
        self.admin = User.objects.create_user(
            username='admin-acht48', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ACHT48', sku='PAN-48',
            prix_achat=0, prix_vente=10, garantie_mois=144)
        self.recep = Installation.objects.create(
            company=self.company, reference='CH-48-R',
            date_reception=RECEPTION)
        self.eq = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.recep, numero_serie='SN-48', date_pose=RECEPTION)
        self.eq.recompute_garanties()
        self.eq.save()
        self.non_recep = Installation.objects.create(
            company=self.company, reference='CH-48-N')

    def _patch(self, inst, corps):
        return self.api.patch(f'{BASE}/{inst.id}/', corps, format='json')

    def test_recalage_equipement_et_chatter(self):
        r = self._patch(self.recep, {'date_reception': str(CORRIGEE)})
        self.assertEqual(r.status_code, 200, r.data)
        self.eq.refresh_from_db()
        self.assertEqual(self.eq.date_pose, CORRIGEE)
        self.assertEqual(self.eq.date_fin_garantie.year, 2038)
        self.assertEqual(self.eq.date_fin_garantie.month, 1)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.recep, body__startswith='Garanties du parc '
            'recalées : 1 équipement(s)').exists())

    def test_notes_seules_aucun_recalage(self):
        r = self._patch(self.recep, {'notes': 'rien à voir'})
        self.assertEqual(r.status_code, 200, r.data)
        self.eq.refresh_from_db()
        self.assertEqual(self.eq.date_pose, RECEPTION)
        self.assertFalse(InstallationActivity.objects.filter(
            installation=self.recep,
            body__startswith='Garanties du parc').exists())

    def test_non_receptionne_aucun_recalage(self):
        r = self._patch(self.non_recep, {'date_reception': str(CORRIGEE)})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(InstallationActivity.objects.filter(
            installation=self.non_recep,
            body__startswith='Garanties du parc').exists())
        self.eq.refresh_from_db()
        self.assertEqual(self.eq.date_pose, RECEPTION)
