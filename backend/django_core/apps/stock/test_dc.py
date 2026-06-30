"""Tests des tâches DC (référentiels uniques / câblage masters) du lot Stock.

Couvre :
  - DC15 : identité légale fournisseur (ICE/IF/RC/RIB).
  - DC28 : résolveur unique `cout_achat_courant` (accord/dernier payé/fallback).
  - DC30/DC31 : sélecteur d'identité tiers fournisseur consommé par
    Compta (comptes auxiliaires) et Contrats (parties) — jamais re-saisir
    nom/ICE/RIB sur le compte ou la partie.

INTERNE : les prix d'achat ne sont jamais client-facing.

Run :
    python manage.py test apps.stock.test_dc -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import Produit, Fournisseur

User = get_user_model()


def make_company(slug='dc-co', nom='DC Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class DCBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company(slug='dc-co-2', nom='Autre Co')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste Solaire',
            ice='001234567000089', identifiant_fiscal='IF12345',
            rc='RC987', rib='011780000012345678901234')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=5)


class TestDC15FournisseurIdentite(DCBase):
    """DC15 — Fournisseur porte ICE/IF/RC/RIB, optionnels et persistés."""

    def test_fields_persisted(self):
        f = Fournisseur.objects.get(pk=self.fournisseur.pk)
        self.assertEqual(f.ice, '001234567000089')
        self.assertEqual(f.identifiant_fiscal, 'IF12345')
        self.assertEqual(f.rc, 'RC987')
        self.assertEqual(f.rib, '011780000012345678901234')

    def test_fields_optional(self):
        f = Fournisseur.objects.create(company=self.company, nom='Sans identité')
        self.assertIsNone(f.ice)
        self.assertIsNone(f.identifiant_fiscal)
        self.assertIsNone(f.rc)
        self.assertIsNone(f.rib)
