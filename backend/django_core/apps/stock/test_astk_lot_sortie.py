"""ASTK204 / ASTK205 (C-ASTK-052) — la sortie d'un lot et le stock du
produit bougent ENSEMBLE.

Sonde MVT-17 (a) d'origine : ``POST lots-entrepot/<L>/sortir/ {quantite: 4}``
→ 200, lot restant 6, mais ``quantite_stock`` restait 10 et AUCUN
``MouvementStock`` n'était posé ; deux sorties concurrentes relisaient le
même restant (pas de verrou).

Aucun mock : vues, services et ``record_stock_movement`` réels.

Run :
    python manage.py test apps.stock.test_astk_lot_sortie -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import LotEntrepot, MouvementStock, Produit
from apps.stock.services import sortir_lot_entrepot

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class LotSortieTests(TestCase):
    def setUp(self):
        self.co = make_company('astk204-co', 'ASTK204 Co')
        self.resp = User.objects.create_user(
            username='astk204_resp', password='x', role_legacy='responsable',
            company=self.co)
        self.api = auth_client(self.resp)
        self.produit = Produit.objects.create(
            company=self.co, nom='Batterie ASTK204', sku='ASTK204-1',
            prix_achat=Decimal('100'), prix_vente=Decimal('200'),
            quantite_stock=10)
        self.lot = LotEntrepot.objects.create(
            company=self.co, produit=self.produit, numero_lot='LOT-ASTK204',
            quantite_recue=10, quantite_restante=10,
            reference_reception='REC-ASTK204')

    def test_sortir_lot_cree_un_mouvement(self):
        r = self.api.post(
            f'/api/django/stock/lots-entrepot/{self.lot.id}/sortir/',
            {'quantite': 4}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['quantite_restante'], 6)
        # Persistance relue.
        self.lot.refresh_from_db()
        self.produit.refresh_from_db()
        self.assertEqual(self.lot.quantite_restante, 6)
        self.assertEqual(self.produit.quantite_stock, 6)
        mouvements = MouvementStock.objects.filter(
            company=self.co, produit=self.produit)
        self.assertEqual(mouvements.count(), 1)
        mvt = mouvements.get()
        self.assertEqual(mvt.type_mouvement,
                         MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(mvt.quantite, 4)
        self.assertEqual(mvt.quantite_avant, 10)
        self.assertEqual(mvt.quantite_apres, 6)
        self.assertEqual(mvt.reference, 'LOT-ASTK204')

    def test_double_sortie_refusee_sous_verrou(self):
        """Deux lecteurs du MÊME lot (restant 10 en mémoire) : la seconde
        sortie de 6 relit le lot sous verrou et est refusée."""
        lecteur_1 = LotEntrepot.objects.get(pk=self.lot.pk)
        lecteur_2 = LotEntrepot.objects.get(pk=self.lot.pk)
        sortir_lot_entrepot(company=self.co, lot=lecteur_1, quantite=6)
        with self.assertRaises(ValueError):
            sortir_lot_entrepot(company=self.co, lot=lecteur_2, quantite=6)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite_restante, 4)

    def test_sortie_refusee_ne_pose_aucun_mouvement(self):
        r = self.api.post(
            f'/api/django/stock/lots-entrepot/{self.lot.id}/sortir/',
            {'quantite': 11}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.lot.refresh_from_db()
        self.produit.refresh_from_db()
        self.assertEqual(self.lot.quantite_restante, 10)
        self.assertEqual(self.produit.quantite_stock, 10)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.produit).exists())
