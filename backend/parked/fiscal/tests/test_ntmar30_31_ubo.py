"""NTMAR30/31 — Registre UBO + export (structure OMPIC).

Critères : déclarer les UBO d'une société les liste avec leur % ; un total
< 25 % couvert lève un avertissement de complétude. L'export contient chaque
UBO déclaré avec % et type de contrôle."""
from decimal import Decimal

from django.test import TestCase

from apps.fiscal.models import BeneficiaireEffectif
from apps.fiscal.selectors import registre_ubo
from apps.fiscal.services import export_declaration_ubo

from ._fixtures import make_company


class RegistreUboTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-ubo', 'Fiscal UBO')

    def test_registre_lists_beneficiaires_with_percentage(self):
        BeneficiaireEffectif.objects.create(
            company=self.company, nom='Jean Dupont',
            pourcentage_detention=Decimal('40.00'))
        data = registre_ubo(self.company)
        self.assertEqual(len(data['beneficiaires']), 1)
        self.assertEqual(data['total_pourcentage'], Decimal('40.00'))

    def test_incomplete_total_raises_warning(self):
        BeneficiaireEffectif.objects.create(
            company=self.company, nom='Petit Actionnaire',
            pourcentage_detention=Decimal('10.00'))
        data = registre_ubo(self.company)
        self.assertFalse(data['complet'])

    def test_complete_total_no_warning(self):
        BeneficiaireEffectif.objects.create(
            company=self.company, nom='Actionnaire Majoritaire',
            pourcentage_detention=Decimal('60.00'))
        data = registre_ubo(self.company)
        self.assertTrue(data['complet'])


class ExportDeclarationUboTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-ubo-export', 'Fiscal UBO Export')

    def test_export_contains_each_ubo_with_percent_and_type(self):
        BeneficiaireEffectif.objects.create(
            company=self.company, nom='Amine Test',
            pourcentage_detention=Decimal('55.50'),
            type_controle=BeneficiaireEffectif.TypeControle.DIRECT)
        lignes = export_declaration_ubo(self.company)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['nom'], 'Amine Test')
        self.assertEqual(lignes[0]['pourcentage_detention'], '55.50')
        self.assertEqual(lignes[0]['type_controle'], 'Contrôle direct')
