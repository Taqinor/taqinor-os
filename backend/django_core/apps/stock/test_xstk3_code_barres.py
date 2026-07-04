"""XSTK3 — Code-barres fabricant (EAN/UPC) sur Produit + résolution au scan.

Couvre :
  * `Produit.code_barres` optionnel, nullable, non exigé (comportement
    historique inchangé pour un produit sans code-barres) ;
  * unicité PAR SOCIÉTÉ quand renseigné : deux produits, même société, même
    code-barres → 400 propre à la création (jamais une IntegrityError 500) ;
    même code-barres, sociétés DIFFÉRENTES → autorisé ;
  * le résolveur de scan (`produits/resolve/`) matche d'abord les jetons
    internes `PRODUIT:<id>`, puis (si le code n'a pas de ':') tente
    `code_barres` — scopé société, jamais cross-tenant ;
  * un code-barres inconnu → 404 propre (jamais 400).

Run:
    python manage.py test apps.stock.test_xstk3_code_barres -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import Produit

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


class Xstk3Base(TestCase):
    def setUp(self):
        self.company = _company('xstk3-co')
        self.user = _user(
            self.company, 'xstk3-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN550',
            prix_vente=Decimal('200'), code_barres='4006381333931')


class TestModelUniqueness(Xstk3Base):
    def test_sans_code_barres_reste_valide(self):
        p = Produit.objects.create(
            company=self.company, nom='Sans EAN', prix_vente=Decimal('10'))
        self.assertIsNone(p.code_barres)

    def test_meme_code_barres_deux_societes_autorise(self):
        other = _company('xstk3-other')
        p = Produit.objects.create(
            company=other, nom='Autre société', prix_vente=Decimal('10'),
            code_barres='4006381333931')
        self.assertEqual(p.code_barres, '4006381333931')

    def test_doublon_meme_societe_leve_integrity_error(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Produit.objects.create(
                    company=self.company, nom='Doublon EAN',
                    prix_vente=Decimal('10'), code_barres='4006381333931')


class TestSerializerValidation(Xstk3Base):
    def test_creation_avec_code_barres_unique_ok(self):
        resp = self.api.post('/api/django/stock/produits/', {
            'nom': 'Onduleur 10kW', 'prix_vente': '1500',
            'code_barres': '5901234123457',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['code_barres'], '5901234123457')

    def test_creation_doublon_meme_societe_rejetee_400(self):
        resp = self.api.post('/api/django/stock/produits/', {
            'nom': 'Doublon', 'prix_vente': '10',
            'code_barres': '4006381333931',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_creation_sans_code_barres_ok(self):
        resp = self.api.post('/api/django/stock/produits/', {
            'nom': 'Sans EAN', 'prix_vente': '10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['code_barres'])


class TestResolveByCodeBarres(Xstk3Base):
    def test_scanner_ean_ouvre_le_bon_produit(self):
        resp = self.api.get(
            '/api/django/stock/produits/resolve/'
            '?code=4006381333931')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['type'], 'produit')
        self.assertEqual(resp.data['id'], self.produit.id)
        self.assertEqual(resp.data['route'], '/stock')

    def test_ean_inconnu_404(self):
        resp = self.api.get(
            '/api/django/stock/produits/resolve/?code=0000000000000')
        self.assertEqual(resp.status_code, 404)

    def test_ean_cross_tenant_404(self):
        other = _company('xstk3-other2')
        other_user = _user(other, 'xstk3-other-user')
        api = _api(other_user)
        resp = api.get(
            '/api/django/stock/produits/resolve/'
            '?code=4006381333931')
        self.assertEqual(resp.status_code, 404)

    def test_jeton_interne_reste_prioritaire(self):
        # PRODUIT:<id> continue de résoudre par id, indépendamment du
        # code-barres (comportement historique inchangé).
        resp = self.api.get(
            f'/api/django/stock/produits/resolve/'
            f'?code=PRODUIT:{self.produit.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['id'], self.produit.id)
