"""ACHT73 (C-ACHT-069) — un outil en usage (retour d'outillage, kit,
instrument de recette) ne se supprime pas : 409 en français nommant l'usage,
rien supprimé ; un outil inutilisé se supprime (204).

Rejoue COUT-4 : DELETE 204, ToolReturn 0, avertissement de recette perdu.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.outillage.tests_acht73_outil_en_usage"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    CommissioningRecord, Installation, Intervention, ToolReturn,
)
from apps.outillage.models import KitOutillage, KitOutillageItem, Outillage

User = get_user_model()
URL = '/api/django/outillage/outils'


class OutilEnUsageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT73 O', slug='acht73-o')
        self.admin = User.objects.create_user(
            username='admin-acht73-o', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.megger = Outillage.objects.create(
            company=self.company, nom='Megger')
        self.libre = Outillage.objects.create(
            company=self.company, nom='Marteau')
        kit = KitOutillage.objects.create(company=self.company, nom='Kit')
        KitOutillageItem.objects.create(
            company=self.company, kit=kit, outil=self.megger)
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT73-O')
        iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose')
        ToolReturn.objects.create(
            company=self.company, intervention=iv, outil=self.megger)
        CommissioningRecord.objects.create(
            company=self.company, installation=inst,
            instrument_id=self.megger.id)

    def test_outil_en_usage_409(self):
        r = self.api.delete(f'{URL}/{self.megger.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        detail = str(r.data)
        self.assertIn('1 retour(s) d', detail)
        self.assertIn('1 kit(s)', detail)
        self.assertIn('1 fiche(s) de recette', detail)
        self.assertTrue(Outillage.objects.filter(pk=self.megger.pk).exists())
        self.assertEqual(ToolReturn.objects.count(), 1)

    def test_outil_inutilise_supprime(self):
        r = self.api.delete(f'{URL}/{self.libre.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Outillage.objects.filter(pk=self.libre.pk).exists())
