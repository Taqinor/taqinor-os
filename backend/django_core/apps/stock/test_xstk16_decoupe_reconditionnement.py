"""XSTK16 — Decoupe / reconditionnement (touret -> coupes) avec cout et lot
preserves.

Couvre :
  * decouper 1 touret (100 m) en 10 coupes (10 m chacune, meme SKU) conserve
    EXACTEMENT la valeur totale (au centime pres) ;
  * la SORTIE source et l'ENTREE cible sont tracees dans MouvementStock avec
    une reference COMMUNE ;
  * stock insuffisant -> ValueError, rien n'est ecrit ;
  * un lot source (XSTK6) est decremente et un nouveau lot cible est cree
    avec le meme numero_lot/date_peremption ;
  * endpoint `produits/decoupes/`.

Run:
    python manage.py test apps.stock.test_xstk16_decoupe_reconditionnement -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import LotEntrepot, MouvementStock, Produit
from apps.stock.services import decouper_produit

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    # Un Role fin n'est créé QUE si des permissions explicites sont passées :
    # sinon `is_responsable` retombe sur `_role_grants_write([])` → False au
    # lieu du repli légitime par `role_legacy` (ERR4, authentication/models.py).
    role = None
    if permissions is not None:
        role = Role.objects.create(
            company=company, nom=f'r-{username}', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xstk16Base(TestCase):
    def setUp(self):
        self.company = _company('xstk16-co')
        self.user = _user(
            self.company, 'xstk16-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.touret = Produit.objects.create(
            company=self.company, nom='Câble touret 100m', sku='CBL-TOURET',
            prix_vente=Decimal('10'), prix_achat=Decimal('5'),
            unite_stock='m', quantite_stock=1)
        self.coupe = Produit.objects.create(
            company=self.company, nom='Câble coupe 10m', sku='CBL-COUPE',
            prix_vente=Decimal('12'), prix_achat=Decimal('5'),
            unite_stock='unité', quantite_stock=0)


class DecouperProduitTests(Xstk16Base):
    def test_conserve_la_valeur_totale(self):
        # coût moyen catalogue du touret : 5 (prix_achat, aucun achat reçu)
        result = decouper_produit(
            company=self.company, produit_source=self.touret,
            quantite_consommee=1, produit_cible=self.coupe,
            quantite_produite=10, user=self.user)
        # 1 touret (coût 5) -> valeur transférée totale = 5.00, peu importe
        # que la cible ait 10 unités (aucune valeur créée/détruite).
        self.assertEqual(result['valeur_transferee'], Decimal('5.00'))
        self.touret.refresh_from_db()
        self.coupe.refresh_from_db()
        self.assertEqual(self.touret.quantite_stock, 0)
        self.assertEqual(self.coupe.quantite_stock, 10)

    def test_reference_commune_sur_les_deux_mouvements(self):
        result = decouper_produit(
            company=self.company, produit_source=self.touret,
            quantite_consommee=1, produit_cible=self.coupe,
            quantite_produite=10, user=self.user)
        mvts = MouvementStock.objects.filter(reference=result['reference'])
        self.assertEqual(mvts.count(), 2)
        types = {m.type_mouvement for m in mvts}
        self.assertEqual(
            types, {MouvementStock.TypeMouvement.SORTIE,
                    MouvementStock.TypeMouvement.ENTREE})

    def test_stock_insuffisant_refuse(self):
        with self.assertRaises(ValueError):
            decouper_produit(
                company=self.company, produit_source=self.touret,
                quantite_consommee=5, produit_cible=self.coupe,
                quantite_produite=50, user=self.user)
        self.touret.refresh_from_db()
        self.assertEqual(self.touret.quantite_stock, 1)

    def test_meme_sku_source_et_cible(self):
        # Découpe d'un produit VERS lui-même (rare mais autorisé par la spec).
        self.touret.quantite_stock = 3
        self.touret.save(update_fields=['quantite_stock'])
        result = decouper_produit(
            company=self.company, produit_source=self.touret,
            quantite_consommee=1, produit_cible=self.touret,
            quantite_produite=1, user=self.user)
        self.touret.refresh_from_db()
        # -1 (consommé) +1 (produit) = net 0 -> reste 3.
        self.assertEqual(self.touret.quantite_stock, 3)
        self.assertEqual(result['produit_source'].quantite_stock, 3)

    def test_propage_lot_et_peremption(self):
        lot = LotEntrepot.objects.create(
            company=self.company, produit=self.touret, numero_lot='LOT-A',
            date_peremption=datetime.date(2027, 1, 1),
            quantite_recue=1, quantite_restante=1)
        result = decouper_produit(
            company=self.company, produit_source=self.touret,
            quantite_consommee=1, produit_cible=self.coupe,
            quantite_produite=10, user=self.user, lot_source=lot)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_restante, 0)
        self.assertEqual(result['numero_lot'], 'LOT-A')
        nouveau_lot = LotEntrepot.objects.get(
            produit=self.coupe, numero_lot='LOT-A')
        self.assertEqual(nouveau_lot.date_peremption, datetime.date(2027, 1, 1))
        self.assertEqual(nouveau_lot.quantite_restante, 10)


class DecoupesEndpointTests(Xstk16Base):
    def test_endpoint_decoupe(self):
        resp = self.api.post(
            '/api/django/stock/produits/decoupes/',
            {'produit_source': self.touret.pk, 'quantite_consommee': 1,
             'produit_cible': self.coupe.pk, 'quantite_produite': 10},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['valeur_transferee'], '5.00')
        self.touret.refresh_from_db()
        self.coupe.refresh_from_db()
        self.assertEqual(self.touret.quantite_stock, 0)
        self.assertEqual(self.coupe.quantite_stock, 10)

    def test_endpoint_stock_insuffisant(self):
        resp = self.api.post(
            '/api/django/stock/produits/decoupes/',
            {'produit_source': self.touret.pk, 'quantite_consommee': 99,
             'produit_cible': self.coupe.pk, 'quantite_produite': 990},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_produit_introuvable(self):
        resp = self.api.post(
            '/api/django/stock/produits/decoupes/',
            {'produit_source': 999999, 'quantite_consommee': 1,
             'produit_cible': self.coupe.pk, 'quantite_produite': 10},
            format='json')
        self.assertEqual(resp.status_code, 404)
