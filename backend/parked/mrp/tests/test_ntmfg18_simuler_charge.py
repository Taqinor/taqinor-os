"""NTMFG18 — Simulation « et si » de charge avant confirmation d'un nouveau
devis/OF.

Critère : simulation sans écriture renvoie un verdict correct sur un cas
testé (poste saturé), intégration devis n'affecte rien si aucun produit du
devis n'a de gamme (aucune écriture — pas d'OF/OperationOF créés)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OperationOF, OrdreFabrication, PosteDeCharge
from apps.mrp.selectors import simuler_charge
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class SimulerChargeTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-simcharge-1', 'MRP SimCharge 1')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-SIM', nom='Poste simulation',
            capacite_heures_jour=Decimal('1'))  # 60 min/jour -> facile à saturer.
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme sim', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op sim', temps_unitaire_min=Decimal('10'))

    def test_sans_gamme_aucune_ecriture(self):
        autre_produit = make_produit(self.company, 'Produit négoce')
        resultat = simuler_charge(
            self.company, [{'produit_id': autre_produit.id, 'quantite': 5}])
        self.assertEqual(resultat['tenable'], 'sans_gamme')
        self.assertEqual(OrdreFabrication.objects.count(), 0)
        self.assertEqual(OperationOF.objects.count(), 0)

    def test_poste_non_sature_tenable(self):
        resultat = simuler_charge(
            self.company, [{'produit_id': self.produit.id, 'quantite': 2}])
        self.assertEqual(resultat['tenable'], 'tenable')
        self.assertEqual(OrdreFabrication.objects.count(), 0)

    def test_poste_sature_tenable_avec_retard(self):
        # 10 unités × 10 min = 100 min > 60 min de capacité -> retard.
        resultat = simuler_charge(
            self.company, [{'produit_id': self.produit.id, 'quantite': 10}])
        self.assertEqual(resultat['tenable'], 'tenable_avec_retard')
        self.assertEqual(resultat['poste_goulot'], 'Poste simulation')
        self.assertGreater(resultat['retard_jours'], 0)
        self.assertEqual(OrdreFabrication.objects.count(), 0)

    def test_capacite_nulle_non_tenable(self):
        poste_sans_capacite = PosteDeCharge.objects.create(
            company=self.company, code='P-ZERO', nom='Poste sans capacité',
            capacite_heures_jour=Decimal('0'))
        gamme2 = Gamme.objects.create(
            company=self.company, nom='Gamme zero', produit=self.produit, version=2)
        OperationGamme.objects.create(
            gamme=gamme2, ordre=1, poste_charge=poste_sans_capacite,
            libelle='Op zero', temps_unitaire_min=Decimal('1'))
        resultat = simuler_charge(
            self.company, [{'produit_id': self.produit.id, 'quantite': 1}])
        self.assertEqual(resultat['tenable'], 'non_tenable')

    def test_isolation_tenant(self):
        autre_company = make_company('mrp-simcharge-2', 'MRP SimCharge 2')
        resultat = simuler_charge(
            autre_company, [{'produit_id': self.produit.id, 'quantite': 100}])
        # Produit inconnu de cette société -> aucune gamme trouvée.
        self.assertEqual(resultat['tenable'], 'sans_gamme')


class SimulerChargeApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-simcharge-api-1', 'MRP SimCharge API 1')
        self.user = make_user(self.company, 'mrp-simcharge-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-SIM-API', nom='Poste API')
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme API', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op', temps_unitaire_min=Decimal('1'))

    def test_simuler_charge_endpoint(self):
        resp = self.api.post('/api/django/mrp/simuler-charge/', {
            'lignes': [{'produit_id': self.produit.id, 'quantite': 3}],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn(resp.data['tenable'], ('tenable', 'tenable_avec_retard'))
