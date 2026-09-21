"""XACC11 — Prorata de déduction TVA & TVA non déductible.

Couvre :

* une facture de véhicule de tourisme (famille non déductible) ne crédite/
  débite AUCUN 3455 : la TVA reste dans la charge ;
* un prorata 80 % réduit la déduction de 20 % (le reliquat rejoint la
  charge), écriture toujours équilibrée ;
* défaut 100 % (aucun exercice paramétré) = comportement actuel intact (non-
  régression exacte, mêmes montants qu'avant XACC11) ;
* le relevé FG138 marque les lignes concernées par le prorata.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    EcritureComptable, ExerciceComptable, FamilleTvaNonDeductible,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class _FakeDoc(SimpleNamespace):
    """Stub duck-typé d'un document stock (lu par valeur, jamais importé)."""


class VehiculeTourismeNonDeductibleTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc11-vehicule', 'XACC11 Véhicule Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        FamilleTvaNonDeductible.objects.create(
            company=self.co, famille='vehicule_tourisme',
            libelle='Véhicules de tourisme')

    def _facture(self, id=1):
        return _FakeDoc(
            id=id, company=self.co, reference='FF-VEH-1',
            date_facture=date(2026, 1, 15), fournisseur_id=99,
            montant_ht=Decimal('200000'), montant_tva=Decimal('40000'),
            montant_ttc=Decimal('240000'))

    def test_aucune_ligne_3455_pour_vehicule_tourisme(self):
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(), force=True, famille_charge='vehicule_tourisme')
        self.assertTrue(ecr.est_equilibree)
        self.assertFalse(
            ecr.lignes.filter(compte__numero='3455').exists())

    def test_tva_reste_dans_la_charge(self):
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(), force=True, famille_charge='vehicule_tourisme')
        charge = ecr.lignes.get(compte__numero='6111')
        # HT (200000) + TVA entière (40000) = 240000 dans la charge.
        self.assertEqual(charge.debit, Decimal('240000'))
        fourn = ecr.lignes.get(compte__numero='4411')
        self.assertEqual(fourn.credit, Decimal('240000'))

    def test_famille_non_active_redevient_deductible(self):
        FamilleTvaNonDeductible.objects.filter(
            company=self.co, famille='vehicule_tourisme').update(actif=False)
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(id=2), force=True,
            famille_charge='vehicule_tourisme')
        self.assertTrue(
            ecr.lignes.filter(compte__numero='3455').exists())


class ProrataTvaTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc11-prorata', 'XACC11 Prorata Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), libelle='Exercice 2026',
            coefficient_prorata_tva=Decimal('80'))

    def _facture(self, id=1):
        return _FakeDoc(
            id=id, company=self.co, reference='FF-PRO-1',
            date_facture=date(2026, 3, 10), fournisseur_id=55,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))

    def test_prorata_80_reduit_la_deduction_de_20pct(self):
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(), force=True)
        self.assertTrue(ecr.est_equilibree)
        # TVA déductible = 200 × 80% = 160 ; reliquat 40 dans la charge.
        tva_line = ecr.lignes.get(compte__numero='3455')
        self.assertEqual(tva_line.debit, Decimal('160.00'))
        charge = ecr.lignes.get(compte__numero='6111')
        self.assertEqual(charge.debit, Decimal('1040.00'))  # 1000 + 40.
        fourn = ecr.lignes.get(compte__numero='4411')
        self.assertEqual(fourn.credit, Decimal('1200'))

    def test_prorata_marque_dans_fg138(self):
        services.ecriture_pour_facture_fournisseur(
            self._facture(id=2), force=True)
        rapport = selectors.releve_deductions_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        self.assertEqual(len(rapport['lignes']), 1)
        self.assertTrue(rapport['lignes'][0]['prorata_applique'])
        self.assertEqual(rapport['lignes'][0]['tva'], Decimal('160.00'))

    def test_coefficient_hors_bornes_refuse(self):
        from django.core.exceptions import ValidationError
        self.exercice.coefficient_prorata_tva = Decimal('150')
        with self.assertRaises(ValidationError):
            self.exercice.full_clean()


class DefautCentPourcentNonRegressionTests(TestCase):
    """Défaut 100 % (aucun exercice paramétré) = comportement inchangé."""

    def setUp(self):
        self.co = make_company('xacc11-defaut', 'XACC11 Défaut Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def _facture(self, id=1):
        return _FakeDoc(
            id=id, company=self.co, reference='FF-DEF-1',
            date_facture=date(2026, 1, 15), fournisseur_id=77,
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'))

    def test_sans_exercice_deduction_integrale(self):
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(), force=True)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(
            ecr.lignes.get(compte__numero='6111').debit, Decimal('100'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='3455').debit, Decimal('20'))
        self.assertNotIn(
            'prorata', ecr.lignes.get(compte__numero='3455').libelle)

    def test_exercice_100pct_explicite_identique(self):
        ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), libelle='Exercice 2026',
            coefficient_prorata_tva=Decimal('100'))
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(id=2), force=True)
        self.assertEqual(
            ecr.lignes.get(compte__numero='3455').debit, Decimal('20'))
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 1)


class ReferentielHelpersTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc11-helpers', 'XACC11 Helpers Co')
        services.seed_plan_comptable(self.co)

    def test_est_famille_non_deductible_sans_famille(self):
        self.assertFalse(services.est_famille_non_deductible(self.co, None))
        self.assertFalse(services.est_famille_non_deductible(self.co, ''))

    def test_coefficient_prorata_tva_defaut_sans_date(self):
        self.assertEqual(
            services.coefficient_prorata_tva(self.co, None), Decimal('100'))
