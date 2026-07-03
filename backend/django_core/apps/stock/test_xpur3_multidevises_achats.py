"""XPUR3 — Multi-devises sur les achats (imports panneaux/onduleurs).

Couvre :
  * un BCF EUR/USD affiche montants devise + contre-valeur MAD ;
  * la valorisation stock utilise la contre-valeur MAD (prix_achat_unitaire
    reste l'unique source consommée par average_cost_with_source) ;
  * fallback MAD (devise MAD / champ non renseigné = comportement inchangé) ;
  * comparatif fournisseurs normalisé MAD (déjà garanti car prix_achat_unitaire
    reste toujours en MAD).

Run:
    python manage.py test apps.stock.test_xpur3_multidevises_achats -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, DeviseAchat, Fournisseur,
    LigneBonCommandeFournisseur, Produit,
)
from apps.stock.services import (
    average_cost_with_source, contre_valeur_mad,
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


class Xpur3Base(TestCase):
    def setUp(self):
        self.company = _company('xpur3-co')
        self.user = _user(
            self.company, 'xpur3-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Import Panneaux EU')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PV-XPUR3',
            prix_vente=Decimal('1500'), prix_achat=Decimal('1000'))


class TestContreValeurMad(Xpur3Base):
    def test_conversion_basic(self):
        self.assertEqual(
            contre_valeur_mad(Decimal('100'), Decimal('10.8')),
            Decimal('1080.00'))

    def test_none_inputs_return_zero(self):
        self.assertEqual(contre_valeur_mad(None, Decimal('10')), Decimal('0'))


class TestBcfMultiDevise(Xpur3Base):
    def test_bcf_eur_line_derives_mad_contrevaleur(self):
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'devise': DeviseAchat.EUR,
            'taux_change': '10.80',
            'lignes': [{
                'produit': self.produit.id, 'quantite': 10,
                'prix_achat_unitaire_devise': '100',
                'prix_achat_unitaire': '0',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ligne = resp.data['lignes'][0]
        self.assertEqual(Decimal(ligne['prix_achat_unitaire_devise']),
                         Decimal('100.00'))
        self.assertEqual(Decimal(ligne['prix_achat_unitaire']),
                         Decimal('1080.00'))
        self.assertEqual(resp.data['devise'], 'EUR')

    def test_bcf_mad_default_unchanged(self):
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 10,
                'prix_achat_unitaire': '950',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['devise'], 'MAD')
        ligne = resp.data['lignes'][0]
        self.assertEqual(Decimal(ligne['prix_achat_unitaire']),
                         Decimal('950.00'))
        self.assertIsNone(ligne['prix_achat_unitaire_devise'])

    def test_valorisation_uses_mad_contrevaleur(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR3-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            devise=DeviseAchat.EUR, taux_change=Decimal('10.8'))
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1080.00'),
            prix_achat_unitaire_devise=Decimal('100'), quantite_recue=10)
        cout, source = average_cost_with_source(self.produit)
        self.assertEqual(source, 'achats')
        self.assertEqual(cout, Decimal('1080.00'))
        self.assertIsNotNone(ligne)


class TestFactureMultiDevise(Xpur3Base):
    def test_facture_usd_derives_mad_ttc(self):
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'devise': DeviseAchat.USD,
            'taux_change': '9.90',
            'montant_ttc_devise': '500',
            'montant_ht': '0', 'montant_tva': '0', 'montant_ttc': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['montant_ttc']), Decimal('4950.00'))
        self.assertEqual(resp.data['devise'], 'USD')

    def test_facture_mad_default_unchanged(self):
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'montant_ht': '1000', 'montant_tva': '200', 'montant_ttc': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['montant_ttc']), Decimal('1200.00'))
        self.assertEqual(resp.data['devise'], 'MAD')
