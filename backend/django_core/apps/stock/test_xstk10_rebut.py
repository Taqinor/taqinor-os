"""XSTK10 — Flux de casse / mise au rebut du stock.

Couvre :
  * `rebuter_produit` décrémente le stock, journalise motif + auteur +
    valeur perdue (coût moyen) dans un MouvementStock REBUT ;
  * un motif manquant / invalide est refusé ;
  * l'action `produits/{id}/rebuter/` (motif obligatoire) crée le rebut et
    renvoie la valeur perdue ;
  * un rebut respecte le garde XSTK8 (stock négatif refusé par défaut) ;
  * un rebut décrémente aussi l'emplacement source (N15) quand fourni ;
  * le rapport « pertes de la période » agrège quantité ET valeur par motif ;
  * l'endpoint du rapport est réservé admin (403 sinon).

Run:
    python manage.py test apps.stock.test_xstk10_rebut -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit,
)
from apps.stock.services import (
    ensure_emplacements, rapport_pertes, rebuter_produit,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None, role_legacy='responsable'):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xstk10Base(TestCase):
    def setUp(self):
        self.company = _company('xstk10-co')
        self.user = _user(
            self.company, 'xstk10-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.admin = _user(
            self.company, 'xstk10-admin', role_legacy='admin')
        self.api = _api(self.user)
        self.admin_api = _api(self.admin)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau X10', sku='PAN-X10',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'),
            quantite_stock=10)


class TestRebuterProduitService(Xstk10Base):
    def test_rebut_decremente_stock_et_journalise(self):
        result = rebuter_produit(
            company=self.company, produit=self.produit, quantite=3,
            motif='casse', user=self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 7)
        mvt = result['mouvement']
        self.assertEqual(mvt.type_mouvement, MouvementStock.TypeMouvement.REBUT)
        self.assertEqual(mvt.motif_rebut, 'casse')
        self.assertEqual(mvt.created_by_id, self.user.id)
        self.assertEqual(result['valeur_perdue'], Decimal('3000'))

    def test_motif_invalide_refuse(self):
        with self.assertRaises(ValueError):
            rebuter_produit(
                company=self.company, produit=self.produit, quantite=1,
                motif='inconnu', user=self.user)

    def test_quantite_invalide_refusee(self):
        with self.assertRaises(ValueError):
            rebuter_produit(
                company=self.company, produit=self.produit, quantite=0,
                motif='casse', user=self.user)

    def test_rebut_respecte_garde_stock_negatif(self):
        with self.assertRaises(ValueError):
            rebuter_produit(
                company=self.company, produit=self.produit, quantite=99,
                motif='casse', user=self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)  # inchangé

    def test_rebut_decremente_emplacement_source(self):
        ensure_emplacements(self.company)
        depot_b = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt B X10', is_principal=False,
            ordre=20)
        from apps.stock.models import StockEmplacement
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=depot_b, quantite=4)
        rebuter_produit(
            company=self.company, produit=self.produit, quantite=2,
            motif='vol', user=self.user, emplacement=depot_b)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=depot_b)
        self.assertEqual(se.quantite, 2)


class TestRapportPertes(Xstk10Base):
    def test_rapport_agrege_quantite_et_valeur_par_motif(self):
        rebuter_produit(
            company=self.company, produit=self.produit, quantite=2,
            motif='casse', user=self.user)
        rebuter_produit(
            company=self.company, produit=self.produit, quantite=1,
            motif='perime', user=self.user)
        rapport = rapport_pertes(self.company)
        self.assertEqual(len(rapport), 1)
        entry = rapport[0]
        self.assertEqual(entry['quantite_totale'], 3)
        self.assertEqual(entry['valeur_totale'], Decimal('3000'))
        self.assertEqual(entry['par_motif']['casse']['quantite'], 2)
        self.assertEqual(entry['par_motif']['perime']['quantite'], 1)


class TestEndpoints(Xstk10Base):
    def test_endpoint_rebuter_cree_et_renvoie_valeur(self):
        resp = self.api.post(
            f'/api/django/stock/produits/{self.produit.id}/rebuter/',
            {'quantite': 3, 'motif': 'obsolete'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['valeur_perdue'], '3000')
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 7)

    def test_endpoint_rebuter_sans_motif_400(self):
        resp = self.api.post(
            f'/api/django/stock/produits/{self.produit.id}/rebuter/',
            {'quantite': 1}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_rebuter_stock_insuffisant_400(self):
        resp = self.api.post(
            f'/api/django/stock/produits/{self.produit.id}/rebuter/',
            {'quantite': 999, 'motif': 'casse'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_rapport_pertes_admin_only(self):
        rebuter_produit(
            company=self.company, produit=self.produit, quantite=2,
            motif='casse', user=self.user)
        resp = self.admin_api.get(
            '/api/django/stock/produits/rapport-pertes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data[0]['quantite_totale'], 2)

    def test_endpoint_rapport_pertes_non_admin_403(self):
        resp = self.api.get('/api/django/stock/produits/rapport-pertes/')
        self.assertEqual(resp.status_code, 403)
