"""ZPUR6 — Regroupement de plusieurs demandes/besoins en un seul BCF par
fournisseur (merge RFQ).

Couvre :
  * fusionner 3 BCF brouillon du même fournisseur produit UN BCF cible aux
    quantités cumulées par produit, et annule les sources avec trace ;
  * un mélange de fournisseurs est refusé (400) ;
  * un BCF non-brouillon dans la sélection est refusé (400) ;
  * multi-tenant : un id d'une autre société est refusé (introuvable).

Run:
    python manage.py test apps.stock.test_zpur6_fusionner_bcf -v 2
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


class Zpur6Base(TestCase):
    def setUp(self):
        self.company = _company('zpur6-co')
        self.user = _user(
            self.company, 'zpur6-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR6')
        self.autre_fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Autre fournisseur ZPUR6')
        self.mc4 = Produit.objects.create(
            company=self.company, nom='Connecteur MC4 ZPUR6', sku='MC4-ZPUR6',
            prix_vente=Decimal('20'), prix_achat=Decimal('5'))
        self.visserie = Produit.objects.create(
            company=self.company, nom='Visserie ZPUR6', sku='VIS-ZPUR6',
            prix_vente=Decimal('10'), prix_achat=Decimal('2'))

    def _bcf_brouillon(self, fournisseur, ref, lignes):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=ref, fournisseur=fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        for produit, qte, prix in lignes:
            bc.lignes.create(
                produit=produit, quantite=qte, prix_achat_unitaire=prix)
        return bc


class TestFusion(Zpur6Base):
    def test_fusionner_trois_bcf_cumule_par_produit(self):
        bc1 = self._bcf_brouillon(
            self.fournisseur, 'BCF-ZPUR6-1',
            [(self.mc4, 100, Decimal('5'))])
        bc2 = self._bcf_brouillon(
            self.fournisseur, 'BCF-ZPUR6-2',
            [(self.mc4, 50, Decimal('5.50')), (self.visserie, 30, Decimal('2'))])
        bc3 = self._bcf_brouillon(
            self.fournisseur, 'BCF-ZPUR6-3',
            [(self.visserie, 20, Decimal('2.10'))])

        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/fusionner/',
            {'bons_commande': [bc1.id, bc2.id, bc3.id]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        cible = BonCommandeFournisseur.objects.get(id=resp.data['id'])
        self.assertEqual(cible.statut, BonCommandeFournisseur.Statut.BROUILLON)
        ligne_mc4 = cible.lignes.get(produit=self.mc4)
        self.assertEqual(ligne_mc4.quantite, 150)  # 100 + 50
        ligne_visserie = cible.lignes.get(produit=self.visserie)
        self.assertEqual(ligne_visserie.quantite, 50)  # 30 + 20

        for bc in (bc1, bc2, bc3):
            bc.refresh_from_db()
            self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ANNULE)
            self.assertIn(cible.reference, bc.note)


class TestGardes(Zpur6Base):
    def test_melange_fournisseurs_refuse(self):
        bc1 = self._bcf_brouillon(
            self.fournisseur, 'BCF-ZPUR6-4', [(self.mc4, 10, Decimal('5'))])
        bc2 = self._bcf_brouillon(
            self.autre_fournisseur, 'BCF-ZPUR6-5',
            [(self.mc4, 10, Decimal('5'))])
        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/fusionner/',
            {'bons_commande': [bc1.id, bc2.id]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        bc1.refresh_from_db()
        bc2.refresh_from_db()
        self.assertEqual(bc1.statut, BonCommandeFournisseur.Statut.BROUILLON)
        self.assertEqual(bc2.statut, BonCommandeFournisseur.Statut.BROUILLON)

    def test_bcf_non_brouillon_refuse(self):
        bc1 = self._bcf_brouillon(
            self.fournisseur, 'BCF-ZPUR6-6', [(self.mc4, 10, Decimal('5'))])
        bc2 = self._bcf_brouillon(
            self.fournisseur, 'BCF-ZPUR6-7', [(self.mc4, 10, Decimal('5'))])
        bc2.statut = BonCommandeFournisseur.Statut.ENVOYE
        bc2.save(update_fields=['statut'])
        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/fusionner/',
            {'bons_commande': [bc1.id, bc2.id]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_moins_de_deux_bcf_refuse(self):
        bc1 = self._bcf_brouillon(
            self.fournisseur, 'BCF-ZPUR6-8', [(self.mc4, 10, Decimal('5'))])
        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/fusionner/',
            {'bons_commande': [bc1.id]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class TestMultiTenant(Zpur6Base):
    def test_bcf_autre_societe_refuse(self):
        autre = _company('zpur6-autre')
        fournisseur_autre = Fournisseur.objects.create(
            company=autre, nom='Fournisseur autre société')
        produit_autre = Produit.objects.create(
            company=autre, nom='Produit autre', sku='PRD-AUTRE-ZPUR6',
            prix_vente=Decimal('10'), prix_achat=Decimal('5'))
        bc_autre = BonCommandeFournisseur.objects.create(
            company=autre, reference='BCF-ZPUR6-AUTRE',
            fournisseur=fournisseur_autre,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        bc_autre.lignes.create(
            produit=produit_autre, quantite=5, prix_achat_unitaire=Decimal('5'))
        bc1 = self._bcf_brouillon(
            self.fournisseur, 'BCF-ZPUR6-9', [(self.mc4, 10, Decimal('5'))])

        resp = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/fusionner/',
            {'bons_commande': [bc1.id, bc_autre.id]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
