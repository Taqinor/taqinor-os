"""AACQ15 — Puissance kWc de l'import photo-chantier telle que l'écran l'envoie.

L'écran poste du JSON à valeurs CHAÎNE (« 6 », « 6,5 ») : le serveur les lit
(virgule décimale comprise), porte le chiffre SAISI sur l'accroche au format
français, et refuse une valeur illisible en 400 sous ``puissance_kwc`` —
jamais une 500. La photo/ville du chantier passent par
``installations.selectors`` (simulés ici, comme ``test_chantier_import``).
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import ConsentRecord, CreativeAsset

User = get_user_model()
URL = '/api/django/adsengine/creatifs/import-chantier/'


class _FakeAttachment:
    file_key = 'chantier/7/photo.jpg'


class ImportPuissanceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Kwc', slug='aacq15-kwc')
        role = Role.objects.create(
            company=self.company, nom='aacq15-role',
            permissions=['adsengine_view', 'adsengine_manage'])
        user = User.objects.create_user(
            username='aacq15-com', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        ConsentRecord.objects.create(
            company=self.company, client_id=42, client_nom='Client',
            portee_photo=True, date_consentement=datetime.date(2026, 1, 1))

    def _post(self, puissance):
        body = {'chantier_id': 7, 'attachment_id': 99, 'client_id': 42,
                'puissance_kwc': puissance, 'ville': ''}
        with mock.patch('apps.installations.selectors.chantier_photo',
                        return_value=_FakeAttachment()), \
                mock.patch('apps.installations.selectors.chantier_ville',
                           return_value=None):
            return self.api.post(URL, body, format='json')

    def _hook(self, resp):
        self.assertEqual(resp.status_code, 201, resp.data)
        return CreativeAsset.objects.get(pk=resp.data['asset_id']).hook_text

    def test_chaine_entiere(self):
        self.assertEqual(self._hook(self._post('6')), 'Chantier — 6 kWc')

    def test_virgule_decimale(self):
        self.assertEqual(self._hook(self._post('6,5')), 'Chantier — 6,5 kWc')

    def test_nombre(self):
        self.assertEqual(self._hook(self._post(6)), 'Chantier — 6 kWc')

    def test_vide_sans_puissance(self):
        self.assertEqual(self._hook(self._post('')), 'Chantier')

    def test_illisible_400_sous_le_champ(self):
        for valeur in ('abc', '-3', 'inf'):
            with self.subTest(valeur=valeur):
                resp = self._post(valeur)
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn('puissance_kwc', resp.data)
                self.assertIn('Puissance illisible',
                              str(resp.data['puissance_kwc']))
        self.assertEqual(CreativeAsset.objects.count(), 0)
