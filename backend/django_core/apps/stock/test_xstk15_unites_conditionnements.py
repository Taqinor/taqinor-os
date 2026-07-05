"""XSTK15 — Unites de mesure & conditionnements (touret/carton...).

Couvre :
  * `Produit.unite_stock` defaut "unite" (comportement historique) ;
  * `convertir_en_unites_stock` convertit N conditionnements en unites de
    stock via le facteur (2 tourets de 100 m -> 200 m) ;
  * `resoudre_conditionnement` par id ou par code-barres scanne, scope
    societe ;
  * recevoir un BCF avec un conditionnement incremente les UNITES DE STOCK
    converties (pas le nombre de conditionnements) ;
  * sans conditionnement, comportement historique inchange (la quantite
    saisie est directement en unites de stock) ;
  * migration additive : un produit existant garde son comportement.

Run:
    python manage.py test apps.stock.test_xstk15_unites_conditionnements -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, ConditionnementProduit, Fournisseur,
    LigneBonCommandeFournisseur, Produit,
)
from apps.stock.services import (
    convertir_en_unites_stock, resoudre_conditionnement,
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


class Xstk15Base(TestCase):
    def setUp(self):
        self.company = _company('xstk15-co')
        self.user = _user(
            self.company, 'xstk15-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur câble')
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble solaire 6mm²', sku='CBL-XSTK15',
            prix_vente=Decimal('10'), prix_achat=Decimal('5'),
            unite_stock='m', quantite_stock=0)
        self.touret = ConditionnementProduit.objects.create(
            company=self.company, produit=self.cable, nom='Touret 100 m',
            facteur=Decimal('100'), code_barres='TOURET100')


class ProduitUniteStockTests(TestCase):
    def test_defaut_unite(self):
        company = _company('xstk15-defaut')
        p = Produit.objects.create(
            company=company, nom='Produit standard', sku='STD-XSTK15',
            prix_vente=Decimal('100'), prix_achat=Decimal('50'))
        self.assertEqual(p.unite_stock, 'unité')


class ConversionTests(Xstk15Base):
    def test_convertir_en_unites_stock(self):
        self.assertEqual(convertir_en_unites_stock(2, self.touret), 200)

    def test_resoudre_par_id(self):
        found = resoudre_conditionnement(
            self.company, conditionnement_id=self.touret.pk)
        self.assertEqual(found, self.touret)

    def test_resoudre_par_code_barres_scanne(self):
        found = resoudre_conditionnement(
            self.company, code_barres='TOURET100')
        self.assertEqual(found, self.touret)

    def test_resoudre_scope_societe(self):
        autre = _company('xstk15-autre')
        self.assertIsNone(
            resoudre_conditionnement(autre, conditionnement_id=self.touret.pk))

    def test_resoudre_sans_parametre(self):
        self.assertIsNone(resoudre_conditionnement(self.company))


class ReceptionAvecConditionnementTests(Xstk15Base):
    def _bcf_envoye(self, quantite_commandee):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XSTK15-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.cable, quantite=quantite_commandee,
            prix_achat_unitaire=Decimal('5'))
        return bcf, ligne

    def test_reception_avec_conditionnement_convertit(self):
        bcf, ligne = self._bcf_envoye(200)
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bcf.pk}/recevoir/',
            {'receptions': [
                {'ligne': ligne.id, 'quantite': 2,
                 'conditionnement': self.touret.pk}]},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 200)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 200)

    def test_reception_sans_conditionnement_comportement_historique(self):
        bcf, ligne = self._bcf_envoye(50)
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bcf.pk}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 50}]},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 50)

    def test_reception_conditionnement_par_code_barres_scanne(self):
        bcf, ligne = self._bcf_envoye(300)
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bcf.pk}/recevoir/',
            {'receptions': [
                {'ligne': ligne.id, 'quantite': 3,
                 'conditionnement_code_barres': 'TOURET100'}]},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 300)


class ConditionnementEndpointTests(Xstk15Base):
    def test_liste_conditionnements(self):
        resp = self.api.get(
            f'/api/django/stock/conditionnements/?produit={self.cable.pk}')
        self.assertEqual(resp.status_code, 200)
        noms = {row['nom'] for row in resp.json()['results']} \
            if isinstance(resp.json(), dict) and 'results' in resp.json() \
            else {row['nom'] for row in resp.json()}
        self.assertIn('Touret 100 m', noms)

    def test_creation_conditionnement(self):
        resp = self.api.post(
            '/api/django/stock/conditionnements/',
            {'produit': self.cable.pk, 'nom': 'Bobine 50 m',
             'facteur': '50'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['unite_stock'], 'm')
