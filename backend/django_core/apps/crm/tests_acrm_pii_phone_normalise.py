"""ACRM5 — ``phone_normalise`` est une PII du lead : la fiche et la liste ne
rendent plus le numéro normalisé à un rôle sans ``client_pii_voir`` ; un
Commercial complet le voit comme avant.

Test-du-test : retirer ``phone_normalise`` de ``LEAD_PII_FIELDS`` ⇒
test_fiche_masque_phone_normalise et test_liste_masque_phone_normalise
échouent.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

User = get_user_model()
NUMERO = '+212661909901'
CLE = '661909901'


class PiiPhoneNormaliseTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM5 Solaire', slug='acrm5-pii')
        complet = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        sans_pii = Role.objects.create(
            company=self.company, nom='Commercial sans PII',
            permissions=[p for p in COMMERCIAL_PERMISSIONS
                         if p != 'client_pii_voir'])
        self.complet = User.objects.create_user(
            username='acrm5-complet', password='x', company=self.company,
            role=complet)
        self.masque = User.objects.create_user(
            username='acrm5-masque', password='x', company=self.company,
            role=sans_pii)
        self.lead_m = Lead.objects.create(
            company=self.company, nom='Masque', telephone=NUMERO,
            owner=self.masque)
        self.lead_c = Lead.objects.create(
            company=self.company, nom='Complet', telephone=NUMERO,
            owner=self.complet)

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_fiche_masque_phone_normalise(self):
        resp = self._api(self.masque).get(
            f'/api/django/crm/leads/{self.lead_m.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['pii_masked'])
        self.assertIsNone(resp.data['telephone'])
        self.assertIsNone(resp.data['phone_normalise'])
        self.assertNotIn(CLE, json.dumps(resp.data, default=str))

    def test_liste_masque_phone_normalise(self):
        resp = self._api(self.masque).get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        lignes = resp.data.get('results', resp.data)
        self.assertTrue(lignes)
        for ligne in lignes:
            self.assertIsNone(ligne.get('phone_normalise'))
        self.assertNotIn(CLE, json.dumps(resp.data, default=str))

    def test_commercial_complet_inchange(self):
        resp = self._api(self.complet).get(
            f'/api/django/crm/leads/{self.lead_c.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['pii_masked'])
        self.assertEqual(resp.data['phone_normalise'], CLE)
