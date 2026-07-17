"""NTMAR17/18/19 — RAS loyers bordereau, prestation étrangère + convention,
récapitulatif annuel.

Critères : une RAS loyer apparaît sur son bordereau dédié ; une prestation vers
un pays conventionné applique le taux réduit, sans convention le taux plein ; le
récapitulatif annuel consolide par bénéficiaire et par type."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import ConventionFiscale, RetenueSource

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class RasLoyersBordereauTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-ras', 'NTMAR RAS')

    def test_loyers_bordereau_filters_by_type(self):
        services.enregistrer_retenue_source(
            self.company, date_piece=date(2026, 3, 1), base=Decimal('10000'),
            taux=Decimal('10'), type_prestation=RetenueSource.TypePrestation.LOYERS,
            tiers_nom='Bailleur A')
        services.enregistrer_retenue_source(
            self.company, date_piece=date(2026, 3, 2), base=Decimal('5000'),
            taux=Decimal('10'),
            type_prestation=RetenueSource.TypePrestation.HONORAIRES,
            tiers_nom='Consultant B')
        data = selectors.bordereau_versement_ras_par_type(
            self.company, RetenueSource.TypePrestation.LOYERS)
        self.assertEqual(data['type_prestation'], 'loyers')
        self.assertEqual(len(data['lignes']), 1)
        self.assertEqual(data['lignes'][0]['tiers_nom'], 'Bailleur A')
        self.assertEqual(data['total_a_verser'], Decimal('1000'))


class RasPrestationEtrangereTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-ras2', 'NTMAR RAS2')
        ConventionFiscale.objects.create(
            company=self.company, pays='France',
            taux_conventionnel=Decimal('7.00'))

    def test_conventioned_country_applies_reduced_rate(self):
        ras = services.enregistrer_retenue_source(
            self.company, date_piece=date(2026, 4, 1), base=Decimal('10000'),
            type_prestation=RetenueSource.TypePrestation.PRESTATION_ETRANGERE,
            pays_beneficiaire='France', tiers_nom='FR SARL')
        self.assertEqual(ras.taux, Decimal('7.00'))
        self.assertTrue(ras.convention_appliquee)
        self.assertEqual(ras.montant, Decimal('700.00'))

    def test_no_convention_applies_full_rate(self):
        ras = services.enregistrer_retenue_source(
            self.company, date_piece=date(2026, 4, 2), base=Decimal('10000'),
            type_prestation=RetenueSource.TypePrestation.PRESTATION_ETRANGERE,
            pays_beneficiaire='Japon', tiers_nom='JP Ltd')
        self.assertEqual(ras.taux, RetenueSource.TAUX_DEFAUT)
        self.assertFalse(ras.convention_appliquee)


class RecapitulatifRasAnnuelTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-ras3', 'NTMAR RAS3')

    def test_recap_consolidates_by_beneficiary_and_type(self):
        services.enregistrer_retenue_source(
            self.company, date_piece=date(2026, 2, 1), base=Decimal('10000'),
            taux=Decimal('10'),
            type_prestation=RetenueSource.TypePrestation.HONORAIRES,
            tiers_id=42, tiers_type='fournisseur', tiers_nom='Cabinet X')
        services.enregistrer_retenue_source(
            self.company, date_piece=date(2026, 5, 1), base=Decimal('20000'),
            taux=Decimal('10'),
            type_prestation=RetenueSource.TypePrestation.LOYERS,
            tiers_id=42, tiers_type='fournisseur', tiers_nom='Cabinet X')
        recap = selectors.recapitulatif_ras_annuel(self.company, 2026)
        self.assertEqual(len(recap['lignes']), 1)
        ligne = recap['lignes'][0]
        self.assertIn('honoraires', ligne['par_type'])
        self.assertIn('loyers', ligne['par_type'])
        self.assertEqual(ligne['total_retenue'], Decimal('3000'))
        self.assertEqual(recap['total_retenue'], Decimal('3000'))
