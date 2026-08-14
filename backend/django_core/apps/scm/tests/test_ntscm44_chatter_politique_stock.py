"""NTSCM44 — Journalisation chatter sur les politiques de stock (le volet
cycle S&OP est couvert par NTSCM12, déjà testé — voir
`test_ntscm12_cycle_sop.py::test_reouvrir_requires_admin_and_logs_history`).

Critère d'acceptation : modifier `service_level_pct` d'une politique crée une
entrée d'activité visible avec ancienne/nouvelle valeur."""
from decimal import Decimal

from django.test import TestCase

from apps.scm.models import PolitiqueStock
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


class ChatterPolitiqueStockTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-chatter-politique', 'Supply Chatter Politique')
        self.admin = make_user(self.company, 'scm-chatter-politique-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Régulateur MPPT 60A', prix_vente=1400)
        self.politique = PolitiqueStock.objects.create(
            company=self.company, produit=self.produit, classe_abc='B',
            service_level_pct=Decimal('90'), point_commande=Decimal('15'),
            stock_securite_calcule=Decimal('5'))

    def test_modifier_service_level_pct_cree_une_entree_de_chatter(self):
        resp = auth(self.admin).patch(
            f'/api/django/scm/politiques-stock/{self.politique.id}/',
            {'service_level_pct': '97.5'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        hist = auth(self.admin).get(
            f'/api/django/scm/politiques-stock/{self.politique.id}/historique/')
        self.assertEqual(hist.status_code, 200, hist.data)
        entree = next(
            e for e in hist.data if e['field'] == 'service_level_pct')
        self.assertEqual(entree['old_value'], '90.00')
        self.assertEqual(entree['new_value'], '97.50')
        self.assertIsNotNone(entree['created_at'])
        self.assertEqual(entree['user_username'], self.admin.username)

    def test_modifier_stock_securite_manuel_cree_une_entree_de_chatter(self):
        resp = auth(self.admin).patch(
            f'/api/django/scm/politiques-stock/{self.politique.id}/',
            {'stock_securite_manuel': '12'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        hist = auth(self.admin).get(
            f'/api/django/scm/politiques-stock/{self.politique.id}/historique/')
        entree = next(
            e for e in hist.data if e['field'] == 'stock_securite_manuel')
        self.assertEqual(entree['new_value'], '12.00')

    def test_patch_sans_changement_reel_ne_cree_rien(self):
        # Même valeur envoyée que la valeur actuelle -> aucune entrée.
        auth(self.admin).patch(
            f'/api/django/scm/politiques-stock/{self.politique.id}/',
            {'service_level_pct': '90'}, format='json')
        hist = auth(self.admin).get(
            f'/api/django/scm/politiques-stock/{self.politique.id}/historique/')
        self.assertEqual(len(hist.data), 0)

    def test_historique_refuse_role_non_responsable(self):
        normal = make_user(self.company, 'scm-chatter-politique-normal', 'normal')
        resp = auth(normal).get(
            f'/api/django/scm/politiques-stock/{self.politique.id}/historique/')
        self.assertEqual(resp.status_code, 403)
