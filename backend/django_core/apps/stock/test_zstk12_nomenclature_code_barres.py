"""ZSTK12 — Nomenclature de code-barres configurable (Default/GS1) par
société.

Couvre :
  * sans nomenclature définie, le scan se comporte comme aujourd'hui
    (résolution EAN/GTIN par `code_barres`, non-régression) ;
  * une règle « préfixe 22 = emplacement » fait résoudre un code 22xxxx
    vers l'emplacement correspondant ;
  * les règles sont triées par priorité (la première qui matche gagne) ;
  * une nomenclature INACTIVE n'affecte jamais le résolveur (repli
    historique) ;
  * cross-company : la nomenclature d'une société n'affecte jamais une
    autre société.

Run:
    python manage.py test \
        apps.stock.test_zstk12_nomenclature_code_barres -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    EmplacementStock, NomenclatureCodeBarres, Produit, RegleCodeBarres,
)
from apps.stock.selectors import resolve_via_nomenclature

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


class Zstk12Base(TestCase):
    def setUp(self):
        self.company = _company('zstk12-co')
        self.user = _user(
            self.company, 'zstk12-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ZSTK12', sku='PAN-ZSTK12',
            prix_vente=Decimal('2000'), code_barres='4006381333931')
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt secondaire ZSTK12')


class TestSansNomenclatureRepliHistorique(Zstk12Base):
    def test_scan_ean_sans_nomenclature_resout_produit(self):
        url = (
            '/api/django/stock/produits/resolve/'
            '?code=4006381333931')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['type'], 'produit')
        self.assertEqual(resp.data['id'], self.produit.id)

    def test_selector_sans_nomenclature_renvoie_none(self):
        result = resolve_via_nomenclature(self.company, '224006381333931')
        self.assertIsNone(result)


class TestReglePrefixeEmplacement(Zstk12Base):
    def setUp(self):
        super().setUp()
        self.nomenclature = NomenclatureCodeBarres.objects.create(
            company=self.company, nom='Interne ZSTK12', actif=True)
        RegleCodeBarres.objects.create(
            nomenclature=self.nomenclature, motif='22',
            encode=RegleCodeBarres.Encode.EMPLACEMENT, priorite=10)

    def test_selector_matche_prefixe_emplacement(self):
        code = f'22{self.emplacement.id}'
        result = resolve_via_nomenclature(self.company, code)
        self.assertIsNotNone(result)
        encode, regle = result
        self.assertEqual(encode, RegleCodeBarres.Encode.EMPLACEMENT)

    def test_endpoint_resout_emplacement_via_regle(self):
        code = f'22{self.emplacement.id}'
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['type'], 'emplacement')
        self.assertEqual(resp.data['id'], self.emplacement.id)

    def test_code_ne_matchant_aucune_regle_repli_historique(self):
        # Code EAN normal (pas de préfixe 22) : comportement historique.
        url = (
            '/api/django/stock/produits/resolve/'
            '?code=4006381333931')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['type'], 'produit')


class TestNomenclatureInactiveNoOp(Zstk12Base):
    def test_nomenclature_inactive_jamais_consultee(self):
        nomenclature = NomenclatureCodeBarres.objects.create(
            company=self.company, nom='Interne inactive', actif=False)
        RegleCodeBarres.objects.create(
            nomenclature=nomenclature, motif='22',
            encode=RegleCodeBarres.Encode.EMPLACEMENT, priorite=10)
        code = f'22{self.emplacement.id}'
        result = resolve_via_nomenclature(self.company, code)
        self.assertIsNone(result)


class TestPrioriteRegles(Zstk12Base):
    def test_regle_priorite_plus_basse_gagne(self):
        nomenclature = NomenclatureCodeBarres.objects.create(
            company=self.company, nom='Interne priorite', actif=True)
        RegleCodeBarres.objects.create(
            nomenclature=nomenclature, motif='2', est_regex=False,
            encode=RegleCodeBarres.Encode.PRODUIT, priorite=50)
        RegleCodeBarres.objects.create(
            nomenclature=nomenclature, motif='22',
            encode=RegleCodeBarres.Encode.EMPLACEMENT, priorite=5)
        code = f'22{self.emplacement.id}'
        result = resolve_via_nomenclature(self.company, code)
        encode, regle = result
        self.assertEqual(encode, RegleCodeBarres.Encode.EMPLACEMENT)
        self.assertEqual(regle.priorite, 5)


class TestCrossCompany(Zstk12Base):
    def test_nomenclature_autre_societe_non_appliquee(self):
        other_co = _company('zstk12-autre')
        nomenclature = NomenclatureCodeBarres.objects.create(
            company=other_co, nom='Autre société', actif=True)
        RegleCodeBarres.objects.create(
            nomenclature=nomenclature, motif='22',
            encode=RegleCodeBarres.Encode.EMPLACEMENT, priorite=10)
        code = f'22{self.emplacement.id}'
        result = resolve_via_nomenclature(self.company, code)
        self.assertIsNone(result)
