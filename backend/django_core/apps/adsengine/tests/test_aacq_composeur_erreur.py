"""AACQ72 — Le composeur manuel (``POST /adsengine/actions/``) renvoie la cause
PRÉCISE d'un payload invalide sous ``payload`` (texte d'``ActionPayloadInvalid``),
au format du contrat ``contract_samples/engine_action_erreur.json`` (AACQ60).
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import EngineAction

User = get_user_model()
BASE = '/api/django/adsengine/actions/'
CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'engine_action_erreur.json')


class ComposeurErreurTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AACQ72', slug='aacq72')
        role = Role.objects.create(
            company=self.company, nom='aacq72-role',
            permissions=['adsengine_view', 'adsengine_manage'])
        user = User.objects.create_user(
            username='aacq72-u', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def _post(self, payload):
        return self.api.post(BASE, {
            'kind': 'set_spend_cap', 'reason_fr': 'Plafonner la campagne.',
            'payload': payload}, format='json')

    def test_spend_cap_nul_message_precis(self):
        resp = self._post({'campaign_id': 'c1', 'spend_cap': 0})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            str(resp.data['payload']),
            'le plafond de dépense doit être strictement positif.')
        resp = self._post({'spend_cap': 100})
        self.assertEqual(resp.status_code, 400, resp.data)
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data), set(contrat['exemple']))
        self.assertEqual(str(resp.data['payload']),
                         contrat['exemple']['payload'])
        self.assertFalse(
            EngineAction.objects.filter(company=self.company).exists())

    def test_payload_valide_201(self):
        resp = self._post({'campaign_id': 'c1', 'spend_cap': 5000})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 1)
