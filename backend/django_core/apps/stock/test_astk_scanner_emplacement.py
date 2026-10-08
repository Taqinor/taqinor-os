"""ASTK196 (C-ASTK-046, volet WMS-8) — les mouvements scannés passent par la
ventilation par emplacement, et un transfert scanné sans aucun casier est
refusé.

Sonde WMS-8b : entrée 3 dans un casier de camionnette → 201, ventilation
[Dépôt 13, Camionnette 0] ; transfert sans casier → 201.

Source réelle : vue `scanner/mouvement/` → `enregistrer_mouvement_scanne` →
`record_stock_movement` / `credit_emplacement_destination` /
`transfer_stock`, lecture `stock_breakdown` — aucun mock.

Run :
    python manage.py test apps.stock.test_astk_scanner_emplacement -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import BinLocation
from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit, TransfertStock,
)
from apps.stock.services import ensure_emplacements, stock_breakdown
from authentication.models import Company

User = get_user_model()

URL = '/api/django/stock/scanner/mouvement/'


class ScannerEmplacementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK196', slug='astk196-co')
        user = User.objects.create_user(
            username='astk196-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        ensure_emplacements(self.company)
        self.depot = EmplacementStock.objects.get(
            company=self.company, is_principal=True)
        self.camionnette = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette ASTK196',
            is_principal=False, ordre=50)
        self.casier_cam = BinLocation.objects.create(
            company=self.company, emplacement=self.camionnette,
            code='CAM-01', zone='C', allee='01', casier='01', ordre=10)
        self.casier_depot = BinLocation.objects.create(
            company=self.company, emplacement=self.depot,
            code='DEP-01', zone='D', allee='01', casier='01', ordre=20)
        self.produit = Produit.objects.create(
            company=self.company, nom='Câble ASTK196', sku='CAB-ASTK196',
            prix_vente=Decimal('20'), prix_achat=Decimal('10'),
            quantite_stock=10)

    def _ventilation(self):
        self.produit.refresh_from_db()
        return {ligne['emplacement_id']: ligne['quantite']
                for ligne in stock_breakdown(self.produit)}

    def _post(self, corps):
        corps = {'produit': self.produit.id, **corps}
        return self.api.post(URL, corps, format='json')

    def test_entree_casier_camionnette_ventilee(self):
        rep = self._post({'type_mouvement': 'entree', 'quantite': 3,
                          'bin_destination': self.casier_cam.id})
        self.assertEqual(rep.status_code, 201, rep.data)
        v = self._ventilation()
        self.assertEqual((v[self.depot.id], v[self.camionnette.id]), (10, 3))
        rep = self._post({'type_mouvement': 'sortie', 'quantite': 1,
                          'bin_source': self.casier_cam.id})
        self.assertEqual(rep.status_code, 201, rep.data)
        v = self._ventilation()
        self.assertEqual((v[self.depot.id], v[self.camionnette.id]), (10, 2))

    def test_transfert_sans_casier_400(self):
        nb = MouvementStock.objects.count()
        rep = self._post({'type_mouvement': 'transfert', 'quantite': 2})
        self.assertEqual(rep.status_code, 400, rep.data)
        # Corps DRF natif + enveloppe YAPIC3 additive sous « error ».
        self.assertEqual(rep.data['error']['code'], 'validation_error')
        self.assertEqual(
            {k: v for k, v in rep.data.items() if k != 'error'},
            {'bin_source': [
                'Un transfert scanné exige un casier source ou destination.']})
        self.assertEqual(MouvementStock.objects.count(), nb)

    def test_transfert_inter_emplacement_par_transfer_stock(self):
        rep = self._post({'type_mouvement': 'transfert', 'quantite': 2,
                          'bin_source': self.casier_depot.id,
                          'bin_destination': self.casier_cam.id})
        self.assertEqual(rep.status_code, 201, rep.data)
        v = self._ventilation()
        self.assertEqual((v[self.depot.id], v[self.camionnette.id]), (8, 2))
        self.assertTrue(TransfertStock.objects.filter(
            produit=self.produit, source=self.depot,
            destination=self.camionnette, quantite=2).exists())
        self.assertEqual(self.produit.quantite_stock, 10)
