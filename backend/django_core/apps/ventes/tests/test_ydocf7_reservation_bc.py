"""YDOCF7 — BonCommande confirmé : réservation de stock (au lieu du seul
décrément à la livraison).

Couvre (toggle `reserver_stock_bc` sur CompanyProfile) :
  * toggle OFF (défaut) : confirmer/annuler/marquer-livre restent
    byte-identiques à avant (décrément direct à la livraison seulement) ;
  * toggle ON : confirmer un BC réserve les quantités (StockReservation),
    annuler libère, livrer solde la réservation SANS double décrément ;
  * jamais d'import direct de `installations.models` depuis `ventes` (le
    branchement passe par `installations.services`).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.parametres.models import CompanyProfile
from apps.ventes.models import BonCommande, Devis, LigneDevis
from apps.installations.models import Installation, StockReservation

User = get_user_model()


def make_company(slug='ydocf7-co', nom='YDOCF7 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class Ydocf7TestBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ydocf7_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YDOCF7',
            telephone='+212600000077')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur YDOCF7', sku='YDOCF7-OND1',
            prix_vente=Decimal('5000'), quantite_stock=20, tva=Decimal('20.00'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-YDOCF7-0001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Onduleur',
            quantite=Decimal('5'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference='BC-YDOCF7-0001',
            client=self.client_obj, devis=self.devis,
            statut=BonCommande.Statut.EN_ATTENTE)
        self.installation = Installation.objects.create(
            company=self.company, reference='CHT-YDOCF7-0001',
            client=self.client_obj, devis=self.devis,
            statut=Installation.Statut.SIGNE)

    def _toggle(self, on):
        prof = CompanyProfile.get(company=self.company)
        prof.reserver_stock_bc = on
        prof.save()


class TestToggleOff(Ydocf7TestBase):
    def test_confirmer_sans_toggle_ne_reserve_rien(self):
        self._toggle(False)
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(StockReservation.objects.filter(
            installation=self.installation).exists())

    def test_livraison_sans_toggle_decremente_directement(self):
        self._toggle(False)
        self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/')
        qte_avant = self.produit.quantite_stock
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/marquer-livre/')
        self.assertEqual(r.status_code, 200, r.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, qte_avant - 5)


class TestToggleOn(Ydocf7TestBase):
    def test_confirmer_reserve_les_quantites(self):
        self._toggle(True)
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/')
        self.assertEqual(r.status_code, 200, r.data)
        resa = StockReservation.objects.get(
            installation=self.installation, produit=self.produit)
        self.assertEqual(resa.quantite, 5)
        self.assertTrue(resa.active)
        self.assertFalse(resa.consomme)
        # Le stock EN MAIN n'est PAS décrémenté à la confirmation (réservé
        # seulement — le "disponible" en tient compte côté stock, pas ici).
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 20)

    def test_annuler_libere_la_reservation(self):
        self._toggle(True)
        self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/')
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/annuler/')
        self.assertEqual(r.status_code, 200, r.data)
        resa = StockReservation.objects.get(
            installation=self.installation, produit=self.produit)
        self.assertFalse(resa.active)
        self.assertFalse(resa.consomme)

    def test_livraison_solde_la_reservation_sans_double_decrement(self):
        self._toggle(True)
        self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/')
        qte_avant = self.produit.quantite_stock
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/marquer-livre/')
        self.assertEqual(r.status_code, 200, r.data)
        resa = StockReservation.objects.get(
            installation=self.installation, produit=self.produit)
        self.assertTrue(resa.consomme)
        self.produit.refresh_from_db()
        # Une SEULE sortie de 5 (via la consommation de réservation), jamais 10.
        self.assertEqual(self.produit.quantite_stock, qte_avant - 5)

    def test_bc_sans_chantier_est_noop_sur(self):
        # BC sans devis (donc sans chantier associé) : confirmer ne casse rien.
        self._toggle(True)
        bc_isole = BonCommande.objects.create(
            company=self.company, reference='BC-YDOCF7-ISOLE',
            client=self.client_obj, statut=BonCommande.Statut.EN_ATTENTE)
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{bc_isole.id}/confirmer/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(StockReservation.objects.filter(
            produit=self.produit, installation__bon_commande=bc_isole
        ).exists())
