"""ZSTK7 — Rapport « historique des mouvements » groupable/croisé
(Reporting ▸ Moves History).

Couvre :
  * l'agrégation par produit sur une période somme correctement entrées/
    sorties/net ;
  * group_by inconnu → 400 propre ;
  * l'export xlsx télécharge (content-type xlsx) ;
  * cross-tenant isolé (les mouvements d'une autre société n'apparaissent
    jamais).

Run:
    python manage.py test apps.stock.test_zstk7_mouvements_agregation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import MouvementStock, Produit
from apps.stock.selectors import mouvements_agreges

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


class Zstk7Base(TestCase):
    def setUp(self):
        self.company = _company('zstk7-co')
        self.user = _user(
            self.company, 'zstk7-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ZSTK7', sku='PAN-ZSTK7',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            quantite_stock=100)

    def _mouvement(self, type_mouvement, quantite):
        return MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=type_mouvement, quantite=quantite,
            quantite_avant=0, quantite_apres=quantite)


class TestAgregationParProduit(Zstk7Base):
    def test_somme_entrees_sorties_net(self):
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 50)
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 30)
        self._mouvement(MouvementStock.TypeMouvement.SORTIE, 20)
        rows = mouvements_agreges(self.company, group_by='produit')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['entrees'], 80)
        self.assertEqual(row['sorties'], 20)
        self.assertEqual(row['net'], 60)

    def test_group_by_type(self):
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 10)
        self._mouvement(MouvementStock.TypeMouvement.SORTIE, 4)
        rows = mouvements_agreges(self.company, group_by='type')
        libelles = {r['libelle'] for r in rows}
        self.assertIn('Entrée', libelles)
        self.assertIn('Sortie', libelles)

    def test_group_by_mois(self):
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 10)
        rows = mouvements_agreges(self.company, group_by='mois')
        self.assertEqual(len(rows), 1)

    def test_group_by_emplacement(self):
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 10)
        rows = mouvements_agreges(self.company, group_by='emplacement')
        self.assertTrue(rows)
        total_entrees = sum(r['entrees'] for r in rows)
        self.assertAlmostEqual(total_entrees, 10, places=6)

    def test_group_by_inconnu_leve_valueerror(self):
        with self.assertRaises(ValueError):
            mouvements_agreges(self.company, group_by='n_importe_quoi')

    def test_cross_tenant_isole(self):
        other = _company('zstk7-autre')
        other_produit = Produit.objects.create(
            company=other, nom='Autre produit', sku='PAN-ZSTK7-AUTRE',
            prix_vente=Decimal('500'))
        MouvementStock.objects.create(
            company=other, produit=other_produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=999, quantite_avant=0, quantite_apres=999)
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 10)
        rows = mouvements_agreges(self.company, group_by='produit')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['entrees'], 10)


class TestEndpoint(Zstk7Base):
    def test_endpoint_agregation_produit(self):
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 25)
        url = '/api/django/stock/mouvements/agregation/?group_by=produit'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['entrees'], 25)

    def test_endpoint_group_by_inconnu_400(self):
        url = '/api/django/stock/mouvements/agregation/?group_by=n_importe_quoi'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_export_xlsx(self):
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 25)
        url = (
            '/api/django/stock/mouvements/agregation/'
            '?group_by=produit&export=xlsx')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])
