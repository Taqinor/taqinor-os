"""XPUR4 — Statuts fournisseur actif / bloqué commandes / bloqué paiements.

Couvre :
  * les 4 statuts (actif/bloque_commandes/bloque_paiements/bloque_total) ;
  * un BCF vers bloque_commandes|bloque_total refusé (400, message FR) ;
  * un PaiementFournisseur vers bloque_paiements|bloque_total refusé ;
  * fournisseurs existants restent 'actif' (compat) ;
  * multi-tenant.

Run:
    python manage.py test apps.stock.test_xpur4_statut_fournisseur -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import FactureFournisseur, Fournisseur, Produit
from apps.stock.services import (
    check_fournisseur_statut_commande, check_fournisseur_statut_paiement,
)

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


class Xpur4Base(TestCase):
    def setUp(self):
        self.company = _company('xpur4-co')
        self.user = _user(
            self.company, 'xpur4-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-XPUR4',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))


class TestDefaultStatutCompat(Xpur4Base):
    def test_new_fournisseur_defaults_to_actif(self):
        f = Fournisseur.objects.create(company=self.company, nom='Défaut')
        self.assertEqual(f.statut, Fournisseur.Statut.ACTIF)
        # No exception raised for an active supplier.
        check_fournisseur_statut_commande(f)
        check_fournisseur_statut_paiement(f)


class TestBcfBlockedStatuses(Xpur4Base):
    def _bcf_payload(self, fournisseur):
        return {
            'fournisseur': fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '1200',
            }],
        }

    def test_bloque_commandes_refuses_bcf(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Bloqué Commandes',
            statut=Fournisseur.Statut.BLOQUE_COMMANDES,
            motif_blocage='Litige qualité')
        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/',
            self._bcf_payload(f), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Litige qualité', resp.data['detail'])

    def test_bloque_total_refuses_bcf(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Bloqué Total',
            statut=Fournisseur.Statut.BLOQUE_TOTAL)
        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/',
            self._bcf_payload(f), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_bloque_paiements_allows_bcf(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Bloqué Paiements Only',
            statut=Fournisseur.Statut.BLOQUE_PAIEMENTS)
        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/',
            self._bcf_payload(f), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_actif_allows_bcf(self):
        f = Fournisseur.objects.create(company=self.company, nom='Actif')
        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/',
            self._bcf_payload(f), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestPaiementBlockedStatuses(Xpur4Base):
    def _facture(self, fournisseur):
        return FactureFournisseur.objects.create(
            company=self.company, reference=f'FF-XPUR4-{fournisseur.id}',
            fournisseur=fournisseur, montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))

    def test_bloque_paiements_refuses_payment(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Bloqué Paiements',
            statut=Fournisseur.Statut.BLOQUE_PAIEMENTS)
        facture = self._facture(f)
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_bloque_total_refuses_payment(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Bloqué Total 2',
            statut=Fournisseur.Statut.BLOQUE_TOTAL)
        facture = self._facture(f)
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_bloque_commandes_allows_payment(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Bloqué Commandes Only',
            statut=Fournisseur.Statut.BLOQUE_COMMANDES)
        facture = self._facture(f)
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_actif_allows_payment(self):
        f = Fournisseur.objects.create(company=self.company, nom='Actif Pay')
        facture = self._facture(f)
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestMultiTenant(Xpur4Base):
    def test_statut_scoped_to_company(self):
        other_company = _company('xpur4-co-2')
        f = Fournisseur.objects.create(
            company=other_company, nom='Autre Société',
            statut=Fournisseur.Statut.BLOQUE_TOTAL)
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': f.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 1,
                'prix_achat_unitaire': '100',
            }],
        }, format='json')
        # Le sérialiseur rejette déjà un fournisseur hors société (400) —
        # jamais un cross-tenant.
        self.assertEqual(resp.status_code, 400, resp.data)
