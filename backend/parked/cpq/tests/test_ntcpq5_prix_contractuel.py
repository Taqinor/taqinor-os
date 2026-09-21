"""NTCPQ5 — PrixContractuel prime sur toute liste générique (priorité 1)."""
from decimal import Decimal

from django.test import TestCase

from apps.cpq.models import PrixContractuel
from apps.ventes.models import ListePrix, LignePrixListe
from apps.ventes.services import prix_applicable
from testkit.factories import CompanyFactory, ClientFactory, ProduitFactory


class TestPrixContractuel(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'))
        self.client_obj = ClientFactory(company=self.company)

    def test_prix_contractuel_ecrase_liste_segment(self):
        # Liste segment qui serait normalement retenue.
        liste = ListePrix.objects.create(
            company=self.company, nom='Segment',
            segment_client=self.client_obj.type_client)
        LignePrixListe.objects.create(
            liste=liste, produit=self.produit,
            prix_unitaire=Decimal('850.00'))
        # Prix contractuel actif pour ce client/produit.
        PrixContractuel.objects.create(
            company=self.company, client=self.client_obj,
            produit=self.produit, prix_ht=Decimal('600.00'),
            motif='Accord cadre 2026')
        resolved = prix_applicable(
            produit=self.produit, client=self.client_obj)
        self.assertEqual(resolved['prix'], Decimal('600.00'))
        self.assertEqual(resolved['source'], 'contractuel')

    def test_prix_contractuel_expire_ignore(self):
        from datetime import timedelta
        from django.utils import timezone
        hier = timezone.now().date() - timedelta(days=1)
        PrixContractuel.objects.create(
            company=self.company, client=self.client_obj,
            produit=self.produit, prix_ht=Decimal('600.00'),
            date_fin=hier)
        resolved = prix_applicable(
            produit=self.produit, client=self.client_obj)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))
        self.assertEqual(resolved['source'], 'standard')

    def test_scope_societe(self):
        other = CompanyFactory()
        PrixContractuel.objects.create(
            company=other, client=self.client_obj, produit=self.produit,
            prix_ht=Decimal('600.00'))
        # company_id du client (self.company) ne matche pas la contractuelle
        # d'une autre société → jamais retenue.
        resolved = prix_applicable(
            produit=self.produit, client=self.client_obj)
        self.assertEqual(resolved['source'], 'standard')
