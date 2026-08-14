"""NTWMS5 — poste de travail scanner : résolution universelle + mouvement scanné.

Le magasinier ne tape aucun texte : il scanne un code, l'API dit CE QUE C'EST,
puis il confirme une quantité. Ces tests couvrent la résolution (casier,
produit, emplacement, lot), l'isolation société, et la pose d'un mouvement avec
casiers source/destination tracés.

Run :
    python manage.py test apps.stock.test_ntwms5_scanner -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, LotEntrepot, MouvementStock, Produit,
)
from apps.stock.selectors import resoudre_code_scanne
from apps.stock.services import enregistrer_mouvement_scanne

User = get_user_model()

PEREMPTION = datetime.date(2027, 6, 30)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms5Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation

        self.company = make_company('ntwms5-co', 'NTWMS5 Co')
        self.autre = make_company('ntwms5-autre', 'NTWMS5 Autre')
        self.admin = User.objects.create_user(
            username='ntwms5_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette NTWMS5')
        self.produit = Produit.objects.create(
            company=self.company, nom='Micro-onduleur', sku='MIC-NTWMS5',
            code_barres='3401579876543', prix_achat=Decimal('80'),
            prix_vente=Decimal('130'), quantite_stock=25)
        self.casier = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='E-03-11', zone='E', allee='03', casier='11', ordre=30)
        self.casier_cible = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='E-03-12', zone='E', allee='03', casier='12', ordre=31)
        self.lot = LotEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_lot='LOT-NTWMS5', date_peremption=PEREMPTION,
            quantite_recue=25, quantite_restante=25)
        self.api = auth(self.admin)


class TestResolutionCodeScanne(Ntwms5Base):
    def test_casier(self):
        res = resoudre_code_scanne(self.company, 'E-03-11')
        self.assertEqual(res['type'], 'casier')
        self.assertEqual(res['id'], self.casier.id)
        self.assertEqual(res['detail']['zone'], 'E')

    def test_produit_par_code_barres(self):
        res = resoudre_code_scanne(self.company, '3401579876543')
        self.assertEqual(res['type'], 'produit')
        self.assertEqual(res['id'], self.produit.id)
        self.assertEqual(res['detail']['quantite_stock'], 25)

    def test_produit_par_sku(self):
        res = resoudre_code_scanne(self.company, 'MIC-NTWMS5')
        self.assertEqual(res['type'], 'produit')

    def test_emplacement(self):
        res = resoudre_code_scanne(self.company, 'Camionnette NTWMS5')
        self.assertEqual(res['type'], 'emplacement')

    def test_lot(self):
        res = resoudre_code_scanne(self.company, 'LOT-NTWMS5')
        self.assertEqual(res['type'], 'lot')
        self.assertEqual(res['detail']['quantite_restante'], 25)

    def test_code_inconnu(self):
        self.assertIsNone(resoudre_code_scanne(self.company, 'ZZZ-000'))

    def test_casier_d_une_autre_societe_invisible(self):
        self.assertIsNone(resoudre_code_scanne(self.autre, 'E-03-11'))

    def test_endpoint_404_sur_code_inconnu(self):
        resp = self.api.get('/api/django/stock/scanner/resoudre/?code=ZZZ')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_400_sans_code(self):
        resp = self.api.get('/api/django/stock/scanner/resoudre/')
        self.assertEqual(resp.status_code, 400)


class TestMouvementScanne(Ntwms5Base):
    def test_entree_scannee_incremente_et_trace_le_casier(self):
        mouvement = enregistrer_mouvement_scanne(
            company=self.company, user=self.admin, produit_id=self.produit.id,
            type_mouvement='entree', quantite=5,
            bin_destination_id=self.casier.id)
        self.assertEqual(mouvement.quantite_avant, 25)
        self.assertEqual(mouvement.quantite_apres, 30)
        self.assertEqual(mouvement.bin_destination_id, self.casier.id)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 30)

    def test_transfert_ne_change_pas_le_total(self):
        mouvement = enregistrer_mouvement_scanne(
            company=self.company, user=self.admin, produit_id=self.produit.id,
            type_mouvement='transfert', quantite=4,
            bin_source_id=self.casier.id,
            bin_destination_id=self.casier_cible.id)
        self.assertEqual(mouvement.quantite_avant, 25)
        self.assertEqual(mouvement.quantite_apres, 25)
        self.assertEqual(mouvement.bin_source_id, self.casier.id)
        self.assertEqual(mouvement.bin_destination_id, self.casier_cible.id)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 25)

    def test_sortie_superieure_au_stock_refusee(self):
        with self.assertRaises(ValueError):
            enregistrer_mouvement_scanne(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, type_mouvement='sortie',
                quantite=999, bin_source_id=self.casier.id)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 25)

    def test_type_non_scannable_refuse(self):
        with self.assertRaises(ValueError):
            enregistrer_mouvement_scanne(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, type_mouvement='rebut',
                quantite=1)

    def test_casier_d_une_autre_societe_refuse(self):
        from apps.installations.models import BinLocation
        emplacement_autre = EmplacementStock.objects.create(
            company=self.autre, nom='Dépôt autre NTWMS5')
        casier_autre = BinLocation.objects.create(
            company=self.autre, emplacement=emplacement_autre, code='X-01-01',
            ordre=1)
        with self.assertRaises(ValueError):
            enregistrer_mouvement_scanne(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, type_mouvement='entree',
                quantite=1, bin_destination_id=casier_autre.id)

    def test_endpoint_pose_le_mouvement(self):
        resp = self.api.post('/api/django/stock/scanner/mouvement/', {
            'produit': self.produit.id, 'type_mouvement': 'entree',
            'quantite': 3, 'bin_destination': self.casier.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['quantite_apres'], 28)
        self.assertEqual(
            MouvementStock.objects.filter(
                company=self.company,
                bin_destination_id=self.casier.id).count(), 1)

    def test_endpoint_refuse_produit_d_une_autre_societe(self):
        etranger = Produit.objects.create(
            company=self.autre, nom='Intrus', sku='INT-NTWMS5',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=10)
        resp = self.api.post('/api/django/stock/scanner/mouvement/', {
            'produit': etranger.id, 'type_mouvement': 'entree', 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
