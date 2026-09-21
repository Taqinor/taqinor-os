"""NTMAR10/11 — Export SIMPL-TVA (structure DGI) + contrôles pré-dépôt.

Critères : le fichier SIMPL-TVA contient tous les postes et se recharge sans
erreur de structure ; une déclaration incohérente liste des alertes, une saine
renvoie vide."""
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import DeclarationTVA

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class ExportSimplTvaTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-tva', 'NTMAR TVA')
        self.decl = DeclarationTVA.objects.create(
            company=self.company, reference='TVA-202601-0001',
            regime=DeclarationTVA.Regime.MENSUEL,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            tva_collectee=Decimal('10000'), tva_deductible=Decimal('4000'),
            tva_a_declarer=Decimal('6000'))

    def test_export_contains_all_postes_and_reloads(self):
        xml = services.export_simpl_tva(self.decl)
        # Se recharge sans erreur de structure.
        root = ET.fromstring(xml.split('-->', 1)[1])
        self.assertTrue(root.tag.endswith('DeclarationTVA'))
        codes = {p.get('code') for p in root.findall('Poste')}
        for expected in ('TVACollectee', 'TVADeductible', 'TVAADeclarer',
                         'CreditReportable', 'Regime', 'PeriodeDebut'):
            self.assertIn(expected, codes)
        self.assertIn('10000', xml)


class ControlesPredepotTvaTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-tva2', 'NTMAR TVA2')
        services.seed_plan_comptable(self.company)

    def test_healthy_declaration_no_alerts(self):
        # Snapshot cohérent + aucun mouvement GL (0 = 0), pas de crédit.
        decl = DeclarationTVA.objects.create(
            company=self.company, regime=DeclarationTVA.Regime.MENSUEL,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            tva_collectee=Decimal('0'), tva_deductible=Decimal('0'),
            tva_a_declarer=Decimal('0'))
        self.assertEqual(selectors.controles_predepot_tva(decl), [])

    def test_deductible_exceeds_collected_without_credit_flagged(self):
        decl = DeclarationTVA.objects.create(
            company=self.company, regime=DeclarationTVA.Regime.MENSUEL,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            tva_collectee=Decimal('1000'), tva_deductible=Decimal('3000'),
            credit_anterieur=Decimal('0'), tva_a_declarer=Decimal('0'),
            credit_reportable=Decimal('2000'))
        alertes = selectors.controles_predepot_tva(decl)
        self.assertTrue(any('déductible' in a.lower() for a in alertes), alertes)

    def test_gl_mismatch_flagged(self):
        # Snapshot dit 5000 collectée mais le GL est vide → écart signalé.
        decl = DeclarationTVA.objects.create(
            company=self.company, regime=DeclarationTVA.Regime.MENSUEL,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            tva_collectee=Decimal('5000'), tva_deductible=Decimal('0'),
            tva_a_declarer=Decimal('5000'))
        alertes = selectors.controles_predepot_tva(decl)
        self.assertTrue(any('collectée' in a.lower() for a in alertes), alertes)
