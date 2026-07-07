"""ZSTK3 — Rapport prévisionnel par produit (disponible + entrant + sortant
→ projeté).

Couvre :
  * un produit avec 1 BCF ouvert de +50 et des réservations chantier de -20
    rend un solde projeté correct daté ;
  * un produit sans mouvement à venir rend le solde plat (= disponible) ;
  * cross-tenant isolé (produit d'une autre société → 404 sur l'endpoint) ;
  * lecture via `installations.selectors` (jamais son modèle) — vérifié
    indirectement par l'absence d'ImportError et le calcul correct.

Run:
    python manage.py test apps.stock.test_zstk3_forecast_produit -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.stock.services import forecast_produit

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Zstk3Base(TestCase):
    def setUp(self):
        self.company = _company('zstk3-co')
        self.user = _user(
            self.company, 'zstk3-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZSTK3')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ZSTK3', sku='PAN-ZSTK3',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            quantite_stock=10)


class TestCalculForecast(Zstk3Base):
    def test_sans_mouvement_solde_plat(self):
        result = forecast_produit(self.company, self.produit)
        self.assertEqual(result['disponible'], 10)
        self.assertEqual(result['solde_projete'], 10)
        self.assertEqual(result['entrees_attendues'], [])
        self.assertEqual(result['sorties_attendues'], 0)

    def test_bcf_ouvert_augmente_le_projete(self):
        demain = timezone.now().date() + timedelta(days=3)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZSTK3-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=demain)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=50,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=0)
        result = forecast_produit(self.company, self.produit)
        self.assertEqual(result['disponible'], 10)
        self.assertEqual(len(result['entrees_attendues']), 1)
        self.assertEqual(
            result['entrees_attendues'][0]['quantite_restante'], 50)
        self.assertEqual(result['solde_projete'], 10 + 50)

    def test_reservations_chantier_diminuent_le_projete(self):
        from apps.installations.models import Installation, StockReservation

        # Deux chantiers distincts réservent le même produit — une seule
        # réservation par (installation, produit) est autorisée
        # (`unique_together`), donc deux réservations sur LE MÊME chantier
        # ne peuvent pas coexister ; on utilise deux installations.
        installation1 = Installation.objects.create(
            company=self.company, reference='CH-ZSTK3-0001')
        installation2 = Installation.objects.create(
            company=self.company, reference='CH-ZSTK3-0002')
        StockReservation.objects.create(
            company=self.company, installation=installation1,
            produit=self.produit, quantite=12, active=True, consomme=False)
        StockReservation.objects.create(
            company=self.company, installation=installation2,
            produit=self.produit, quantite=8, active=True, consomme=False)
        result = forecast_produit(self.company, self.produit)
        self.assertEqual(result['sorties_attendues'], 20)
        self.assertEqual(result['solde_projete'], 10 - 20)

    def test_bcf_plus_reservations_combine(self):
        from apps.installations.models import Installation, StockReservation

        demain = timezone.now().date() + timedelta(days=3)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZSTK3-0002',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=demain)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=50,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=0)
        installation = Installation.objects.create(
            company=self.company, reference='CH-ZSTK3-0002')
        StockReservation.objects.create(
            company=self.company, installation=installation,
            produit=self.produit, quantite=20, active=True, consomme=False)
        result = forecast_produit(self.company, self.produit)
        # disponible(10) + entrant(50) - sortant(20) = 40.
        self.assertEqual(result['solde_projete'], 40)


class TestEndpoint(Zstk3Base):
    def test_endpoint_previsionnel(self):
        url = f'/api/django/stock/produits/{self.produit.id}/previsionnel/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['produit_id'], self.produit.id)
        self.assertIn('solde_projete', resp.data)

    def test_cross_company_404(self):
        other_co = _company('zstk3-autre')
        other_user = _user(
            other_co, 'zstk3-autre-user',
            permissions=['stock_modifier', 'stock_voir'])
        other_api = _api(other_user)
        url = f'/api/django/stock/produits/{self.produit.id}/previsionnel/'
        resp = other_api.get(url)
        self.assertEqual(resp.status_code, 404)
