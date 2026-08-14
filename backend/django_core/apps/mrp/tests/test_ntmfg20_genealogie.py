"""NTMFG20 — Traçabilité amont/aval par lot de fabrication (généalogie).

Critère : la génération remonte correctement amont+aval sur un cas testé à
2 niveaux, isolation tenant, lecture seule."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import OrdreFabrication, ReservationOF
from apps.mrp.selectors import genealogie_of
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class GenealogieTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-genea-1', 'MRP Généalogie 1')
        # Chaîne à 2 niveaux : matiere -> sous_ensemble -> composite.
        self.matiere = make_produit(self.company, 'Matière première')
        self.sous_ensemble = make_produit(self.company, 'Sous-ensemble')
        self.composite = make_produit(self.company, 'Composite fini')

        # OF1 : produit le sous-ensemble à partir de la matière.
        self.of1 = OrdreFabrication.objects.create(
            company=self.company, produit=self.sous_ensemble, quantite=10,
            statut=OrdreFabrication.Statut.TERMINE)
        ReservationOF.objects.create(
            ordre_fabrication=self.of1, produit=self.matiere,
            quantite=Decimal('20'), consomme=True)

        # OF2 : produit le composite à partir du sous-ensemble (produit par OF1).
        self.of2 = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=5,
            statut=OrdreFabrication.Statut.TERMINE)
        ReservationOF.objects.create(
            ordre_fabrication=self.of2, produit=self.sous_ensemble,
            quantite=Decimal('10'), consomme=True)

        # OF3 : consomme le composite d'OF2 (aval d'OF2).
        self.of3 = OrdreFabrication.objects.create(
            company=self.company, produit=make_produit(self.company, 'Produit final'),
            quantite=1)
        ReservationOF.objects.create(
            ordre_fabrication=self.of3, produit=self.composite,
            quantite=Decimal('5'), consomme=False)

    def test_amont_deux_niveaux(self):
        resultat = genealogie_of(self.of2, profondeur=2)
        self.assertEqual(len(resultat['amont']), 1)
        ligne = resultat['amont'][0]
        self.assertEqual(ligne['produit_id'], self.sous_ensemble.id)
        self.assertIsNotNone(ligne['of_source'])
        self.assertEqual(ligne['of_source']['of_id'], self.of1.id)
        # 2e niveau : la matière consommée par OF1.
        self.assertEqual(len(ligne['of_source']['amont']), 1)
        self.assertEqual(
            ligne['of_source']['amont'][0]['produit_id'], self.matiere.id)

    def test_aval_un_niveau(self):
        resultat = genealogie_of(self.of2, profondeur=2)
        self.assertEqual(len(resultat['aval']), 1)
        self.assertEqual(resultat['aval'][0]['of_id'], self.of3.id)

    def test_of_sans_composants_ni_consommateurs(self):
        of_isole = OrdreFabrication.objects.create(
            company=self.company, produit=make_produit(self.company, 'Isolé'),
            quantite=1)
        resultat = genealogie_of(of_isole)
        self.assertEqual(resultat['amont'], [])
        self.assertEqual(resultat['aval'], [])

    def test_isolation_tenant(self):
        autre_company = make_company('mrp-genea-2', 'MRP Généalogie 2')
        autre_produit = make_produit(autre_company, 'Produit autre société')
        autre_of = OrdreFabrication.objects.create(
            company=autre_company, produit=autre_produit, quantite=1)
        ReservationOF.objects.create(
            ordre_fabrication=autre_of, produit=self.sous_ensemble, quantite=1)
        # Le sous-ensemble d'une AUTRE société ne doit jamais apparaître en
        # aval de of1 (isolation stricte par company_id).
        resultat = genealogie_of(self.of1)
        of_ids_aval = [a['of_id'] for a in resultat['aval']]
        self.assertNotIn(autre_of.id, of_ids_aval)


class GenealogieApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-genea-api-1', 'MRP Généalogie API 1')
        self.user = make_user(self.company, 'mrp-genea-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1)

    def test_endpoint_genealogie(self):
        resp = self.api.get(
            f'/api/django/mrp/ordres-fabrication/{self.of.id}/genealogie/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['of_id'], self.of.id)
        self.assertIn('amont', resp.data)
        self.assertIn('aval', resp.data)
