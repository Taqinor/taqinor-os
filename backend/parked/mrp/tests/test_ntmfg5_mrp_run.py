"""NTMFG5 — Calcul des besoins nets (MRP) multi-produits sur horizon.

Critère : un scénario avec 2 niveaux de nomenclature + un OF planifié + un
devis signé produit un besoin net correct par période, proposition achat vs
fabrication cohérente, isolation tenant."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OrdreFabrication
from apps.mrp.selectors import calculer_besoins_nets
from apps.stock.models import KitComposant, KitProduit, Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom, quantite_stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=0, tva=20,
        quantite_stock=quantite_stock)


class CalculerBesoinsNetsTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-mrp5-1', 'MRP MRP5 1')
        self.raw1 = make_produit(self.company, 'Raw 1', quantite_stock=50)
        self.raw2 = make_produit(self.company, 'Raw 2', quantite_stock=5)
        self.fini = make_produit(self.company, 'Produit fini', quantite_stock=0)
        self.kit = KitProduit.objects.create(company=self.company, nom='Kit fini')
        KitComposant.objects.create(kit=self.kit, produit=self.raw1, quantite=Decimal('2'))
        KitComposant.objects.create(kit=self.kit, produit=self.raw2, quantite=Decimal('1'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme fini', produit=self.fini,
            kit_source=self.kit)

    def test_deux_niveaux_avec_demande_independante(self):
        resultats = calculer_besoins_nets(
            self.company,
            demande_independante={self.fini.id: 20})
        par_id = {r['produit_id']: r for r in resultats}

        # Niveau 1 : produit fini -> besoin net = 20 (rien en stock/en-cours).
        self.assertEqual(par_id[self.fini.id]['besoin_net'], '20')
        self.assertEqual(par_id[self.fini.id]['proposition'], 'fabriquer')

        # Niveau 2 : composants explosés (20 x 2 = 40 raw1, 20 x 1 = 20 raw2).
        self.assertEqual(par_id[self.raw1.id]['besoin_net'], '0')  # 40 <= 50 en stock.
        self.assertIsNone(par_id[self.raw1.id]['proposition'])
        self.assertEqual(par_id[self.raw2.id]['besoin_net'], '15')  # 20 - 5 en stock.
        self.assertEqual(par_id[self.raw2.id]['proposition'], 'acheter')

    def test_of_planifie_reduit_le_besoin_net(self):
        OrdreFabrication.objects.create(
            company=self.company, produit=self.fini, quantite=5,
            gamme=self.gamme, statut=OrdreFabrication.Statut.PLANIFIE)
        resultats = calculer_besoins_nets(
            self.company, demande_independante={self.fini.id: 20})
        par_id = {r['produit_id']: r for r in resultats}
        self.assertEqual(par_id[self.fini.id]['besoin_net'], '15')
        self.assertEqual(par_id[self.fini.id]['en_cours_fabrication'], '5')

    def test_of_annule_ne_compte_pas_dans_en_cours(self):
        OrdreFabrication.objects.create(
            company=self.company, produit=self.fini, quantite=100,
            gamme=self.gamme, statut=OrdreFabrication.Statut.ANNULE)
        resultats = calculer_besoins_nets(
            self.company, demande_independante={self.fini.id: 20})
        par_id = {r['produit_id']: r for r in resultats}
        self.assertEqual(par_id[self.fini.id]['besoin_net'], '20')

    def test_isolation_tenant(self):
        autre_company = make_company('mrp-mrp5-2', 'MRP MRP5 2')
        resultats = calculer_besoins_nets(
            autre_company, produits=[self.fini.id])
        # Le produit appartient à une AUTRE société -> introuvable, ignoré.
        self.assertEqual(resultats, [])

    def test_stock_securite_pct_gonfle_le_besoin(self):
        resultats = calculer_besoins_nets(
            self.company, demande_independante={self.fini.id: 20},
            stock_securite_pct=Decimal('10'))
        par_id = {r['produit_id']: r for r in resultats}
        # besoin_brut = 20 + 10% de 20 = 22 -> besoin_net = 22.
        self.assertEqual(par_id[self.fini.id]['besoin_net'], '22')


class MrpRunApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-mrp5-api-1', 'MRP MRP5 API 1')
        self.user = make_user(self.company, 'mrp-mrp5-api-user')
        self.api = auth(self.user)
        self.fini = make_produit(self.company, 'Produit fini API')
        self.raw = make_produit(self.company, 'Raw API', quantite_stock=10)
        kit = KitProduit.objects.create(company=self.company, nom='Kit API')
        KitComposant.objects.create(kit=kit, produit=self.raw, quantite=Decimal('1'))
        Gamme.objects.create(
            company=self.company, nom='Gamme API', produit=self.fini, kit_source=kit)

    def test_mrp_run_endpoint(self):
        resp = self.api.post('/api/django/mrp/mrp-run/', {
            'demande_independante': {str(self.fini.id): 5},
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        par_id = {r['produit_id']: r for r in resp.data}
        self.assertEqual(par_id[self.fini.id]['besoin_net'], '5')
        self.assertEqual(par_id[self.fini.id]['proposition'], 'fabriquer')
