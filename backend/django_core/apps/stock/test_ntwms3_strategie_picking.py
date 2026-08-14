"""NTWMS3 — stratégies de prélèvement FIFO / FEFO / ZONE.

Vérifie que :
  * `aucune` (défaut) laisse le comportement historique intact — une ligne
    libre, jamais de lot ni de casier imposé ;
  * FEFO propose TOUJOURS le lot dont la péremption est la plus proche ;
  * FIFO propose le lot le plus ancien ;
  * ZONE suit l'ordre de parcours des casiers (FG319) ;
  * un produit sans lot / sans casier ne provoque jamais d'erreur.

Run :
    python manage.py test apps.stock.test_ntwms3_strategie_picking -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Categorie, EmplacementStock, LotEntrepot, Produit,
)
from apps.stock.selectors import (
    resoudre_allocation_picking, strategie_picking_produit,
)

User = get_user_model()

# Dates FIXES (jamais `today()`).
PEREMPTION_PROCHE = datetime.date(2026, 4, 30)
PEREMPTION_LOINTAINE = datetime.date(2027, 12, 31)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms3Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms3-co', 'NTWMS3 Co')
        self.autre = make_company('ntwms3-autre', 'NTWMS3 Autre')
        self.admin = User.objects.create_user(
            username='ntwms3_admin', password='x', role_legacy='admin',
            company=self.company)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Batteries NTWMS3')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie LFP', sku='LFP-NTWMS3',
            categorie=self.categorie, prix_achat=Decimal('100'),
            prix_vente=Decimal('160'), quantite_stock=30)
        self.api = auth(self.admin)

    def _deux_lots(self):
        """Lot A créé EN PREMIER mais périmant en dernier ; lot B créé après
        mais périmant en premier — FIFO et FEFO doivent donc diverger."""
        lot_ancien = LotEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_lot='LOT-A',
            date_peremption=PEREMPTION_LOINTAINE, quantite_recue=10,
            quantite_restante=10)
        lot_recent = LotEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_lot='LOT-B',
            date_peremption=PEREMPTION_PROCHE, quantite_recue=10,
            quantite_restante=10)
        return lot_ancien, lot_recent


class TestStrategieParDefaut(Ntwms3Base):
    def test_defaut_aucune_comportement_historique(self):
        self.assertEqual(self.categorie.strategie_picking_defaut, 'aucune')
        self.assertEqual(strategie_picking_produit(self.produit), 'aucune')
        self._deux_lots()
        plan = resoudre_allocation_picking(self.produit, 5)
        self.assertEqual(len(plan), 1)
        self.assertIsNone(plan[0]['lot_id'])
        self.assertIsNone(plan[0]['bin_id'])
        self.assertEqual(plan[0]['quantite'], 5)

    def test_produit_sans_categorie(self):
        orphelin = Produit.objects.create(
            company=self.company, nom='Vis inox', sku='VIS-NTWMS3',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        self.assertEqual(strategie_picking_produit(orphelin), 'aucune')


class TestFefoEtFifo(Ntwms3Base):
    def test_fefo_propose_la_peremption_la_plus_proche(self):
        self.categorie.strategie_picking_defaut = (
            Categorie.StrategiePicking.FEFO)
        self.categorie.save(update_fields=['strategie_picking_defaut'])
        self._deux_lots()
        plan = resoudre_allocation_picking(self.produit, 12)
        self.assertEqual(plan[0]['numero_lot'], 'LOT-B')
        self.assertEqual(plan[0]['date_peremption'], PEREMPTION_PROCHE)
        self.assertEqual(plan[0]['quantite'], 10)
        self.assertEqual(plan[1]['numero_lot'], 'LOT-A')
        self.assertEqual(plan[1]['quantite'], 2)

    def test_fifo_propose_le_lot_le_plus_ancien(self):
        self.categorie.strategie_picking_defaut = (
            Categorie.StrategiePicking.FIFO)
        self.categorie.save(update_fields=['strategie_picking_defaut'])
        self._deux_lots()
        plan = resoudre_allocation_picking(self.produit, 4)
        self.assertEqual(plan[0]['numero_lot'], 'LOT-A')

    def test_lot_epuise_ignore(self):
        self.categorie.strategie_picking_defaut = (
            Categorie.StrategiePicking.FEFO)
        self.categorie.save(update_fields=['strategie_picking_defaut'])
        _, lot_recent = self._deux_lots()
        lot_recent.quantite_restante = 0
        lot_recent.save(update_fields=['quantite_restante'])
        plan = resoudre_allocation_picking(self.produit, 3)
        self.assertEqual(plan[0]['numero_lot'], 'LOT-A')

    def test_produit_non_suivi_par_lot_ne_leve_pas(self):
        self.categorie.strategie_picking_defaut = (
            Categorie.StrategiePicking.FEFO)
        self.categorie.save(update_fields=['strategie_picking_defaut'])
        plan = resoudre_allocation_picking(self.produit, 7)
        self.assertEqual(len(plan), 1)
        self.assertIsNone(plan[0]['lot_id'])
        self.assertEqual(plan[0]['quantite'], 7)


class TestStrategieZone(Ntwms3Base):
    def setUp(self):
        super().setUp()
        from apps.installations.models import BinLocation, BinAffectation

        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS3', is_principal=True)
        loin = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='D-08-02', zone='D', allee='08', casier='02', ordre=80)
        proche = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-01', zone='A', allee='01', casier='01', ordre=2)
        BinAffectation.objects.create(
            company=self.company, bin=loin, produit=self.produit, quantite=6)
        BinAffectation.objects.create(
            company=self.company, bin=proche, produit=self.produit, quantite=4)
        self.categorie.strategie_picking_defaut = (
            Categorie.StrategiePicking.ZONE)
        self.categorie.save(update_fields=['strategie_picking_defaut'])

    def test_zone_suit_l_ordre_de_parcours(self):
        plan = resoudre_allocation_picking(self.produit, 9)
        self.assertEqual(plan[0]['bin_code'], 'A-01-01')
        self.assertEqual(plan[0]['quantite'], 4)
        self.assertEqual(plan[1]['bin_code'], 'D-08-02')
        self.assertEqual(plan[1]['quantite'], 5)


class TestEndpointPlanPicking(Ntwms3Base):
    def test_endpoint_expose_le_plan(self):
        self.categorie.strategie_picking_defaut = (
            Categorie.StrategiePicking.FEFO)
        self.categorie.save(update_fields=['strategie_picking_defaut'])
        self._deux_lots()
        resp = self.api.get(
            f'/api/django/stock/produits/{self.produit.id}/plan-picking/'
            '?quantite=3')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['strategie'], 'fefo')
        self.assertEqual(resp.data['lignes'][0]['numero_lot'], 'LOT-B')

    def test_strategie_inconnue_refusee(self):
        resp = self.api.get(
            f'/api/django/stock/produits/{self.produit.id}/plan-picking/'
            '?quantite=3&strategie=lifo')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe(self):
        intrus = User.objects.create_user(
            username='ntwms3_intrus', password='x', role_legacy='admin',
            company=self.autre)
        resp = auth(intrus).get(
            f'/api/django/stock/produits/{self.produit.id}/plan-picking/')
        self.assertEqual(resp.status_code, 404)
