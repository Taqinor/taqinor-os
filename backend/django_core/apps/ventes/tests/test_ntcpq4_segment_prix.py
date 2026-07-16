"""NTCPQ4 — Listes de prix multi-segment + exclusion des listes expirées."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.ventes.models import ListePrix, LignePrixListe
from apps.ventes.services import prix_applicable
from testkit.factories import CompanyFactory, ClientFactory, ProduitFactory


class TestSegmentPrix(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'))
        # Client au segment 'particulier' (type_client par défaut).
        self.client_obj = ClientFactory(company=self.company)
        self.segment = self.client_obj.type_client

    def _liste(self, **kw):
        return ListePrix.objects.create(
            company=self.company, nom='Segment', segment_client=self.segment,
            **kw)

    def test_liste_segment_active_est_retenue(self):
        liste = self._liste()
        LignePrixListe.objects.create(
            liste=liste, produit=self.produit,
            prix_unitaire=Decimal('850.00'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client_obj)
        self.assertEqual(resolved['prix'], Decimal('850.00'))
        self.assertEqual(resolved['source'], 'liste')

    def test_liste_segment_expiree_jamais_retenue(self):
        hier = timezone.now().date() - timedelta(days=1)
        avant_hier = hier - timedelta(days=30)
        liste = self._liste(date_debut=avant_hier, date_fin=hier)
        LignePrixListe.objects.create(
            liste=liste, produit=self.produit,
            prix_unitaire=Decimal('850.00'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client_obj)
        # Liste expirée : jamais retenue même si le segment correspond.
        self.assertEqual(resolved['prix'], Decimal('1000.00'))
        self.assertEqual(resolved['source'], 'standard')

    def test_liste_assignee_prime_sur_segment(self):
        assignee = ListePrix.objects.create(
            company=self.company, nom='Assignée')
        LignePrixListe.objects.create(
            liste=assignee, produit=self.produit,
            prix_unitaire=Decimal('700.00'))
        self.client_obj.liste_prix = assignee
        self.client_obj.save()
        # une liste segment concurrente existe aussi
        seg = self._liste()
        LignePrixListe.objects.create(
            liste=seg, produit=self.produit, prix_unitaire=Decimal('999.00'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client_obj)
        self.assertEqual(resolved['prix'], Decimal('700.00'))
