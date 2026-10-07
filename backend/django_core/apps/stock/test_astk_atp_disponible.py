"""ASTK100 + ASTK101 — ATP : disponible aligné sur la liste, arrivée due.

Run :
    python manage.py test apps.stock.test_astk_atp_disponible -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BlocageQualite, BonCommandeFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, Produit,
)
from apps.stock.selectors_negoce import atp_produit
from authentication.models import Company

User = get_user_model()

AUJOURD = datetime.date(2026, 6, 1)


class _Base(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='astk100-co', defaults={'nom': 'ASTK100 Co'})
        self.user = User.objects.create_user(
            username='astk100_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four ASTK100')
        self._seq = 0

    def _produit(self, stock, sku='P-ASTK100'):
        return Produit.objects.create(
            company=self.company, nom=f'Produit {sku}', sku=sku,
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=stock)

    def _reserver_chantier(self, produit, quantite):
        from apps.installations.models import Installation, StockReservation
        installation = Installation.objects.create(company=self.company)
        StockReservation.objects.create(
            company=self.company, installation=installation,
            produit=produit, quantite=quantite)

    def _reserver_assemblage(self, produit, quantite):
        from apps.installations.models import (
            Kit, OrdreAssemblage, ReservationAssemblage,
        )
        compose = self._produit(0, sku='KIT-ASTK100')
        kit = Kit.objects.create(
            company=self.company, nom='Kit ASTK100', produit_compose=compose)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ASTK100', kit=kit,
            quantite=1)
        ReservationAssemblage.objects.create(
            company=self.company, ordre=ordre, produit=produit,
            quantite=quantite)

    def _commande(self, produit, quantite, jours):
        self._seq += 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK100-{self._seq:03d}',
            fournisseur=self.fournisseur, date_commande=AUJOURD,
            date_confirmee_fournisseur=AUJOURD + datetime.timedelta(
                days=jours),
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=produit, quantite=quantite,
            prix_achat_unitaire=Decimal('10'))


class AtpDisponibleTests(_Base):
    def test_atp_compte_assemblage(self):
        produit = self._produit(30)
        self._reserver_chantier(produit, 20)
        self._reserver_assemblage(produit, 3)
        atp = atp_produit(self.company, produit, aujourdhui=AUJOURD)
        self.assertEqual(atp['quantite_reservee'], 23)
        self.assertEqual(atp['disponible_maintenant'], 7)
        liste = self.api.get('/api/django/stock/produits/').json()
        lignes = liste['results'] if isinstance(liste, dict) else liste
        ligne = next(x for x in lignes if x['id'] == produit.id)
        self.assertEqual(ligne['quantite_reservee'], 23)
        self.assertEqual(ligne['quantite_disponible'],
                         atp['disponible_maintenant'])

    def test_atp_deduit_quarantaine(self):
        produit = self._produit(5, sku='Q-ASTK100')
        BlocageQualite.objects.create(
            company=self.company, produit=produit, quantite=5,
            statut=BlocageQualite.Statut.EN_QUARANTAINE)
        atp = atp_produit(self.company, produit, aujourdhui=AUJOURD)
        self.assertEqual(atp['disponible_maintenant'], 0)
        liste = self.api.get('/api/django/stock/produits/').json()
        lignes = liste['results'] if isinstance(liste, dict) else liste
        ligne = next(x for x in lignes if x['id'] == produit.id)
        self.assertEqual(ligne['quantite_disponible'], 0)


class AtpDateTests(_Base):
    def test_reliquat_deja_du_n_est_pas_promis(self):
        produit = self._produit(5, sku='D-ASTK100')
        self._reserver_chantier(produit, 20)
        self._commande(produit, 15, 3)
        atp = atp_produit(self.company, produit, aujourdhui=AUJOURD)
        self.assertEqual(atp['quantite_a_cette_date'], 0)
        self.assertIsNone(atp['disponible_le'])

        self._commande(produit, 10, 7)
        atp = atp_produit(self.company, produit, aujourdhui=AUJOURD)
        self.assertEqual(
            atp['disponible_le'],
            (AUJOURD + datetime.timedelta(days=7)).isoformat())
        self.assertEqual(atp['quantite_a_cette_date'], 10)
