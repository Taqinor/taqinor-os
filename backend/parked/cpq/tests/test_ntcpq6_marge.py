"""NTCPQ6 — SeuilMargeFamille + drapeau interne marge_sous_seuil (staff only)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cpq.models import SeuilMargeFamille
from apps.cpq.selectors import devis_marge_sous_seuil
from apps.stock.models import Categorie
from apps.ventes.models import LigneDevis
from apps.ventes.serializers import DevisSerializer
from testkit.factories import (
    CompanyFactory, ProduitFactory, DevisFactory, UserFactory,
)


class TestMargeSousSeuil(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs')
        # Marge = (1000-900)/1000 = 10% < seuil 30% → sous seuil.
        self.produit = ProduitFactory(
            company=self.company, categorie=self.categorie,
            prix_achat=Decimal('900.00'), prix_vente=Decimal('1000.00'))
        self.devis = DevisFactory(company=self.company)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('1000.00'))
        SeuilMargeFamille.objects.create(
            company=self.company, categorie=self.categorie,
            marge_min_pct=Decimal('30.00'))

    def test_selector_detecte_sous_seuil(self):
        self.assertTrue(devis_marge_sous_seuil(self.devis))

    def test_selector_faux_sans_seuil(self):
        SeuilMargeFamille.objects.all().delete()
        self.assertFalse(devis_marge_sous_seuil(self.devis))

    def test_serializer_staff_voit_le_flag(self):
        factory = APIRequestFactory()
        request = factory.get('/')
        force_authenticate(request, user=self.user)
        request.user = self.user
        data = DevisSerializer(self.devis, context={'request': request}).data
        self.assertIn('marge_sous_seuil', data)
        self.assertTrue(data['marge_sous_seuil'])

    def test_serializer_sans_request_retire_la_cle(self):
        data = DevisSerializer(self.devis, context={}).data
        self.assertNotIn('marge_sous_seuil', data)
