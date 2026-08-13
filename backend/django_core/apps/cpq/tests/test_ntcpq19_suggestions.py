"""NTCPQ19 — Suggestions de vente croisée (RECOMMANDE + co-achat historique)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import ContrainteCompatibilite
from apps.cpq.reports import suggestions_produit
from apps.ventes.models import Devis, LigneDevis
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

URL = '/api/django/cpq/suggestions/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestSuggestionsProduit(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.onduleur = ProduitFactory(company=self.company, nom='Onduleur X')
        self.acc1 = ProduitFactory(company=self.company, nom='Parafoudre')
        self.acc2 = ProduitFactory(company=self.company, nom='Coffret AC')
        self.acc3 = ProduitFactory(company=self.company, nom='Câble solaire')
        self.acc4 = ProduitFactory(company=self.company, nom='Connecteur MC4')

    def _devis_accepte(self, produits):
        devis = DevisFactory(
            company=self.company, statut=Devis.Statut.ACCEPTE)
        for produit in produits:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('100.00'))
        return devis

    def test_co_achat_les_plus_frequents(self):
        self._devis_accepte([self.onduleur, self.acc1, self.acc2])
        self._devis_accepte([self.onduleur, self.acc1, self.acc3])
        self._devis_accepte([self.onduleur, self.acc1, self.acc2, self.acc4])
        sugg = suggestions_produit(
            company=self.company, produit_id=self.onduleur.id)
        self.assertEqual(len(sugg), 3)
        self.assertEqual(sugg[0]['nom'], 'Parafoudre')
        self.assertEqual(sugg[0]['occurrences'], 3)
        self.assertEqual(sugg[1]['nom'], 'Coffret AC')
        self.assertTrue(all(s['source'] == 'co_achat' for s in sugg))

    def test_recommande_prioritaire_sur_le_co_achat(self):
        self._devis_accepte([self.onduleur, self.acc1])
        self._devis_accepte([self.onduleur, self.acc1])
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.onduleur,
            produit_b=self.acc4,
            type=ContrainteCompatibilite.TypeContrainte.RECOMMANDE)
        sugg = suggestions_produit(
            company=self.company, produit_id=self.onduleur.id)
        self.assertEqual(sugg[0]['nom'], 'Connecteur MC4')
        self.assertEqual(sugg[0]['source'], 'recommande')

    def test_devis_non_acceptes_ignores(self):
        DevisFactory(company=self.company, statut=Devis.Statut.BROUILLON)
        brouillon = DevisFactory(
            company=self.company, statut=Devis.Statut.BROUILLON)
        for produit in (self.onduleur, self.acc1):
            LigneDevis.objects.create(
                devis=brouillon, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('100.00'))
        self.assertEqual(suggestions_produit(
            company=self.company, produit_id=self.onduleur.id), [])

    def test_isolation_societe(self):
        self._devis_accepte([self.onduleur, self.acc1])
        self.assertEqual(suggestions_produit(
            company=CompanyFactory(), produit_id=self.onduleur.id), [])

    def test_le_produit_lui_meme_nest_jamais_suggere(self):
        self._devis_accepte([self.onduleur, self.onduleur, self.acc1])
        sugg = suggestions_produit(
            company=self.company, produit_id=self.onduleur.id)
        self.assertNotIn(self.onduleur.id, [s['produit_id'] for s in sugg])

    def test_endpoint(self):
        self._devis_accepte([self.onduleur, self.acc1])
        resp = auth(self.user).get(f'{URL}?produit_id={self.onduleur.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            [s['nom'] for s in resp.data['suggestions']], ['Parafoudre'])

    def test_endpoint_sans_produit_id(self):
        resp = auth(self.user).get(URL)
        self.assertEqual(resp.status_code, 400, resp.data)
