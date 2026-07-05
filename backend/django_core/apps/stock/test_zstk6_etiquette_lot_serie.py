"""ZSTK6 — Étiquette lot/série scannable + intégration au registre entrepôt.

Couvre :
  * une réception à N séries imprime N étiquettes scannables (planche) ;
  * une réception avec un lot imprime son étiquette ;
  * scanner un jeton LOT ouvre le `LotEntrepot` correspondant (via
    `produits/resolve/`) ;
  * scanner un jeton SERIE ouvre le `SerieEntrepot` correspondant (lu via
    `installations.selectors`, jamais son modèle) ;
  * cross-company : lot/série d'une autre société → 404 ;
  * une réception sans série/lot → 404 propre sur l'action étiquettes.

Run:
    python manage.py test apps.stock.test_zstk6_etiquette_lot_serie -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, LotEntrepot, Produit, ReceptionFournisseur,
)
from apps.stock import labels

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


class Zstk6Base(TestCase):
    def setUp(self):
        self.company = _company('zstk6-co')
        self.user = _user(
            self.company, 'zstk6-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZSTK6')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ZSTK6', sku='OND-ZSTK6',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))

    def _reception(self, numeros_serie=None, numero_lot=None,
                   reference='REC-ZSTK6-0001'):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{reference}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=5)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=reference, bon_commande=bcf,
            statut=ReceptionFournisseur.Statut.BROUILLON)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=5, numeros_serie=numeros_serie, numero_lot=numero_lot)
        return rec


class TestPlanchePlusieursSeriesEtLot(Zstk6Base):
    def test_cinq_series_impriment_cinq_etiquettes(self):
        series = [f'SN-{i}' for i in range(5)]
        rec = self._reception(numeros_serie=series)
        url = (
            f'/api/django/stock/receptions-fournisseur/{rec.id}'
            '/etiquettes/?sortie=html')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        for s in series:
            self.assertIn(
                labels.serie_token(self.produit.id, s), content)

    def test_lot_imprime_son_etiquette(self):
        rec = self._reception(numero_lot='LOT-ZSTK6-001')
        url = (
            f'/api/django/stock/receptions-fournisseur/{rec.id}'
            '/etiquettes/?sortie=html')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn(
            labels.lot_token(self.produit.id, 'LOT-ZSTK6-001'), content)

    def test_reception_sans_serie_ni_lot_404(self):
        rec = self._reception()
        url = (
            f'/api/django/stock/receptions-fournisseur/{rec.id}'
            '/etiquettes/')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)


class TestResolutionLot(Zstk6Base):
    def test_scan_lot_ouvre_lot_entrepot(self):
        lot = LotEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_lot='LOT-ZSTK6-RESOLVE', quantite_recue=10,
            quantite_restante=10)
        code = labels.lot_token(self.produit.id, 'LOT-ZSTK6-RESOLVE')
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['type'], 'lot')
        self.assertEqual(resp.data['id'], lot.id)
        self.assertEqual(resp.data['quantite_restante'], 10)

    def test_scan_lot_inconnu_404(self):
        code = labels.lot_token(self.produit.id, 'LOT-INCONNU')
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_scan_lot_cross_company_404(self):
        other_co = _company('zstk6-autre')
        LotEntrepot.objects.create(
            company=other_co, produit=self.produit,
            numero_lot='LOT-AUTRE', quantite_recue=5, quantite_restante=5)
        code = labels.lot_token(self.produit.id, 'LOT-AUTRE')
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)


class TestResolutionSerie(Zstk6Base):
    def test_scan_serie_ouvre_serie_entrepot(self):
        from apps.installations.models import SerieEntrepot

        serie = SerieEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_serie='SN-RESOLVE-001')
        code = labels.serie_token(self.produit.id, 'SN-RESOLVE-001')
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['type'], 'serie_entrepot')
        self.assertEqual(resp.data['id'], serie.id)

    def test_scan_serie_inconnue_404(self):
        code = labels.serie_token(self.produit.id, 'SN-INCONNUE')
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)
