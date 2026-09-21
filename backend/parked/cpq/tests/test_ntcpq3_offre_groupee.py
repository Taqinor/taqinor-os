"""NTCPQ3 — OffreGroupee : application au devis à prix cascadé."""
from decimal import Decimal

from django.test import TestCase

from apps.cpq.models import OffreGroupee, LigneOffreGroupee
from apps.cpq import services
from testkit.factories import (
    CompanyFactory, ProduitFactory, DevisFactory,
)


class TestOffreGroupee(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.p1 = ProduitFactory(
            company=self.company, prix_vente=Decimal('2000.00'))
        self.p2 = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'))
        self.devis = DevisFactory(company=self.company)

    def test_bundle_fixe_sous_total_egal_prix_fixe(self):
        offre = OffreGroupee.objects.create(
            company=self.company, nom='Kit résidentiel 3kW',
            prix_total=Decimal('2700.00'))
        LigneOffreGroupee.objects.create(
            offre=offre, produit=self.p1, quantite=Decimal('1'),
            mode_prix=LigneOffreGroupee.ModePrix.FIXE)
        LigneOffreGroupee.objects.create(
            offre=offre, produit=self.p2, quantite=Decimal('1'),
            mode_prix=LigneOffreGroupee.ModePrix.FIXE)
        lignes = services.appliquer_offre_groupee(
            offre=offre, devis=self.devis)
        self.assertEqual(len(lignes), 2)
        # Sous-total HT du devis == prix fixe du bundle au centime.
        self.assertEqual(self.devis.total_ht, Decimal('2700.00'))

    def test_bundle_remise_pct(self):
        offre = OffreGroupee.objects.create(
            company=self.company, nom='Remise pack')
        LigneOffreGroupee.objects.create(
            offre=offre, produit=self.p1, quantite=Decimal('1'),
            mode_prix=LigneOffreGroupee.ModePrix.REMISE_PCT,
            valeur=Decimal('10'))
        lignes = services.appliquer_offre_groupee(
            offre=offre, devis=self.devis)
        # 2000 - 10% = 1800
        self.assertEqual(lignes[0].total_ht, Decimal('1800.00'))

    def test_bundle_prix_composant(self):
        offre = OffreGroupee.objects.create(
            company=self.company, nom='Pack composant')
        LigneOffreGroupee.objects.create(
            offre=offre, produit=self.p1, quantite=Decimal('2'),
            mode_prix=LigneOffreGroupee.ModePrix.PRIX_COMPOSANT,
            valeur=Decimal('1500.00'))
        lignes = services.appliquer_offre_groupee(
            offre=offre, devis=self.devis)
        self.assertEqual(lignes[0].prix_unitaire, Decimal('1500.00'))
        self.assertEqual(lignes[0].total_ht, Decimal('3000.00'))
