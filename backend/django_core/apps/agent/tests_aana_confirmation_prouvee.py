"""AANA18 (C-AANA-008) — ``POST /api/django/agent/logs/confirmer/`` n'accepte
QUE la confirmation d'une proposition réellement émise par l'agent.

Sonde du 05/10 : un utilisateur SANS ``crm_creer`` postait
``{action_key: 'crm.client.create', object_id: <client existant>}`` → 201, puis
l'annulation du journal par un admin SUPPRIMAIT le client préexistant.
Désormais : action présente dans ``registry.for_user(user)`` au même niveau de
risque (permission requise détenue) ET preuve HMAC (secret partagé
``AGENT_HMAC_SECRET``) couvrant action + entrées + objet + utilisateur +
société de la requête ; sinon 403 et AUCUN journal. Le format de la preuve est
le contrat ``contract_samples/logs_confirmer.json``, chargé ici ET par
``backend/fastapi_ia/tests/test_action_tools.py`` (C-AANA-032).
"""
import json
import os
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.agent import services
from apps.agent.models import AgentActionLog
from apps.crm.models import Client
from apps.roles.models import Role

User = get_user_model()

URL = '/api/django/agent/logs/confirmer/'
SECRET = 'secret-partage-de-test-aana18'
CONTRAT = Path(__file__).resolve().parent / 'contract_samples' / \
    'logs_confirmer.json'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _preuve(user, *, action_key='crm.client.create', inputs=None,
            object_id=None, company=None, secret=SECRET):
    return services.calculer_preuve_confirmation(
        secret=secret, action_key=action_key,
        company_id=(company or user.company).pk, user_id=user.pk,
        inputs=inputs or {}, object_id=object_id)


@override_settings(AGENT_HMAC_SECRET=SECRET)
class ConfirmationProuveeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AANA18 Co')
        cls.lecteur = User.objects.create_user(
            username='aana18_lecteur', password='x', company=cls.company,
            role=Role.objects.create(
                company=cls.company, nom='Lecture', permissions=['crm_voir']))
        cls.createur = User.objects.create_user(
            username='aana18_createur', password='x', company=cls.company,
            role=Role.objects.create(
                company=cls.company, nom='Commercial',
                permissions=['crm_voir', 'crm_creer']))
        cls.client_existant = Client.objects.create(
            company=cls.company, nom='Client préexistant')

    def _corps(self, **extra):
        corps = {
            'action_key': 'crm.client.create', 'risk_level': 'outward',
            'inputs': {'nom': 'Client Confirmé'},
            'object_id': self.client_existant.id,
        }
        corps.update(extra)
        return corps

    def test_journal_forge_refuse(self):
        """Le scénario de la sonde : sans crm_creer, sans preuve → 403, aucun
        journal (donc plus rien à « annuler » sur le client préexistant)."""
        resp = _api(self.lecteur).post(URL, self._corps(), format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(AgentActionLog.objects.count(), 0)
        # Même avec une preuve VALIDE pour lui : l'action n'est pas dans son
        # catalogue (permission crm_creer absente) → 403.
        corps = self._corps(preuve=_preuve(
            self.lecteur, inputs={'nom': 'Client Confirmé'},
            object_id=self.client_existant.id))
        resp = _api(self.lecteur).post(URL, corps, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(AgentActionLog.objects.count(), 0)

    def test_preuve_absente_ou_fausse_refusee_meme_avec_permission(self):
        for preuve in (None, '', 'abc123', 'f' * 64):
            with self.subTest(preuve=preuve):
                corps = self._corps()
                if preuve is not None:
                    corps['preuve'] = preuve
                resp = _api(self.createur).post(URL, corps, format='json')
                self.assertEqual(resp.status_code, 403)
        self.assertEqual(AgentActionLog.objects.count(), 0)

    def test_preuve_valide_pour_cet_utilisateur_201(self):
        preuve = _preuve(self.createur, inputs={'nom': 'Client Confirmé'},
                         object_id=self.client_existant.id)
        resp = _api(self.createur).post(
            URL, self._corps(preuve=preuve), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        log = AgentActionLog.objects.get(pk=resp.data['id'])
        self.assertEqual(log.user_id, self.createur.id)
        self.assertEqual(log.company_id, self.company.id)
        # L'empreinte journalisée est la preuve HMAC, jamais un jeton brut.
        self.assertEqual(log.proposal_hash, preuve)
        self.assertEqual(log.object_id, str(self.client_existant.id))

    def test_preuve_d_un_autre_utilisateur_refusee(self):
        autre = User.objects.create_user(
            username='aana18_autre', password='x', company=self.company,
            role=self.createur.role)
        preuve = _preuve(autre, inputs={'nom': 'Client Confirmé'},
                         object_id=self.client_existant.id)
        resp = _api(self.createur).post(
            URL, self._corps(preuve=preuve), format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(AgentActionLog.objects.count(), 0)

    def test_preuve_ne_couvre_pas_un_autre_objet(self):
        """Une preuve émise pour l'objet 42 ne vaut pas pour un autre id."""
        preuve = _preuve(self.createur, inputs={'nom': 'Client Confirmé'},
                         object_id=999999)
        resp = _api(self.createur).post(
            URL, self._corps(preuve=preuve), format='json')
        self.assertEqual(resp.status_code, 403)

    def test_risque_falsifie_refuse(self):
        preuve = _preuve(self.createur, inputs={'nom': 'Client Confirmé'},
                         object_id=self.client_existant.id)
        resp = _api(self.createur).post(
            URL, self._corps(preuve=preuve, risk_level='internal'),
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_sans_secret_configure_refuse(self):
        """Fail-closed : sans AGENT_HMAC_SECRET (ni réglage ni variable
        d'environnement), même une « preuve » signée par une clé vide est
        refusée."""
        preuve = _preuve(self.createur, inputs={'nom': 'Client Confirmé'},
                         object_id=self.client_existant.id, secret='')
        with self.settings(AGENT_HMAC_SECRET=''), \
                mock.patch.dict(os.environ, {'AGENT_HMAC_SECRET': ''}):
            resp = _api(self.createur).post(
                URL, self._corps(preuve=preuve), format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(AgentActionLog.objects.count(), 0)


class ContratPreuveTests(TestCase):
    """C-AANA-032 — le contrat partagé est CHARGÉ et son vecteur vérifié."""

    def test_vecteur_du_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        vecteur = contrat['preuve']['vecteur_de_test']
        champs = vecteur['champs']
        self.assertEqual(
            services.message_preuve_confirmation(**champs),
            vecteur['message'])
        self.assertEqual(
            services.calculer_preuve_confirmation(
                secret=vecteur['secret'], **champs),
            vecteur['preuve'])
        self.assertEqual(contrat['exemple_corps']['preuve'], vecteur['preuve'])
        self.assertEqual(contrat.get('forme_serveur'), 'complete')
