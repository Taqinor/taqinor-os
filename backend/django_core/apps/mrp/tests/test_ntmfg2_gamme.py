"""NTMFG2 — Gamme opératoire généraliste : `Operation` + `GammeOperation` avec
poste de charge et temps standard.

Critère : une gamme à 3 opérations sur 2 postes calcule un temps total prévu
correct (prépa + unitaire×qté), versionnable, cross-tenant refusé."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, PosteDeCharge
from apps.mrp.services import temps_total_gamme
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Coffret AC/DC'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class TempsTotalGammeTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-gamme-1', 'MRP Gamme 1')
        self.produit = make_produit(self.company)
        self.poste_a = PosteDeCharge.objects.create(
            company=self.company, code='P-A', nom='Poste A')
        self.poste_b = PosteDeCharge.objects.create(
            company=self.company, code='P-B', nom='Poste B')
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme coffret', produit=self.produit)
        # 3 opérations sur 2 postes.
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste_a,
            libelle='Découpe', temps_prepa_min=Decimal('10'),
            temps_unitaire_min=Decimal('2'))
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=2, poste_charge=self.poste_b,
            libelle='Câblage', temps_prepa_min=Decimal('5'),
            temps_unitaire_min=Decimal('4'))
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=3, poste_charge=self.poste_a,
            libelle='Contrôle', temps_prepa_min=Decimal('0'),
            temps_unitaire_min=Decimal('1'))

    def test_temps_total_prevu_correct(self):
        # Pour 5 pièces :
        #   op1 = 10 + 2*5  = 20
        #   op2 = 5  + 4*5  = 25
        #   op3 = 0  + 1*5  = 5
        # total = 50
        total = temps_total_gamme(self.gamme, 5)
        self.assertEqual(total, Decimal('50'))

    def test_temps_min_par_lot_borne_le_minimum(self):
        op = OperationGamme.objects.create(
            gamme=self.gamme, ordre=4, poste_charge=self.poste_b,
            libelle='Réglage', temps_prepa_min=Decimal('0'),
            temps_unitaire_min=Decimal('0.5'), temps_min_par_lot=Decimal('30'))
        from apps.mrp.services import temps_operation_min
        # 1 pièce -> 0.5 min brut, mais le minimum par lot est 30.
        self.assertEqual(temps_operation_min(op, 1), Decimal('30'))

    def test_gamme_versionnable(self):
        v2 = Gamme.objects.create(
            company=self.company, nom='Gamme coffret', produit=self.produit,
            version=2)
        self.assertEqual(
            Gamme.objects.filter(company=self.company, produit=self.produit).count(), 2)
        self.assertEqual(v2.version, 2)


class GammeApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-gamme-api-1', 'MRP Gamme API 1')
        self.other_company = make_company('mrp-gamme-api-2', 'MRP Gamme API 2')
        self.user = make_user(self.company, 'mrp-gamme-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.other_produit = make_produit(self.other_company, 'Autre produit')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-1', nom='Poste 1')

    def test_cross_tenant_gamme_retrieve_404(self):
        gamme = Gamme.objects.create(
            company=self.other_company, nom='Gamme étrangère',
            produit=self.other_produit)
        resp = self.api.get(f'/api/django/mrp/gammes/{gamme.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_operation_gamme_refuses_foreign_gamme(self):
        gamme = Gamme.objects.create(
            company=self.other_company, nom='Gamme étrangère',
            produit=self.other_produit)
        resp = self.api.post('/api/django/mrp/operations-gamme/', {
            'gamme': gamme.id, 'poste_charge': self.poste.id,
            'ordre': 1, 'libelle': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_operation_gamme_crud_and_filter_by_gamme(self):
        gamme = Gamme.objects.create(
            company=self.company, nom='Gamme locale', produit=self.produit)
        resp = self.api.post('/api/django/mrp/operations-gamme/', {
            'gamme': gamme.id, 'poste_charge': self.poste.id,
            'ordre': 1, 'libelle': 'Assemblage',
            'temps_prepa_min': '5', 'temps_unitaire_min': '1',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = self.api.get(f'/api/django/mrp/operations-gamme/?gamme={gamme.id}')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 1)

        resp = self.api.get(f'/api/django/mrp/gammes/{gamme.id}/')
        self.assertEqual(len(resp.data['operations']), 1)
