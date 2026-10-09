"""APDF44 (D-APDF-4) — au seed, les produits de prestation « Installation » et
« Transport » sont rangés dans une catégorie de type ``service`` ; prix,
prix d'achat et quantités inchangés ; un second run ne change rien.

Base de départ = la situation constatée en production (C-APDF-014) : les deux
produits semés rangés dans « Accessoires » (``type_equipement='accessoire'``).
Aucun mock : la vraie commande ``seed_catalogue`` sur une vraie base."""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.stock.models import Categorie, Produit
from authentication.models import Company


def _seed(company):
    call_command('seed_catalogue', company_slug=company.slug, stdout=StringIO())


class SeedPrestationsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='APDF44', slug='apdf44-co')
        self.accessoires = Categorie.objects.create(
            company=self.company, nom='Accessoires',
            type_equipement='accessoire')
        # Prix/quantités volontairement DIFFÉRENTS du catalogue : le seed ne
        # doit jamais les réécrire.
        self.avant = {
            'INST-CAT': ('Installation', Decimal('4321.00'),
                         Decimal('1234.00'), 7),
            'TRANS-CAT': ('Transport', Decimal('876.00'),
                          Decimal('543.00'), 3),
        }
        for sku, (nom, pv, pa, qte) in self.avant.items():
            Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                categorie=self.accessoires, prix_vente=pv, prix_achat=pa,
                quantite_stock=qte, tva=Decimal('20.00'))

    def _produit(self, sku):
        return Produit.objects.select_related('categorie').get(
            company=self.company, sku=sku)

    def test_categorie_service(self):
        _seed(self.company)
        for sku in self.avant:
            p = self._produit(sku)
            self.assertIsNotNone(p.categorie, sku)
            self.assertEqual(p.categorie.type_equipement, 'service', sku)
            self.assertEqual(p.categorie.company_id, self.company.id)

    def test_prix_inchanges(self):
        _seed(self.company)
        for sku, (_nom, pv, pa, qte) in self.avant.items():
            p = self._produit(sku)
            self.assertEqual(p.prix_vente, pv, sku)
            self.assertEqual(p.prix_achat, pa, sku)
            self.assertEqual(p.quantite_stock, qte, sku)

    def test_idempotent(self):
        _seed(self.company)
        etat = list(Produit.objects.filter(company=self.company).order_by(
            'pk').values_list('pk', 'categorie_id', 'prix_vente',
                              'prix_achat', 'quantite_stock'))
        nb_categories = Categorie.objects.filter(company=self.company).count()
        _seed(self.company)
        self.assertEqual(
            list(Produit.objects.filter(company=self.company).order_by(
                'pk').values_list('pk', 'categorie_id', 'prix_vente',
                                  'prix_achat', 'quantite_stock')), etat)
        self.assertEqual(
            Categorie.objects.filter(company=self.company).count(),
            nb_categories)
