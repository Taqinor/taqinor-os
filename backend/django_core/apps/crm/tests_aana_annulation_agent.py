"""AANA49 — l'annulation d'une création de client par l'agent ne supprime
JAMAIS un client préexistant.

C-AANA-008 : un journal ``crm.client.create`` dont ``object_id`` désignait un
client créé AVANT lui (journal forgé, ou client réutilisé) faisait supprimer
ce client par l'annulation d'un admin (sonde du 05/10 : 200, client supprimé).
Désormais le gestionnaire n'annule que si le client a été créé PAR CE journal :
créateur = ``log.user`` et créé au plus tôt 5 s avant ``log.confirmed_at``.
Sinon 409 « ce client n'a pas été créé par l'agent » et le client reste.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.agent import services as agent_services
from apps.agent.models import AgentActionLog
from apps.crm.models import Client

User = get_user_model()


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _url(log):
    return f'/api/django/agent/logs/{log.pk}/annuler/'


class AnnulationCreationClientAgentTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AANA49 Co')
        cls.admin = User.objects.create_user(
            username='aana49_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.agent_user = User.objects.create_user(
            username='aana49_agent', password='x', company=cls.company)
        cls.autre = User.objects.create_user(
            username='aana49_autre', password='x', company=cls.company)

    def _journal(self, client_obj, user=None):
        return agent_services.log_confirmed_action(
            company=self.company,
            user=self.agent_user if user is None else user,
            action_key='crm.client.create',
            risk_level=AgentActionLog.RiskLevel.OUTWARD,
            resulted_object=client_obj)

    def _vieillir(self, client_obj, jours=30):
        Client.objects.filter(pk=client_obj.pk).update(
            date_creation=client_obj.date_creation - timedelta(days=jours))

    def test_client_preexistant_jamais_supprime(self):
        client_obj = Client.objects.create(
            company=self.company, nom='Préexistant', created_by=self.autre)
        self._vieillir(client_obj)
        log = self._journal(client_obj)

        resp = _api(self.admin).post(_url(log))

        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertIn("n'a pas été créé par l'agent", resp.json()['detail'])
        self.assertTrue(Client.objects.filter(pk=client_obj.pk).exists())
        log.refresh_from_db()
        self.assertIsNone(log.undone_at)

    def test_client_du_meme_utilisateur_mais_anterieur_refuse(self):
        client_obj = Client.objects.create(
            company=self.company, nom='Ancien', created_by=self.agent_user)
        self._vieillir(client_obj, jours=1)
        log = self._journal(client_obj)

        resp = _api(self.admin).post(_url(log))

        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertTrue(Client.objects.filter(pk=client_obj.pk).exists())

    def test_client_cree_par_un_autre_utilisateur_refuse(self):
        client_obj = Client.objects.create(
            company=self.company, nom='Autre créateur', created_by=self.autre)
        log = self._journal(client_obj)

        resp = _api(self.admin).post(_url(log))

        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertTrue(Client.objects.filter(pk=client_obj.pk).exists())

    def test_journal_sans_utilisateur_refuse(self):
        client_obj = Client.objects.create(
            company=self.company, nom='Sans auteur', created_by=None)
        log = agent_services.log_confirmed_action(
            company=self.company, user=None,
            action_key='crm.client.create',
            risk_level=AgentActionLog.RiskLevel.OUTWARD,
            resulted_object=client_obj)

        resp = _api(self.admin).post(_url(log))

        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertTrue(Client.objects.filter(pk=client_obj.pk).exists())

    def test_client_cree_par_ce_journal_est_supprime(self):
        client_obj = Client.objects.create(
            company=self.company, nom='Créé par l’agent',
            created_by=self.agent_user)
        log = self._journal(client_obj)

        resp = _api(self.admin).post(_url(log))

        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(Client.objects.filter(pk=client_obj.pk).exists())
        log.refresh_from_db()
        self.assertIsNotNone(log.undone_at)
