"""XSTK4 — Parsing GS1-128 / DataMatrix (GTIN + lot + péremption + série en
un scan).

Couvre :
  * décomposition d'un code GS1 mixte (AI 01/10/17/21, avec et sans FNC1
    explicite) ;
  * GTIN seul (pas d'autre AI) reste décodable ;
  * un code sans AI reconnu ne casse jamais (dégradation propre, champs
    None) ;
  * une date de péremption invalide reste None (jamais inventée) ;
  * le résolveur de scan (`produits/resolve/`) matche un GS1 composite via
    le GTIN → 404 propre si le GTIN est inconnu ;
  * l'action `receptions-fournisseur/scan-gs1/` renvoie le préremplissage
    (produit + lot + péremption + série) prêt pour la ligne de réception.

Run:
    python manage.py test apps.stock.test_xstk4_gs1 -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock import gs1
from apps.stock.models import Produit

User = get_user_model()

FNC1 = '\x1d'


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


class TestParseGs1(TestCase):
    def test_gtin_lot_peremption_serie_avec_fnc1(self):
        # 01 + GTIN(14) + 10 + lot + FNC1 + 17 + AAMMJJ + 21 + série
        code = ('01' + '04006381333931' + '10' + 'LOT42' + FNC1
                + '17' + '270615' + '21' + 'SN0007')
        fields = gs1.parse_gs1(code)
        self.assertEqual(fields['gtin'], '04006381333931')
        self.assertEqual(fields['lot'], 'LOT42')
        self.assertEqual(fields['date_peremption'], date(2027, 6, 15))
        self.assertEqual(fields['serie'], 'SN0007')

    def test_fnc1_placeholder_textuel(self):
        code = ('01' + '04006381333931' + '10' + 'LOT42' + '<GS>'
                + '21' + 'SN0007')
        fields = gs1.parse_gs1(code)
        self.assertEqual(fields['lot'], 'LOT42')
        self.assertEqual(fields['serie'], 'SN0007')

    def test_gtin_seul(self):
        code = '01' + '04006381333931'
        fields = gs1.parse_gs1(code)
        self.assertEqual(fields['gtin'], '04006381333931')
        self.assertIsNone(fields['lot'])
        self.assertIsNone(fields['date_peremption'])
        self.assertIsNone(fields['serie'])

    def test_ai_inconnu_ne_casse_jamais(self):
        fields = gs1.parse_gs1('99ABCDEF')
        self.assertIsNone(fields['gtin'])
        self.assertIsNone(fields['lot'])

    def test_chaine_vide(self):
        fields = gs1.parse_gs1('')
        self.assertEqual(
            fields, {'gtin': None, 'lot': None, 'date_peremption': None,
                     'serie': None})

    def test_date_invalide_reste_none(self):
        code = '01' + '04006381333931' + '17' + '271340'  # mois 13 invalide
        fields = gs1.parse_gs1(code)
        self.assertIsNone(fields['date_peremption'])

    def test_lot_et_serie_sans_fnc1_en_fin_de_chaine(self):
        # Dernier AI variable de la chaîne : pas de FNC1 nécessaire.
        code = '01' + '04006381333931' + '21' + 'SNLAST'
        fields = gs1.parse_gs1(code)
        self.assertEqual(fields['serie'], 'SNLAST')


class Xstk4ApiBase(TestCase):
    def setUp(self):
        self.company = _company('xstk4-co')
        self.user = _user(
            self.company, 'xstk4-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie LFP 5kWh',
            prix_vente=Decimal('8000'), code_barres='04006381333931')


class TestResolveGs1Composite(Xstk4ApiBase):
    def test_resolve_via_gtin_compose(self):
        code = ('01' + '04006381333931' + '10' + 'LOT42' + FNC1
                + '17' + '270615' + '21' + 'SN0007')
        resp = self.api.get(
            f'/api/django/stock/produits/resolve/?code={code}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['id'], self.produit.id)
        self.assertEqual(resp.data['gs1']['numero_lot'], 'LOT42')
        self.assertEqual(resp.data['gs1']['date_peremption'], '2027-06-15')
        self.assertEqual(resp.data['gs1']['numero_serie'], 'SN0007')

    def test_resolve_gtin_inconnu_404(self):
        code = '01' + '99999999999999' + '10' + 'LOTX'
        resp = self.api.get(
            f'/api/django/stock/produits/resolve/?code={code}')
        self.assertEqual(resp.status_code, 404)


class TestScanGs1Endpoint(Xstk4ApiBase):
    def test_scan_gs1_prefill(self):
        code = ('01' + '04006381333931' + '10' + 'LOT42' + FNC1
                + '17' + '270615' + '21' + 'SN0007')
        resp = self.api.get(
            f'/api/django/stock/receptions-fournisseur/scan-gs1/'
            f'?code={code}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['produit_id'], self.produit.id)
        self.assertEqual(resp.data['numero_lot'], 'LOT42')
        self.assertEqual(resp.data['date_peremption'], '2027-06-15')
        self.assertEqual(resp.data['numeros_serie'], ['SN0007'])

    def test_scan_gs1_gtin_inconnu_404(self):
        code = '01' + '99999999999999'
        resp = self.api.get(
            f'/api/django/stock/receptions-fournisseur/scan-gs1/'
            f'?code={code}')
        self.assertEqual(resp.status_code, 404)

    def test_scan_gs1_code_illisible_400(self):
        resp = self.api.get(
            '/api/django/stock/receptions-fournisseur/scan-gs1/'
            '?code=notgs1')
        self.assertEqual(resp.status_code, 400)

    def test_scan_gs1_cross_tenant_404(self):
        other = _company('xstk4-other')
        other_user = _user(other, 'xstk4-other-user')
        api = _api(other_user)
        code = '01' + '04006381333931'
        resp = api.get(
            f'/api/django/stock/receptions-fournisseur/scan-gs1/'
            f'?code={code}')
        self.assertEqual(resp.status_code, 404)
