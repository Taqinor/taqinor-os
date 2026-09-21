"""NTMFG3 — Ordre de Fabrication (OF) capacitaire lié à une gamme et des
postes.

Critère : un OF instancie ses opérations depuis la gamme, dates prévues
cohérentes avec la capacité poste, lien optionnel vers un OrdreAssemblage
sans double mouvement de stock, cross-tenant refusé."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.services import confirmer_of
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Coffret AC/DC'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class ConfirmerOfTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-of-1', 'MRP OF 1')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-1', nom='Poste 1',
            capacite_heures_jour=Decimal('8'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme test', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Découpe', temps_prepa_min=Decimal('10'),
            temps_unitaire_min=Decimal('2'))
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=2, poste_charge=self.poste,
            libelle='Câblage', temps_prepa_min=Decimal('5'),
            temps_unitaire_min=Decimal('3'))

    def test_confirmer_instancie_operations_depuis_gamme(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        self.assertEqual(of.statut, OrdreFabrication.Statut.PLANIFIE)
        self.assertEqual(of.operations.count(), 2)
        libelles = list(of.operations.order_by('ordre').values_list('libelle', flat=True))
        self.assertEqual(libelles, ['Découpe', 'Câblage'])

    def test_confirmer_est_idempotent(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=self.gamme)
        confirmer_of(of)
        confirmer_of(of)
        of.refresh_from_db()
        self.assertEqual(of.operations.count(), 2)

    def test_dates_prevues_respectent_capacite_poste(self):
        # Poste à 1h/jour (60 min) : découpe (10+2*10=30min) + câblage
        # (5+3*10=35min) = 65min > 60min -> bascule au jour ouvré suivant.
        poste_petit = PosteDeCharge.objects.create(
            company=self.company, code='P-PETIT', nom='Poste petit',
            capacite_heures_jour=Decimal('1'))
        gamme2 = Gamme.objects.create(
            company=self.company, nom='Gamme petite capacité',
            produit=self.produit, version=2)
        OperationGamme.objects.create(
            gamme=gamme2, ordre=1, poste_charge=poste_petit,
            libelle='Op1', temps_prepa_min=Decimal('10'),
            temps_unitaire_min=Decimal('2'))
        OperationGamme.objects.create(
            gamme=gamme2, ordre=2, poste_charge=poste_petit,
            libelle='Op2', temps_prepa_min=Decimal('5'),
            temps_unitaire_min=Decimal('3'))
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=gamme2)
        confirmer_of(of)
        of.refresh_from_db()
        op1, op2 = of.operations.order_by('ordre')
        self.assertLess(op1.date_planifiee, op2.date_planifiee)
        self.assertIsNotNone(of.date_debut_planifiee)
        self.assertIsNotNone(of.date_fin_planifiee)
        self.assertGreater(of.date_fin_planifiee, of.date_debut_planifiee)

    def test_of_sans_gamme_ne_cree_aucune_operation(self):
        # Un OF sans gamme (ex. entièrement délégué à un
        # `kit_ordre_assemblage`) ne crée aucune opération ni date prévue,
        # mais la confirmation ne plante jamais.
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5)
        confirmer_of(of)
        of.refresh_from_db()
        self.assertEqual(of.operations.count(), 0)
        self.assertIsNone(of.date_debut_planifiee)
        self.assertEqual(of.statut, OrdreFabrication.Statut.PLANIFIE)


class OrdreFabricationApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-of-api-1', 'MRP OF API 1')
        self.other_company = make_company('mrp-of-api-2', 'MRP OF API 2')
        self.user = make_user(self.company, 'mrp-of-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.other_produit = make_produit(self.other_company, 'Autre produit')

    def test_cross_tenant_retrieve_404(self):
        of = OrdreFabrication.objects.create(
            company=self.other_company, produit=self.other_produit, quantite=1)
        resp = self.api.get(f'/api/django/mrp/ordres-fabrication/{of.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_create_refuses_foreign_produit(self):
        resp = self.api.post('/api/django/mrp/ordres-fabrication/', {
            'produit': self.other_produit.id, 'quantite': '3',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_and_confirmer_via_api(self):
        poste = PosteDeCharge.objects.create(
            company=self.company, code='P-API', nom='Poste API')
        gamme = Gamme.objects.create(
            company=self.company, nom='Gamme API', produit=self.produit)
        OperationGamme.objects.create(
            gamme=gamme, ordre=1, poste_charge=poste, libelle='Op unique',
            temps_prepa_min=Decimal('1'), temps_unitaire_min=Decimal('1'))
        resp = self.api.post('/api/django/mrp/ordres-fabrication/', {
            'produit': self.produit.id, 'quantite': '4', 'gamme': gamme.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        of_id = resp.data['id']
        self.assertEqual(resp.data['statut'], 'brouillon')

        resp = self.api.post(f'/api/django/mrp/ordres-fabrication/{of_id}/confirmer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'planifie')
        self.assertEqual(len(resp.data['operations']), 1)
