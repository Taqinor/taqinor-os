"""NTMAR12 — Échéancier des 4 acomptes IS matérialisés + export SIMPL-IS.

Critère : un exercice avec IS N-1 connu génère 4 acomptes datés + un fichier
IS exportable."""
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import AcompteIS, ExerciceComptable

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_exercice(company, annee=2026):
    return ExerciceComptable.objects.create(
        company=company, libelle=f'Exercice {annee}',
        date_debut=date(annee, 1, 1), date_fin=date(annee, 12, 31))


class MaterialiserAcomptesIsTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-is', 'NTMAR IS')
        services.seed_plan_comptable(self.company)
        self.exercice = make_exercice(self.company)

    def test_materialise_four_dated_instalments(self):
        acomptes = services.materialiser_acomptes_is(
            self.company, self.exercice, is_reference=Decimal('40000'))
        self.assertEqual(len(acomptes), 4)
        self.assertEqual(
            AcompteIS.objects.filter(
                company=self.company, exercice=self.exercice).count(), 4)
        # 25 % chacun de 40 000 = 10 000.
        self.assertEqual(acomptes[0].montant, Decimal('10000.00'))
        for a in acomptes:
            self.assertIsNotNone(a.date_echeance)

    def test_idempotent(self):
        services.materialiser_acomptes_is(
            self.company, self.exercice, is_reference=Decimal('40000'))
        services.materialiser_acomptes_is(
            self.company, self.exercice, is_reference=Decimal('40000'))
        self.assertEqual(
            AcompteIS.objects.filter(
                company=self.company, exercice=self.exercice).count(), 4)

    def test_wrong_company_rejected(self):
        from django.core.exceptions import ValidationError
        other = make_company('ntmar-is-other', 'Other')
        with self.assertRaises(ValidationError):
            services.materialiser_acomptes_is(
                other, self.exercice, is_reference=Decimal('40000'))


class ExportSimplIsTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-is2', 'NTMAR IS2')
        services.seed_plan_comptable(self.company)
        self.exercice = make_exercice(self.company)

    def test_export_reloads_with_acomptes(self):
        xml = services.export_simpl_is(
            self.company, self.exercice, is_reference=Decimal('40000'))
        root = ET.fromstring(xml.split('-->', 1)[1])
        self.assertTrue(root.tag.endswith('DeclarationIS'))
        acomptes = root.find('Acomptes').findall('Acompte')
        self.assertEqual(len(acomptes), 4)
        codes = {p.get('code') for p in root.findall('Poste')}
        for expected in ('ResultatFiscal', 'ISDu', 'TotalAcomptes',
                         'Regularisation'):
            self.assertIn(expected, codes)
