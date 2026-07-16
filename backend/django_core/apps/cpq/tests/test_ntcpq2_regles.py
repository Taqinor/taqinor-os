"""NTCPQ2 — RegleProduitCPQ + évaluation via core.rules."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import RegleProduitCPQ
from apps.cpq import selectors
from testkit.factories import CompanyFactory, UserFactory


def _auth(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


class TestReglesProduit(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.regle = RegleProduitCPQ.objects.create(
            company=self.company, nom='kWc>9 → triphasé requis',
            condition_group={
                'op': 'and',
                'conditions': [
                    {'field': 'kwc', 'operator': 'gt', 'value': 9},
                ],
            },
            actions=[{'type': 'exiger_option', 'valeur': 'triphase'}])

    def test_regle_declenchee_pour_12kwc(self):
        declenchees = selectors.evaluer_regles_produit(
            company=self.company, context={'kwc': 12})
        self.assertEqual(len(declenchees), 1)
        self.assertEqual(
            declenchees[0]['actions'],
            [{'type': 'exiger_option', 'valeur': 'triphase'}])

    def test_regle_non_declenchee_sous_seuil(self):
        declenchees = selectors.evaluer_regles_produit(
            company=self.company, context={'kwc': 5})
        self.assertEqual(declenchees, [])

    def test_endpoint_evaluer(self):
        client = _auth(self.user)
        resp = client.post('/api/django/cpq/regles/evaluer/',
                           {'context': {'kwc': 12}}, format='json')
        self.assertEqual(resp.status_code, 200)
        actions = resp.json()['actions_declenchees']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['nom'], 'kWc>9 → triphasé requis')

    def test_regle_inactive_ignoree(self):
        self.regle.actif = False
        self.regle.save()
        declenchees = selectors.evaluer_regles_produit(
            company=self.company, context={'kwc': 12})
        self.assertEqual(declenchees, [])

    def test_condition_group_invalide_rejetee(self):
        # Un condition_group mal formé est rejeté par le sérialiseur (validation
        # structurelle déléguée à core.rules.validate_condition_group).
        from apps.cpq.serializers import RegleProduitCPQSerializer
        ser = RegleProduitCPQSerializer(data={
            'nom': 'bad', 'condition_group': {'op': 'xor', 'conditions': []},
            'actions': []})
        self.assertFalse(ser.is_valid())
        self.assertIn('condition_group', ser.errors)
