"""NTCPQ29 — Wizard de résolution de conflit de compatibilité.

Quand ``NTCPQ1`` renvoie une violation BLOQUANTE, elle porte désormais
``alternatives`` (produits compatibles) au lieu d'un simple message
d'erreur sans issue."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq import selectors
from apps.cpq.models import ContrainteCompatibilite, ProduitEquivalent
from testkit.factories import CompanyFactory, ProduitFactory, UserFactory

VALIDER_URL = '/api/django/cpq/valider-compatibilite/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestAlternativesIncompatible(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.pa = ProduitFactory(company=self.company, nom='Onduleur A')
        self.pb = ProduitFactory(company=self.company, nom='Batterie B')
        self.pc = ProduitFactory(company=self.company, nom='Batterie C')
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.pa, produit_b=self.pb,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE,
            message_utilisateur='Onduleur A incompatible avec Batterie B.')

    def test_alternative_via_produit_equivalent(self):
        ProduitEquivalent.objects.create(
            company=self.company, produit_source=self.pb,
            produit_substitut=self.pc, tier=ProduitEquivalent.Tier.STANDARD)
        violation = {
            'type': ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE,
            'produit_a': self.pa.id, 'produit_b': self.pb.id,
        }
        alternatives = selectors.alternatives_violation(
            company=self.company, produit_ids=[self.pa.id, self.pb.id],
            violation=violation)
        self.assertEqual(len(alternatives), 1)
        self.assertEqual(alternatives[0]['produit_id'], self.pc.id)
        self.assertEqual(alternatives[0]['source'], 'substitut')

    def test_alternative_via_recommande(self):
        pd = ProduitFactory(company=self.company, nom='Batterie D')
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.pa, produit_b=pd,
            type=ContrainteCompatibilite.TypeContrainte.RECOMMANDE)
        violation = {
            'type': ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE,
            'produit_a': self.pa.id, 'produit_b': self.pb.id,
        }
        alternatives = selectors.alternatives_violation(
            company=self.company, produit_ids=[self.pa.id, self.pb.id],
            violation=violation)
        self.assertEqual(len(alternatives), 1)
        self.assertEqual(alternatives[0]['produit_id'], pd.id)
        self.assertEqual(alternatives[0]['source'], 'recommande')

    def test_aucune_alternative_connue_liste_vide(self):
        violation = {
            'type': ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE,
            'produit_a': self.pa.id, 'produit_b': self.pb.id,
        }
        alternatives = selectors.alternatives_violation(
            company=self.company, produit_ids=[self.pa.id, self.pb.id],
            violation=violation)
        self.assertEqual(alternatives, [])

    def test_endpoint_expose_alternatives_sur_violation_bloquante(self):
        ProduitEquivalent.objects.create(
            company=self.company, produit_source=self.pb,
            produit_substitut=self.pc, tier=ProduitEquivalent.Tier.STANDARD)
        resp = auth(self.user).post(
            VALIDER_URL, {'produit_ids': [self.pa.id, self.pb.id]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['bloquantes']), 1)
        self.assertEqual(
            len(resp.data['bloquantes'][0]['alternatives']), 1)


class TestAlternativesRequiert(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.pa = ProduitFactory(company=self.company, nom='Pompe')
        self.pb = ProduitFactory(company=self.company, nom='Variateur requis')
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.pa, produit_b=self.pb,
            type=ContrainteCompatibilite.TypeContrainte.REQUIERT)

    def test_alternative_est_le_produit_manquant_lui_meme(self):
        violation = {
            'type': ContrainteCompatibilite.TypeContrainte.REQUIERT,
            'produit_a': self.pa.id, 'produit_b': self.pb.id,
        }
        alternatives = selectors.alternatives_violation(
            company=self.company, produit_ids=[self.pa.id],
            violation=violation)
        self.assertEqual(len(alternatives), 1)
        self.assertEqual(alternatives[0]['produit_id'], self.pb.id)
        self.assertEqual(alternatives[0]['source'], 'a_ajouter')
