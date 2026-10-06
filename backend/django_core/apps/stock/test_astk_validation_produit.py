"""ASTK92/ASTK93 — validation de saisie produit, bulk et SKU (C-ASTK-026).

Sonde CAT-10 : PATCH prix=-5 / tva=500 / seuil=-3 → 200 ; bulk NaN → 500 ;
bulk -100 % → 200 prix=0.00 ; conditionnement facteur=0 → 201. Chaque règle
a son test ; le produit relu après un refus garde ses valeurs d'origine.
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import ConditionnementProduit, Produit
from authentication.models import Company, User

_seq = itertools.count(1)


class _Base(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK92 {n}', slug=f'astk92-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk92_admin_{n}', password='x',
            email=f'astk92-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class ValidationProduitTests(_Base):
    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550', sku='PAN-550',
            prix_achat=Decimal('60'), prix_vente=Decimal('100'),
            seuil_alerte=2, tva=Decimal('20'))

    def _patch(self, **corps):
        return self.api.patch(
            f'/api/django/stock/produits/{self.produit.pk}/', corps,
            format='json')

    def _bulk(self, **corps):
        return self.api.post(
            '/api/django/stock/produits/bulk/',
            {'ids': [self.produit.pk], **corps}, format='json')

    def _inchange(self):
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.prix_vente, Decimal('100.00'))
        self.assertEqual(self.produit.prix_achat, Decimal('60.00'))
        self.assertEqual(self.produit.seuil_alerte, 2)
        self.assertEqual(self.produit.tva, Decimal('20.00'))

    def test_prix_vente_negatif(self):
        reponse = self._patch(prix_vente='-5')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('prix_vente', reponse.json())
        self._inchange()

    def test_prix_achat_negatif(self):
        reponse = self._patch(prix_achat='-5')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('prix_achat', reponse.json())
        self._inchange()

    def test_seuil_alerte_negatif(self):
        reponse = self._patch(seuil_alerte='-3')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('seuil_alerte', reponse.json())
        self._inchange()

    def test_tva_hors_bornes(self):
        reponse = self._patch(tva='500')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('tva', reponse.json())
        self._inchange()

    def test_prix_vente_zero_reste_accepte(self):
        """Pompes « prix à renseigner » : 0 est une valeur légitime."""
        reponse = self._patch(prix_vente='0')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.prix_vente, Decimal('0.00'))

    def test_garantie_negative(self):
        reponse = self._patch(garantie_mois='-1')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('garantie_mois', reponse.json())
        self._inchange()

    def test_bulk_nan_et_infinity(self):
        for valeur in ('NaN', 'Infinity', '-Infinity'):
            reponse = self._bulk(
                action='set_price', mode='fixed', valeur=valeur)
            self.assertEqual(reponse.status_code, 400, (valeur, reponse.content))
        self._inchange()

    def test_bulk_hors_bornes(self):
        reponse = self._bulk(
            action='set_price', mode='fixed', valeur='1000000000000')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self._inchange()

    def test_bulk_moins_100_pourcent_refuse(self):
        reponse = self._bulk(
            action='set_price', mode='percent', valeur='-100')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self._inchange()

    def test_bulk_prix_fixe_nul_refuse(self):
        reponse = self._bulk(action='set_price', mode='fixed', valeur='0')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self._inchange()

    def test_bulk_garantie_negative(self):
        reponse = self._bulk(action='set_warranty', garantie_mois=-1)
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self._inchange()
        self.assertIsNone(
            Produit.objects.get(pk=self.produit.pk).garantie_mois)

    def test_conditionnement_facteur_nul(self):
        reponse = self.api.post(
            '/api/django/stock/conditionnements/',
            {'produit': self.produit.pk, 'nom': 'Carton', 'facteur': '0'},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('facteur', reponse.json())
        self.assertFalse(ConditionnementProduit.objects.filter(
            produit=self.produit).exists())


class SkuTests(_Base):
    """ASTK93 — SKU normalisé ('' → None) et unique à la casse près."""

    def _creer(self, **corps):
        return self.api.post(
            '/api/django/stock/produits/',
            {'prix_vente': '10', **corps}, format='json')

    def test_sku_vide_normalise_puis_doublon_a_la_casse_refuse(self):
        Produit.objects.create(
            company=self.company, nom='A', sku='ref-1', prix_vente=10)
        # un produit existant sans SKU : le POST '' ne doit plus entrer en
        # collision (500 IntegrityError avant)
        Produit.objects.create(
            company=self.company, nom='Sans sku', prix_vente=10)

        reponse = self._creer(nom='B', sku='')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        self.assertIsNone(Produit.objects.get(pk=reponse.json()['id']).sku)

        reponse = self._creer(nom='C', sku='REF-1')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertEqual(
            reponse.json()['sku'], ['Ce SKU existe déjà (REF-1 ≈ ref-1).'])
        self.assertFalse(Produit.objects.filter(nom='C').exists())

    def test_deux_produits_sans_sku_ne_collisionnent_plus(self):
        premier = self._creer(nom='Premier', sku='')
        second = self._creer(nom='Second', sku='   ')
        self.assertEqual(premier.status_code, 201, premier.content)
        self.assertEqual(second.status_code, 201, second.content)

    def test_kits_sku_vide_deux_fois_puis_doublon(self):
        for nom in ('Kit 1', 'Kit 2'):
            reponse = self.api.post(
                '/api/django/stock/kits/',
                {'nom': nom, 'sku': '', 'composants': []}, format='json')
            self.assertEqual(reponse.status_code, 201, reponse.content)
        reponse = self.api.post(
            '/api/django/stock/kits/',
            {'nom': 'Kit 3', 'sku': 'kit-x', 'composants': []},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        reponse = self.api.post(
            '/api/django/stock/kits/',
            {'nom': 'Kit 4', 'sku': 'KIT-X', 'composants': []},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('sku', reponse.json())
