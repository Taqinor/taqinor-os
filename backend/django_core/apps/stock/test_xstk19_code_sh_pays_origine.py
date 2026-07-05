"""XSTK19 — Code SH (HS) + pays d'origine sur Produit -> dossier d'import.

Couvre :
  * les champs code_sh/pays_origine sont exposes par le serializer produit ;
  * un dossier d'import cree depuis un BCF pre-remplit codes SH/origines
    depuis les SKUs (via le selector stock, jamais un import direct) ;
  * champs vides tolerees (jamais de valeur inventee) ;
  * scope societe (un BCF d'une autre societe ne renvoie rien).

Run:
    python manage.py test apps.stock.test_xstk19_code_sh_pays_origine -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.stock.selectors import lignes_import_depuis_bcf
from apps.stock.serializers import ProduitSerializer

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


class Xstk19Base(TestCase):
    def setUp(self):
        self.company = _company('xstk19-co')
        self.user = _user(
            self.company, 'xstk19-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur import')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur import', sku='OND-XSTK19',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            code_sh='8504.40', pays_origine='Chine')
        self.produit_sans_sh = Produit.objects.create(
            company=self.company, nom='Cable import', sku='CBL-XSTK19',
            prix_vente=Decimal('50'), prix_achat=Decimal('20'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XSTK19-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit_sans_sh, quantite=20,
            prix_achat_unitaire=Decimal('20'))


class ProduitFieldsTests(Xstk19Base):
    def test_serializer_exposes_code_sh_et_pays_origine(self):
        data = ProduitSerializer(self.produit).data
        self.assertEqual(data['code_sh'], '8504.40')
        self.assertEqual(data['pays_origine'], 'Chine')

    def test_champs_vides_tolerees(self):
        data = ProduitSerializer(self.produit_sans_sh).data
        self.assertIsNone(data['code_sh'])
        self.assertIsNone(data['pays_origine'])


class LignesImportSelectorTests(Xstk19Base):
    def test_prefill_depuis_bcf(self):
        lignes = lignes_import_depuis_bcf(self.company, self.bcf.pk)
        self.assertEqual(len(lignes), 2)
        par_sku = {row['sku']: row for row in lignes}
        self.assertEqual(par_sku['OND-XSTK19']['code_sh'], '8504.40')
        self.assertEqual(par_sku['OND-XSTK19']['pays_origine'], 'Chine')
        self.assertEqual(par_sku['OND-XSTK19']['quantite'], 5)
        # champ vide tolere, jamais invente
        self.assertEqual(par_sku['CBL-XSTK19']['code_sh'], '')
        self.assertEqual(par_sku['CBL-XSTK19']['pays_origine'], '')

    def test_scope_societe(self):
        autre = _company('xstk19-autre')
        self.assertEqual(lignes_import_depuis_bcf(autre, self.bcf.pk), [])

    def test_bcf_inexistant(self):
        self.assertEqual(lignes_import_depuis_bcf(self.company, 999999), [])


class LignesImportEndpointTests(Xstk19Base):
    def test_endpoint_lignes_import(self):
        resp = self.api.get(
            f'/api/django/stock/bons-commande-fournisseur/{self.bcf.pk}/lignes-import/')
        self.assertEqual(resp.status_code, 200)
        skus = {row['sku'] for row in resp.json()}
        self.assertEqual(skus, {'OND-XSTK19', 'CBL-XSTK19'})
