"""NTMFG23 — Rapport imprimable « Ordre de Fabrication » (fiche de
lancement) distinct du traveler.

Critère : le PDF se génère pour un OF planifié, disponibilité par ligne
exacte vs stock au moment de la génération, aucun montant dans le document
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


def make_produit(company, nom='Produit', quantite_stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=500, prix_achat=200, tva=20,
        quantite_stock=quantite_stock)


class FicheLancementPayloadTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-fl-1', 'MRP FicheLancement 1')
        self.composant = make_produit(self.company, 'Composant', quantite_stock=3)
        self.produit = make_produit(self.company, 'Composite')
        self.kit = None  # pas de nomenclature stock.KitProduit dans ce test simple.
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-FL', nom='Poste FL',
            cout_horaire=Decimal('80'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme FL', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op FL', temps_unitaire_min=Decimal('10'))
        self.of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=2,
            gamme=self.gamme)
        confirmer_of(self.of)
        self.of.refresh_from_db()

    def test_gamme_resumee_dans_l_ordre(self):
        payload = mrp_pdf._gamme_resumee_payload(self.of)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['ordre'], 1)
        self.assertEqual(payload[0]['poste_nom'], 'Poste FL')

    def test_nomenclature_vide_sans_reservation(self):
        # Pas de kit_source sur la gamme -> aucune réservation créée.
        payload = mrp_pdf._nomenclature_payload(self.of)
        self.assertEqual(payload, [])

    def test_aucun_prix_dans_le_contexte_ni_le_code(self):
        payload = mrp_pdf._gamme_resumee_payload(self.of)
        for op in payload:
            self.assertNotIn('prix_achat', op)
            self.assertNotIn('cout_horaire', op)
        source = inspect.getsource(mrp_pdf)
        self.assertNotIn('prix_achat', source)
        self.assertNotIn('prix_vente', source)
        self.assertNotIn('cout_horaire', source)


class FicheLancementPdfApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-fl-api-1', 'MRP FicheLancement API 1')
        self.user = make_user(self.company, 'mrp-fl-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-FL-API', nom='Poste API')
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
            f'/api/django/mrp/ordres-fabrication/{self.of.id}/fiche-lancement-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
