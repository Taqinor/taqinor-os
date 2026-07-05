"""ZPUR1 — Politique de facturation par produit/fournisseur (à la commande
vs à la réception, parité Odoo « Bill Control »).

Couvre :
  * un BCF de produits « sur_commande » se facture directement, SANS
    réception (`bons-commande-fournisseur/{id}/facturer/`) ;
  * un BCF de produits « sur_reception » (défaut) reste bloqué sur ce chemin
    direct — il doit passer par FG56 ;
  * une facture n'est jamais générée deux fois pour la même quantité
    (idempotence) ;
  * les deux politiques cohabitent sur le même BCF (lignes mixtes) sans que
    les lignes sur_reception soient facturées par ce chemin ;
  * multi-tenant : un BCF d'une autre société → 404.

Run:
    python manage.py test \
        apps.stock.test_zpur1_politique_facturation_achat -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur, Produit,
)
from apps.stock.services import facturer_bcf_sur_commande

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


class Zpur1Base(TestCase):
    def setUp(self):
        self.company = _company('zpur1-co')
        self.user = _user(
            self.company, 'zpur1-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR1')
        self.produit_commande = Produit.objects.create(
            company=self.company, nom='Import ZPUR1', sku='IMP-ZPUR1',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            politique_facturation_achat=(
                Produit.PolitiqueFacturationAchat.SUR_COMMANDE))
        self.produit_reception = Produit.objects.create(
            company=self.company, nom='Standard ZPUR1', sku='STD-ZPUR1',
            prix_vente=Decimal('500'), prix_achat=Decimal('200'))

    def _bcf(self, lignes):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR1-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        for produit, qte, prix in lignes:
            bc.lignes.create(
                produit=produit, quantite=qte, prix_achat_unitaire=prix)
        return bc


class TestFacturationDirecteSurCommande(Zpur1Base):
    def test_bcf_sur_commande_se_facture_sans_reception(self):
        bc = self._bcf([(self.produit_commande, 10, Decimal('100'))])
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/facturer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(str(resp.data['montant_ht'])), Decimal('1000'))

    def test_bcf_sur_reception_seul_refuse_facturation_directe(self):
        bc = self._bcf([(self.produit_reception, 5, Decimal('200'))])
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/facturer/')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_idempotence_pas_de_double_facturation(self):
        bc = self._bcf([(self.produit_commande, 10, Decimal('100'))])
        facturer_bcf_sur_commande(self.company, self.user, bc)
        with self.assertRaises(ValueError):
            facturer_bcf_sur_commande(self.company, self.user, bc)
        self.assertEqual(
            FactureFournisseur.objects.filter(bon_commande=bc).count(), 1)

    def test_lignes_mixtes_ne_facture_que_sur_commande(self):
        bc = self._bcf([
            (self.produit_commande, 10, Decimal('100')),
            (self.produit_reception, 5, Decimal('200')),
        ])
        facture = facturer_bcf_sur_commande(self.company, self.user, bc)
        # Seule la ligne sur_commande (10 x 100 = 1000) entre dans la
        # facture — la ligne sur_reception (5 x 200 = 1000) reste hors de
        # ce chemin, réservée à FG56.
        self.assertEqual(facture.montant_ht, Decimal('1000'))
        self.assertEqual(facture.lignes.count(), 1)


class TestMultiTenant(Zpur1Base):
    def test_bcf_autre_societe_404(self):
        autre = _company('zpur1-autre')
        autre_user = _user(
            autre, 'zpur1-autre-user',
            permissions=['stock_modifier', 'stock_voir'])
        autre_api = _api(autre_user)
        bc = self._bcf([(self.produit_commande, 10, Decimal('100'))])
        resp = autre_api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/facturer/')
        self.assertEqual(resp.status_code, 404)
