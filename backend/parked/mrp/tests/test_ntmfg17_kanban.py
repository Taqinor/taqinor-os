"""NTMFG17 — Ordre de fabrication répétitif / kanban de réappro atelier
(pull flow).

Critère : franchir le seuil crée un OF brouillon (pas dupliqué si déjà un OF
ouvert pour ce produit), déclenchement manuel fonctionne sans Celery beat,
isolation tenant."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OrdreFabrication, ReglesKanbanProduction
from apps.mrp.services import declencher_kanban, declencher_kanban_toutes_regles
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit', quantite_stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=0, tva=20,
        quantite_stock=quantite_stock)


class KanbanDeclencheurTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-kanban-1', 'MRP Kanban 1')
        self.produit = make_produit(self.company, quantite_stock=2)

    def test_franchissement_seuil_cree_of_brouillon(self):
        regle = ReglesKanbanProduction.objects.create(
            company=self.company, produit=self.produit,
            quantite_lot=Decimal('10'), seuil_declenchement=Decimal('5'))
        of = declencher_kanban(regle)
        self.assertIsNotNone(of)
        self.assertEqual(of.statut, 'brouillon')
        self.assertEqual(of.quantite, Decimal('10'))

    def test_stock_au_dessus_du_seuil_pas_de_declenchement(self):
        regle = ReglesKanbanProduction.objects.create(
            company=self.company, produit=self.produit,
            quantite_lot=Decimal('10'), seuil_declenchement=Decimal('1'))
        of = declencher_kanban(regle)
        self.assertIsNone(of)

    def test_jamais_duplique_si_of_deja_ouvert(self):
        regle = ReglesKanbanProduction.objects.create(
            company=self.company, produit=self.produit,
            quantite_lot=Decimal('10'), seuil_declenchement=Decimal('5'))
        premier = declencher_kanban(regle)
        self.assertIsNotNone(premier)
        deuxieme = declencher_kanban(regle)
        self.assertIsNone(deuxieme)
        self.assertEqual(
            OrdreFabrication.objects.filter(company=self.company).count(), 1)

    def test_gamme_active_attachee_si_existante(self):
        gamme = Gamme.objects.create(
            company=self.company, nom='Gamme kanban', produit=self.produit)
        regle = ReglesKanbanProduction.objects.create(
            company=self.company, produit=self.produit,
            quantite_lot=Decimal('5'), seuil_declenchement=Decimal('5'))
        of = declencher_kanban(regle)
        self.assertEqual(of.gamme_id, gamme.id)

    def test_regle_inactive_ignoree(self):
        regle = ReglesKanbanProduction.objects.create(
            company=self.company, produit=self.produit,
            quantite_lot=Decimal('10'), seuil_declenchement=Decimal('5'),
            actif=False)
        of = declencher_kanban(regle)
        self.assertIsNone(of)

    def test_toutes_regles_isolation_tenant(self):
        autre_company = make_company('mrp-kanban-2', 'MRP Kanban 2')
        ReglesKanbanProduction.objects.create(
            company=self.company, produit=self.produit,
            quantite_lot=Decimal('10'), seuil_declenchement=Decimal('5'))
        crees = declencher_kanban_toutes_regles(autre_company)
        self.assertEqual(crees, [])
        crees = declencher_kanban_toutes_regles(self.company)
        self.assertEqual(len(crees), 1)


class KanbanDeclencherManuelApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-kanban-api-1', 'MRP Kanban API 1')
        self.user = make_user(self.company, 'mrp-kanban-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company, quantite_stock=0)

    def test_declenchement_manuel_endpoint(self):
        ReglesKanbanProduction.objects.create(
            company=self.company, produit=self.produit,
            quantite_lot=Decimal('3'), seuil_declenchement=Decimal('1'))
        resp = self.api.post('/api/django/mrp/kanban/declencher/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['quantite'], '3')
