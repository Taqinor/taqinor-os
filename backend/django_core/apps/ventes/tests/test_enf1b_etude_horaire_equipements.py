# -*- coding: utf-8 -*-
"""ENF1b — POST /ventes/etude-horaire/preview/ : `equipements` non-objet.

api-fuzz du 09/10/2026 : le corps multipart `equipements={}` (une CHAÎNE)
faisait planter `composer_equipements` (`'str' object has no attribute
'get'`) → 500. Un corps inexploitable répond 400 ; un objet reste accepté.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()

URL = '/api/django/ventes/etude-horaire/preview/'

# Corps EXACT du cas 0IhAeU du run 37897343514.
CORPS_FUZZ = {
    'devis': '0', 'lead': '0', 'ville': '0', 'lat': '0', 'lon': '0',
    'facture_hiver': '0', 'facture_ete': '0', 'ete_differente': 'False',
    'occupation': 'presence_jour', 'equipements': '{}', 'raccordement': '0',
    'kwc': '0', 'batterie_kwh': '0', 'dimensionner': 'False', 'critere': '',
}


class EtudeHoraireEquipementsTests(TestCase):
    def setUp(self):
        co = Company.objects.create(nom='ENF1b EH', slug='enf1b-eh')
        user = User.objects.create_user(
            username='enf1b_eh', password='x', role_legacy='responsable',
            company=co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def test_equipements_chaine_multipart_400(self):
        response = self.api.post(URL, CORPS_FUZZ, format='multipart')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('equipements', response.json()['detail'])

    def test_equipements_chaine_json_400(self):
        response = self.api.post(URL, {'equipements': 'piscine'},
                                 format='json')
        self.assertEqual(response.status_code, 400, response.content)

    def test_equipements_objet_accepte(self):
        response = self.api.post(
            URL, {'facture_hiver': 900, 'equipements': {'piscine': True}},
            format='json')
        self.assertEqual(response.status_code, 200, response.content)
