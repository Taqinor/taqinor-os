"""ACHT44 (C-ACHT-043) — `CommissioningRecord.instrument_id` borné à la
société : écriture d'un outil étranger/inexistant refusée (400) et lecture
d'une donnée héritée sans fuite du nom ni du n° de série d'un autre locataire.

Rejoue CREC-1 : PATCH instrument_id étranger -> 200 + nom/n° de série de B.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht44_instrument_recette_tenant"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import CommissioningRecord, Installation
from apps.outillage.models import Outillage

User = get_user_model()
URL = '/api/django/installations/recettes-commissioning'


class InstrumentRecetteTenantTests(TestCase):
    def setUp(self):
        self.co_a, _ = Company.objects.get_or_create(
            slug='co-acht44a', defaults={'nom': 'Co ACHT44 A'})
        self.co_b, _ = Company.objects.get_or_create(
            slug='co-acht44b', defaults={'nom': 'Co ACHT44 B'})
        self.admin = User.objects.create_user(
            username='admin-acht44', password='x', company=self.co_a,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.outil_b = Outillage.objects.create(
            company=self.co_b, nom='Multimètre SECRET co2',
            numero_serie='SN-OTHER-TENANT')
        self.outil_a = Outillage.objects.create(
            company=self.co_a, nom='Multimètre A', numero_serie='SN-A')
        inst = Installation.objects.create(
            company=self.co_a, reference='CH-ACHT44')
        self.fiche = CommissioningRecord.objects.create(
            company=self.co_a, installation=inst)

    def test_patch_instrument_etranger_400(self):
        for valeur in (self.outil_b.id, 999999):
            r = self.api.patch(f'{URL}/{self.fiche.id}/',
                               {'instrument_id': valeur}, format='json')
            self.assertEqual(r.status_code, 400, r.data)
            self.assertIn('instrument_id', r.data)
        self.fiche.refresh_from_db()
        self.assertIsNone(self.fiche.instrument_id)
        r = self.api.patch(f'{URL}/{self.fiche.id}/',
                           {'instrument_id': self.outil_a.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['instrument_nom'], 'Multimètre A')

    def test_lecture_instrument_heritee_bornee(self):
        CommissioningRecord.objects.filter(pk=self.fiche.pk).update(
            instrument_id=self.outil_b.id)
        r = self.api.get(f'{URL}/{self.fiche.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['instrument_nom'])
        self.assertIsNone(r.data['instrument_numero_serie'])
        self.assertNotIn('SECRET', str(r.data))
        self.assertNotIn('SN-OTHER-TENANT', str(r.data))
