"""NTCPQ9 — configurateur guidé : démarrer / répondre / résultat via NTCPQ2."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import (
    QuestionConfigurateur, RegleProduitCPQ, SessionConfigurateur,
    ReponseConfigurateur,
)
from apps.cpq import selectors
from testkit.factories import CompanyFactory, UserFactory


def _auth(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class TestConfigurateur(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.q_toiture = QuestionConfigurateur.objects.create(
            company=self.company, ordre=1, texte='Type de toiture',
            type=QuestionConfigurateur.TypeQuestion.CHOIX_UNIQUE,
            options={'champ': 'toiture', 'choices': ['inclinee', 'plate']})
        self.q_kwc = QuestionConfigurateur.objects.create(
            company=self.company, ordre=2, texte='Puissance (kWc)',
            type=QuestionConfigurateur.TypeQuestion.NUMERIQUE,
            options={'champ': 'kwc'})
        RegleProduitCPQ.objects.create(
            company=self.company, nom='Toiture inclinée 9kWc',
            condition_group={'op': 'and', 'conditions': [
                {'field': 'toiture', 'operator': 'eq', 'value': 'inclinee'},
                {'field': 'kwc', 'operator': 'gte', 'value': 9},
            ]},
            actions=[{'type': 'proposer_kit', 'valeur': 'kit_9kwc_incline'}])

    def test_flux_complet(self):
        client = _auth(self.user)
        # démarrer
        resp = client.post('/api/django/cpq/configurateur/demarrer/')
        self.assertEqual(resp.status_code, 201)
        token = resp.json()['session']
        self.assertEqual(len(resp.json()['questions']), 2)
        # répondre
        client.post(
            f'/api/django/cpq/configurateur/{token}/repondre/',
            {'reponses': [
                {'question': self.q_toiture.id, 'valeur': 'inclinee'},
                {'question': self.q_kwc.id, 'valeur': 9},
            ]}, format='json')
        # résultat
        r = client.get(f'/api/django/cpq/configurateur/{token}/resultat/')
        self.assertEqual(r.status_code, 200)
        actions = r.json()['actions_declenchees']
        self.assertEqual(len(actions), 1)
        self.assertEqual(
            actions[0]['actions'],
            [{'type': 'proposer_kit', 'valeur': 'kit_9kwc_incline'}])

    def test_resoudre_selector(self):
        session = SessionConfigurateur.objects.create(company=self.company)
        ReponseConfigurateur.objects.create(
            session=session, question=self.q_toiture, valeur='inclinee')
        ReponseConfigurateur.objects.create(
            session=session, question=self.q_kwc, valeur=12)
        result = selectors.resoudre_configurateur(session)
        self.assertEqual(result['context'], {'toiture': 'inclinee', 'kwc': 12})
        self.assertEqual(len(result['actions_declenchees']), 1)
