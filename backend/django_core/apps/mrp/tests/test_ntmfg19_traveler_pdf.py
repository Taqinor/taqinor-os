"""NTMFG19 — Étiquette/fiche suiveuse d'Ordre de Fabrication (traveler)
imprimable.

Critère : le PDF liste les opérations dans l'ordre de gamme avec zones
d'émargement, se génère pour un OF planifié, aucun prix dans le document
(test de non-régression)."""
import inspect
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp import pdf as mrp_pdf
from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.services import confirmer_of
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=500, prix_achat=200, tva=20)


class TravelerPayloadTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-trav-1', 'MRP Traveler 1')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-TRAV', nom='Poste traveler',
            cout_horaire=Decimal('150'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme traveler', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op traveler', temps_unitaire_min=Decimal('5'))
        self.of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=4,
            gamme=self.gamme)
        confirmer_of(self.of)
        self.of.refresh_from_db()

    def test_operations_dans_l_ordre_de_gamme(self):
        payload = mrp_pdf._operations_payload(self.of)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['ordre'], 1)
        self.assertEqual(payload[0]['poste_nom'], 'Poste traveler')

    def test_aucun_prix_dans_le_contexte_ni_le_code(self):
        payload = mrp_pdf._operations_payload(self.of)
        for op in payload:
            self.assertNotIn('prix_achat', op)
            self.assertNotIn('prix_vente', op)
            self.assertNotIn('cout', op)
            self.assertNotIn('cout_horaire', op)
        source = inspect.getsource(mrp_pdf)
        self.assertNotIn('prix_achat', source)
        self.assertNotIn('prix_vente', source)
        self.assertNotIn('cout_horaire', source)


class TravelerPdfApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-trav-api-1', 'MRP Traveler API 1')
        self.user = make_user(self.company, 'mrp-trav-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-TRAV-API', nom='Poste API')
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme API', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op', temps_unitaire_min=Decimal('1'))
        self.of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1,
            gamme=self.gamme)
        confirmer_of(self.of)
        self.of.refresh_from_db()

    def test_endpoint_renvoie_un_pdf(self):
        resp = self.api.get(
            f'/api/django/mrp/ordres-fabrication/{self.of.id}/traveler-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
