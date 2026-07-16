"""NTCPQ1 — OptionProduit + ContrainteCompatibilite + valider-compatibilite."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import OptionProduit, ContrainteCompatibilite
from apps.cpq import selectors
from testkit.factories import CompanyFactory, ProduitFactory, UserFactory


def _auth(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


class TestCompatibilite(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.pa = ProduitFactory(company=self.company)
        self.pb = ProduitFactory(company=self.company)
        self.pc = ProduitFactory(company=self.company)

    def test_incompatible_deux_produits_violation_bloquante(self):
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.pa, produit_b=self.pb,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE,
            message_utilisateur='Ces deux produits ne sont pas compatibles.')
        client = _auth(self.user)
        resp = client.post(
            '/api/django/cpq/valider-compatibilite/',
            {'produit_ids': [self.pa.id, self.pb.id]}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['valide'])
        self.assertEqual(len(data['bloquantes']), 1)
        self.assertEqual(
            data['bloquantes'][0]['message'],
            'Ces deux produits ne sont pas compatibles.')

    def test_incompatible_un_seul_produit_pas_de_violation(self):
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.pa, produit_b=self.pb,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE)
        v = selectors.violations_compatibilite(
            company=self.company, produit_ids=[self.pa.id])
        self.assertEqual(v, [])

    def test_requiert_manquant_est_bloquant(self):
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.pa, produit_b=self.pb,
            type=ContrainteCompatibilite.TypeContrainte.REQUIERT)
        v = selectors.violations_compatibilite(
            company=self.company, produit_ids=[self.pa.id])
        self.assertEqual(len(v), 1)
        self.assertTrue(v[0]['bloquante'])

    def test_recommande_manquant_est_avertissement(self):
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.pa, produit_b=self.pc,
            type=ContrainteCompatibilite.TypeContrainte.RECOMMANDE)
        client = _auth(self.user)
        resp = client.post(
            '/api/django/cpq/valider-compatibilite/',
            {'produit_ids': [self.pa.id]}, format='json')
        data = resp.json()
        self.assertTrue(data['valide'])  # aucun bloquant
        self.assertEqual(len(data['avertissements']), 1)

    def test_scope_societe_isolation(self):
        other = CompanyFactory()
        ContrainteCompatibilite.objects.create(
            company=other, produit_a=self.pa, produit_b=self.pb,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE)
        v = selectors.violations_compatibilite(
            company=self.company, produit_ids=[self.pa.id, self.pb.id])
        self.assertEqual(v, [])

    def test_option_produit_creation(self):
        opt = OptionProduit.objects.create(
            company=self.company, produit=self.pa,
            groupe_option='Onduleur', obligatoire=True)
        self.assertEqual(str(opt), f'Onduleur · produit {self.pa.id}')
