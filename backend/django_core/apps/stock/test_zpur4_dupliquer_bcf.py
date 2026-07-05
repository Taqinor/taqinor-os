"""ZPUR4 — Duplication d'un bon de commande fournisseur.

Couvre :
  * dupliquer un BCF reçu produit un nouveau brouillon aux mêmes lignes,
    référence neuve, zéro quantité reçue ;
  * la source reste intacte (statut, quantités reçues inchangés) ;
  * cross-company → 404.

Run:
    python manage.py test apps.stock.test_zpur4_dupliquer_bcf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit

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


class Zpur4Base(TestCase):
    def setUp(self):
        self.company = _company('zpur4-co')
        self.user = _user(
            self.company, 'zpur4-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR4')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ZPUR4', sku='OND-ZPUR4',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf_recu(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR4-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        bc.lignes.create(
            produit=self.produit, quantite=10, quantite_recue=10,
            prix_achat_unitaire=Decimal('100'))
        return bc


class TestDuplication(Zpur4Base):
    def test_dupliquer_bcf_recu_produit_brouillon_meme_lignes(self):
        bc = self._bcf_recu()
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/dupliquer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        clone = BonCommandeFournisseur.objects.get(id=resp.data['id'])
        self.assertNotEqual(clone.reference, bc.reference)
        self.assertEqual(clone.statut, BonCommandeFournisseur.Statut.BROUILLON)
        self.assertEqual(clone.fournisseur_id, bc.fournisseur_id)
        self.assertEqual(clone.lignes.count(), 1)
        ligne_clone = clone.lignes.first()
        self.assertEqual(ligne_clone.produit_id, self.produit.id)
        self.assertEqual(ligne_clone.quantite, 10)
        self.assertEqual(ligne_clone.prix_achat_unitaire, Decimal('100'))
        self.assertEqual(ligne_clone.quantite_recue, 0)

    def test_source_reste_intacte(self):
        bc = self._bcf_recu()
        self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/dupliquer/')
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.RECU)
        ligne = bc.lignes.first()
        self.assertEqual(ligne.quantite_recue, 10)


class TestMultiTenant(Zpur4Base):
    def test_dupliquer_bcf_autre_societe_404(self):
        autre = _company('zpur4-autre')
        autre_user = _user(
            autre, 'zpur4-autre-user',
            permissions=['stock_modifier', 'stock_voir'])
        autre_api = _api(autre_user)
        bc = self._bcf_recu()
        resp = autre_api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/dupliquer/')
        self.assertEqual(resp.status_code, 404)
