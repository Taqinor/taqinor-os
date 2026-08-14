"""NTMFG9 — Écran de gestion des Ordres de Fabrication (liste + détail +
Kanban par statut).

Critère backend : écran liste+kanban+détail fonctionnel avec les données
NTMFG3/6, filtre poste opérationnel. (Le rendu React lui-même n'est pas
testé ici, hors gates backend de cette lane — voir
`frontend/src/pages/mrp/OrdresFabricationPage.jsx`.)"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.services import confirmer_of
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class FiltrePosteTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ecran-1', 'MRP Ecran 1')
        self.user = make_user(self.company, 'mrp-ecran-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.poste_a = PosteDeCharge.objects.create(
            company=self.company, code='P-A', nom='Poste A')
        self.poste_b = PosteDeCharge.objects.create(
            company=self.company, code='P-B', nom='Poste B')
        self.gamme_a = Gamme.objects.create(
            company=self.company, nom='Gamme A', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme_a, ordre=1, poste_charge=self.poste_a, libelle='Op A')
        self.gamme_b = Gamme.objects.create(
            company=self.company, nom='Gamme B', produit=self.produit, version=2)
        OperationGamme.objects.create(
            gamme=self.gamme_b, ordre=1, poste_charge=self.poste_b, libelle='Op B')

    def test_filtre_par_poste(self):
        of_a = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1, gamme=self.gamme_a)
        confirmer_of(of_a)
        of_b = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1, gamme=self.gamme_b)
        confirmer_of(of_b)

        resp = self.api.get(f'/api/django/mrp/ordres-fabrication/?poste={self.poste_a.id}')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        ids = {row['id'] for row in data}
        self.assertIn(of_a.id, ids)
        self.assertNotIn(of_b.id, ids)

    def test_sans_filtre_poste_renvoie_tout(self):
        of_a = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1, gamme=self.gamme_a)
        of_b = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1, gamme=self.gamme_b)
        resp = self.api.get('/api/django/mrp/ordres-fabrication/')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        ids = {row['id'] for row in data}
        self.assertIn(of_a.id, ids)
        self.assertIn(of_b.id, ids)


class ProduitNomTests(TestCase):
    def test_produit_nom_expose_pour_l_ecran(self):
        company = make_company('mrp-ecran-2', 'MRP Ecran 2')
        user = make_user(company, 'mrp-ecran-user-2')
        api = auth(user)
        produit = make_produit(company, 'Coffret assemblé')
        of = OrdreFabrication.objects.create(
            company=company, produit=produit, quantite=1)
        resp = api.get(f'/api/django/mrp/ordres-fabrication/{of.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['produit_nom'], 'Coffret assemblé')
