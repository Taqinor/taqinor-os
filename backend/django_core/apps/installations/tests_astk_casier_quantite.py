"""ASTK194 — `appliquer_mouvement_casier` tient `BinAffectation.quantite`.

Avant : aucun service — la quantité par casier n'était écrite que par le
CRUD manuel (BinAffectationViewSet), jamais par les mouvements. Le service
décrémente la source, incrémente la destination (affectation créée au
besoin), ne passe jamais sous zéro et vérifie la société.

Run :
    python manage.py test apps.installations.tests_astk_casier_quantite
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.installations.models_bin_location import BinAffectation, BinLocation
from apps.installations.services import appliquer_mouvement_casier
from apps.stock.models import Produit
from apps.stock.services import ensure_emplacements


class CasierQuantiteTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-astk194', defaults={'nom': 'Co ASTK194'})
        depot = ensure_emplacements(self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK194', sku='SKU-ASTK194',
            prix_vente=Decimal('100'), quantite_stock=20)
        self.s = BinLocation.objects.create(
            company=self.company, emplacement=depot, code='A-01-01')
        self.c = BinLocation.objects.create(
            company=self.company, emplacement=depot, code='A-01-02')
        BinAffectation.objects.create(
            company=self.company, bin=self.s, produit=self.produit,
            quantite=10)

    def _qte(self, bin_):
        aff = BinAffectation.objects.filter(
            bin=bin_, produit=self.produit).first()
        return aff.quantite if aff else None

    def test_transfert(self):
        ecart = appliquer_mouvement_casier(
            self.company, self.produit.id, 8, self.s.id, self.c.id)
        self.assertEqual(ecart, 0)
        self.assertEqual(self._qte(self.s), 2)
        self.assertEqual(self._qte(self.c), 8)

    def test_creation_affectation(self):
        self.assertIsNone(self._qte(self.c))
        appliquer_mouvement_casier(
            self.company, self.produit.id, 8, self.s.id, self.c.id)
        appliquer_mouvement_casier(
            self.company, self.produit.id, 3, None, self.c.id)
        self.assertEqual(self._qte(self.c), 11)
        aff = BinAffectation.objects.get(bin=self.c, produit=self.produit)
        self.assertEqual(aff.company_id, self.company.id)

    def test_jamais_negatif(self):
        appliquer_mouvement_casier(
            self.company, self.produit.id, 8, self.s.id, self.c.id)
        ecart = appliquer_mouvement_casier(
            self.company, self.produit.id, 12, self.s.id, None)
        self.assertEqual(self._qte(self.s), 0)
        self.assertEqual(ecart, 10)

    def test_autre_societe_refusee(self):
        autre, _ = Company.objects.get_or_create(
            slug='co-astk194-b', defaults={'nom': 'Co ASTK194 B'})
        with self.assertRaises(ValueError):
            appliquer_mouvement_casier(
                autre, self.produit.id, 1, self.s.id, None)
        depot_b = ensure_emplacements(autre)
        bin_b = BinLocation.objects.create(
            company=autre, emplacement=depot_b, code='B-01-01')
        with self.assertRaises(ValueError):
            appliquer_mouvement_casier(
                self.company, self.produit.id, 1, self.s.id, bin_b.id)
        self.assertEqual(self._qte(self.s), 10)
        self.assertFalse(BinAffectation.objects.filter(bin=bin_b).exists())
