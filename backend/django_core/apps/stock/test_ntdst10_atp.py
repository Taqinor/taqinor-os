"""NTDST10 — disponibilité ATP (Available-To-Promise) simple.

Critère d'acceptation testé : un produit EN RUPTURE avec une commande
fournisseur CONFIRMÉE dans 5 jours affiche ``disponible_le`` = CETTE date.

Toutes les dates sont FIXES et injectées.

Run :
    python manage.py test apps.stock.test_ntdst10_atp -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    ParametresNegoce, Produit,
)
from apps.stock.selectors_negoce import atp_produit

User = get_user_model()

AUJOURDHUI = datetime.date(2026, 6, 1)
DANS_5_JOURS = AUJOURDHUI + datetime.timedelta(days=5)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntdst10Base(TestCase):
    def setUp(self):
        self.company = make_company('ntdst10-co', 'NTDST10 Co')
        self.autre = make_company('ntdst10-autre', 'NTDST10 Autre')
        self.admin = User.objects.create_user(
            username='ntdst10_admin', password='x', role_legacy='admin',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTDST10')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 6 kW', sku='OND6-NTDST10',
            prix_achat=Decimal('8000'), prix_vente=Decimal('11000'),
            quantite_stock=0)
        self._seq = 0

    def _commande(self, *, quantite, quantite_recue=0, confirmee_le,
                  statut=None):
        self._seq += 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-NTDST10-{self._seq:04d}',
            fournisseur=self.fournisseur, date_commande=AUJOURDHUI,
            date_confirmee_fournisseur=confirmee_le,
            statut=(statut or BonCommandeFournisseur.Statut.ENVOYE))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            quantite_recue=quantite_recue,
            prix_achat_unitaire=Decimal('8000'))
        return bc


class Ntdst10AtpTests(Ntdst10Base):
    def test_rupture_avec_commande_confirmee_dans_5_jours(self):
        self._commande(quantite=10, confirmee_le=DANS_5_JOURS)

        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)

        self.assertEqual(res['disponible_maintenant'], 0)
        self.assertEqual(res['disponible_le'], DANS_5_JOURS.isoformat())
        self.assertEqual(res['quantite_a_cette_date'], 10)

    def test_produit_en_stock_na_pas_de_date_a_promettre(self):
        self.produit.quantite_stock = 25
        self.produit.save(update_fields=['quantite_stock'])
        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)
        self.assertEqual(res['disponible_maintenant'], 25)
        self.assertIsNone(res['disponible_le'])

    def test_une_reservation_de_chantier_reduit_le_disponible(self):
        from apps.installations.models import Installation, StockReservation

        self.produit.quantite_stock = 20
        self.produit.save(update_fields=['quantite_stock'])
        installation = Installation.objects.create(company=self.company)
        StockReservation.objects.create(
            company=self.company, installation=installation,
            produit=self.produit, quantite=8)

        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)
        self.assertEqual(res['quantite_reservee'], 8)
        self.assertEqual(res['disponible_maintenant'], 12)

    def test_une_commande_sans_date_confirmee_ne_promet_rien(self):
        self._commande(quantite=10, confirmee_le=None)
        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)
        self.assertIsNone(res['disponible_le'])

    def test_une_commande_hors_horizon_ne_promet_rien(self):
        self._commande(
            quantite=10,
            confirmee_le=AUJOURDHUI + datetime.timedelta(days=90))
        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)
        self.assertIsNone(res['disponible_le'])

    def test_lhorizon_est_configurable_par_societe(self):
        ParametresNegoce.objects.create(
            company=self.company, atp_horizon_jours=120)
        self._commande(
            quantite=10,
            confirmee_le=AUJOURDHUI + datetime.timedelta(days=90))
        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)
        self.assertIsNotNone(res['disponible_le'])

    def test_une_commande_annulee_ne_promet_rien(self):
        self._commande(
            quantite=10, confirmee_le=DANS_5_JOURS,
            statut=BonCommandeFournisseur.Statut.ANNULE)
        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)
        self.assertIsNone(res['disponible_le'])

    def test_une_ligne_deja_entierement_recue_ne_promet_rien(self):
        self._commande(quantite=10, quantite_recue=10,
                       confirmee_le=DANS_5_JOURS)
        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)
        self.assertIsNone(res['disponible_le'])

    def test_la_premiere_date_confirmee_gagne(self):
        self._commande(
            quantite=4,
            confirmee_le=AUJOURDHUI + datetime.timedelta(days=20))
        self._commande(quantite=7, confirmee_le=DANS_5_JOURS)
        res = atp_produit(self.company, self.produit, aujourdhui=AUJOURDHUI)
        self.assertEqual(res['disponible_le'], DANS_5_JOURS.isoformat())
        self.assertEqual(res['quantite_a_cette_date'], 7)

    def test_aucune_commande_dune_autre_societe(self):
        self._commande(quantite=10, confirmee_le=DANS_5_JOURS)
        autre_produit = Produit.objects.create(
            company=self.autre, nom='Voisin', sku='VOISIN-DST10',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=0)
        res = atp_produit(self.autre, autre_produit, aujourdhui=AUJOURDHUI)
        self.assertIsNone(res['disponible_le'])


class Ntdst10ApiTests(Ntdst10Base):
    def test_endpoint_atp_du_produit(self):
        self._commande(quantite=10, confirmee_le=DANS_5_JOURS)
        res = auth(self.admin).get(
            f'/api/django/stock/produits/{self.produit.id}/atp/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['disponible_maintenant'], 0)
        self.assertIn('disponible_le', res.data)

    def test_endpoint_natteint_jamais_le_prix_dachat(self):
        res = auth(self.admin).get(
            f'/api/django/stock/produits/{self.produit.id}/atp/')
        self.assertNotIn('prix_achat', res.data)

    def test_endpoint_refuse_lanonyme(self):
        res = APIClient().get(
            f'/api/django/stock/produits/{self.produit.id}/atp/')
        self.assertEqual(res.status_code, 401)
