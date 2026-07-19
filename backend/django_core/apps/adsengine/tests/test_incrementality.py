"""PUB38 — Tests du harnais MINIMAL d'incrémentalité geo-holdout.

Prouve : les helpers PURS (ratio, fourchette large, confiance) ; le rapport
complet sur des fixtures ERP réelles (leads + devis acceptés, par ville) via
``apps.crm.selectors.reporting_lead_rows`` ; la validation honnête (zone tenue
vide, périodes invalides/chevauchantes) ; la vue lecture seule gatée ; la
commande de management. AUCUNE action automatique nulle part.
"""
import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import incrementality
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

User = get_user_model()
URL = '/api/django/adsengine/reporting/incrementalite/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PureHelperTests(SimpleTestCase):
    def test_normalize_ville(self):
        self.assertEqual(incrementality._normalize_ville('  Agadir '), 'agadir')
        self.assertEqual(incrementality._normalize_ville(None), '')

    def test_rate_change_zero_before_is_none(self):
        self.assertIsNone(incrementality._rate_change(0, 10))

    def test_rate_change_computes_ratio(self):
        self.assertAlmostEqual(incrementality._rate_change(4, 8), 1.0)
        self.assertAlmostEqual(incrementality._rate_change(10, 5), -0.5)

    def test_wide_interval_zero_is_zero(self):
        self.assertEqual(incrementality._wide_interval(0), (0, 0))

    def test_wide_interval_widens_with_n(self):
        low5, high5 = incrementality._wide_interval(5)
        low50, high50 = incrementality._wide_interval(50)
        self.assertLessEqual(low5, 5)
        self.assertGreaterEqual(high5, 5)
        # La largeur ABSOLUE grandit avec n (bruit ~ sqrt(n)), la largeur
        # RELATIVE (en %) rétrécit — les deux propriétés attendues d'une
        # approximation Poisson honnête.
        self.assertGreater(high50 - low50, high5 - low5)

    def test_confidence_faible_below_threshold(self):
        self.assertEqual(incrementality._confidence_label(2, 20, 20, 20), 'faible')

    def test_confidence_moyenne_above_threshold(self):
        self.assertEqual(
            incrementality._confidence_label(15, 20, 30, 40), 'moyenne')

    def test_bucket_counts_splits_held_vs_active_and_ignores_unknown_ville(self):
        rows = [
            {'ville': 'Agadir', 'created_date': datetime.date(2026, 1, 5),
             'signature_date': None},
            {'ville': 'agadir ', 'created_date': datetime.date(2026, 1, 6),
             'signature_date': datetime.date(2026, 1, 10)},
            {'ville': 'Casablanca', 'created_date': datetime.date(2026, 1, 7),
             'signature_date': datetime.date(2026, 1, 20)},
            {'ville': '', 'created_date': datetime.date(2026, 1, 8),
             'signature_date': datetime.date(2026, 1, 8)},
            {'ville': None, 'created_date': datetime.date(2026, 1, 8),
             'signature_date': None},
        ]
        held, active = incrementality._bucket_counts(
            rows, {'agadir'}, date_start=datetime.date(2026, 1, 1),
            date_end=datetime.date(2026, 1, 31))
        self.assertEqual(held, {'leads': 2, 'signatures': 1})
        self.assertEqual(active, {'leads': 1, 'signatures': 1})

    def test_bucket_counts_respects_date_window(self):
        rows = [
            {'ville': 'Agadir', 'created_date': datetime.date(2025, 1, 1),
             'signature_date': None},
        ]
        held, _active = incrementality._bucket_counts(
            rows, {'agadir'}, date_start=datetime.date(2026, 1, 1),
            date_end=datetime.date(2026, 1, 31))
        self.assertEqual(held, {'leads': 0, 'signatures': 0})


class GeoHoldoutReportValidationTests(SimpleTestCase):
    def test_empty_held_villes_is_invalid(self):
        report = incrementality.geo_holdout_report(
            None, held_villes=[], baseline_start=datetime.date(2026, 1, 1),
            baseline_end=datetime.date(2026, 1, 31),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))
        self.assertFalse(report['valide'])
        self.assertIn('erreur_fr', report)

    def test_blank_villes_only_is_invalid(self):
        report = incrementality.geo_holdout_report(
            None, held_villes=['   ', ''],
            baseline_start=datetime.date(2026, 1, 1),
            baseline_end=datetime.date(2026, 1, 31),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))
        self.assertFalse(report['valide'])

    def test_inverted_period_is_invalid(self):
        report = incrementality.geo_holdout_report(
            None, held_villes=['Agadir'],
            baseline_start=datetime.date(2026, 1, 31),
            baseline_end=datetime.date(2026, 1, 1),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))
        self.assertFalse(report['valide'])

    def test_missing_date_is_invalid(self):
        report = incrementality.geo_holdout_report(
            None, held_villes=['Agadir'], baseline_start=None,
            baseline_end=datetime.date(2026, 1, 31),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))
        self.assertFalse(report['valide'])

    def test_overlapping_periods_is_invalid(self):
        report = incrementality.geo_holdout_report(
            None, held_villes=['Agadir'],
            baseline_start=datetime.date(2026, 1, 1),
            baseline_end=datetime.date(2026, 2, 15),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))
        self.assertFalse(report['valide'])


class GeoHoldoutReportEngineTests(TestCase):
    """Câblage bout-en-bout sur données ERP réelles (leads + devis acceptés)."""

    def setUp(self):
        self.company = Company.objects.create(nom='GH Co', slug='gh-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='GH',
            email='gh@example.com', telephone='+212600000099')
        self._n = 0

    def _lead(self, ville, created):
        lead = Lead.objects.create(
            company=self.company, nom=f'Lead {ville} {created}', ville=ville)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.make_aware(
                datetime.datetime.combine(created, datetime.time.min)))
        return lead

    def _sign(self, lead, signed_on):
        self._n += 1
        Devis.objects.create(
            company=self.company, reference=f'DEV-GH-{self._n:04d}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), date_acceptation=signed_on)

    def test_full_report_computes_lift_and_confidence(self):
        # Zone tenue (Agadir, pub coupée) : 4 signatures en référence, 4 en
        # test — pas de croissance. Zone active (Casablanca) : 4 -> 8 —
        # double. Chaque lead créé la veille de sa signature (recul couvert
        # par LOOKBACK_DAYS).
        for i in range(4):
            lead = self._lead('Agadir', datetime.date(2026, 1, 5 + i))
            self._sign(lead, datetime.date(2026, 1, 10 + i))
        for i in range(4):
            lead = self._lead('Agadir', datetime.date(2026, 2, 5 + i))
            self._sign(lead, datetime.date(2026, 2, 10 + i))
        for i in range(4):
            lead = self._lead('Casablanca', datetime.date(2026, 1, 5 + i))
            self._sign(lead, datetime.date(2026, 1, 10 + i))
        for i in range(8):
            lead = self._lead('Casablanca', datetime.date(2026, 2, 5 + i))
            self._sign(lead, datetime.date(2026, 2, 10 + i))

        report = incrementality.geo_holdout_report(
            self.company, held_villes=['Agadir'],
            baseline_start=datetime.date(2026, 1, 1),
            baseline_end=datetime.date(2026, 1, 31),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))

        self.assertTrue(report['valide'])
        self.assertEqual(report['zone_tenue'], ['agadir'])
        self.assertEqual(report['zone_tenue_baseline']['signatures'], 4)
        self.assertEqual(report['zone_tenue_test']['signatures'], 4)
        self.assertEqual(report['zone_active_baseline']['signatures'], 4)
        self.assertEqual(report['zone_active_test']['signatures'], 8)
        self.assertEqual(report['delta_signatures_zone_tenue_pct'], 0.0)
        self.assertEqual(report['delta_signatures_zone_active_pct'], 100.0)
        self.assertEqual(report['confiance'], 'faible')  # < 10 signatures
        self.assertIn('AUCUNE action automatique', report['message_fr'])
        self.assertIn('zone active', report['message_fr'].lower())

    def test_signature_before_window_but_after_baseline_start_is_counted(self):
        # Lead CRÉÉ avant la fenêtre baseline (dans le recul LOOKBACK_DAYS),
        # SIGNÉ pendant la fenêtre test — doit être compté côté signatures
        # test (le cycle de vente peut dépasser la fenêtre de référence).
        lead = self._lead('Agadir', datetime.date(2025, 11, 1))
        self._sign(lead, datetime.date(2026, 2, 15))
        report = incrementality.geo_holdout_report(
            self.company, held_villes=['Agadir'],
            baseline_start=datetime.date(2026, 1, 1),
            baseline_end=datetime.date(2026, 1, 31),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))
        self.assertEqual(report['zone_tenue_test']['signatures'], 1)

    def test_unknown_ville_never_counted_in_either_zone(self):
        lead = self._lead('', datetime.date(2026, 2, 5))
        self._sign(lead, datetime.date(2026, 2, 10))
        report = incrementality.geo_holdout_report(
            self.company, held_villes=['Agadir'],
            baseline_start=datetime.date(2026, 1, 1),
            baseline_end=datetime.date(2026, 1, 31),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))
        self.assertEqual(report['zone_tenue_test']['leads'], 0)
        self.assertEqual(report['zone_active_test']['leads'], 0)

    def test_company_scoped(self):
        other = Company.objects.create(nom='GH Other', slug='gh-other')
        lead = self._lead('Agadir', datetime.date(2026, 2, 5))
        self._sign(lead, datetime.date(2026, 2, 10))
        report = incrementality.geo_holdout_report(
            other, held_villes=['Agadir'],
            baseline_start=datetime.date(2026, 1, 1),
            baseline_end=datetime.date(2026, 1, 31),
            test_start=datetime.date(2026, 2, 1),
            test_end=datetime.date(2026, 2, 28))
        self.assertEqual(report['zone_tenue_test']['leads'], 0)


class GeoHoldoutReportViewTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='GHV Co', slug='ghv-co')
        self.viewer = make_user(self.company, 'ghviewer', ['adsengine_view'])

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'ghnobody', [])
        resp = auth(nobody).get(URL, {
            'villes': 'Agadir', 'baseline_debut': '2026-01-01',
            'baseline_fin': '2026-01-31', 'test_debut': '2026-02-01',
            'test_fin': '2026-02-28'})
        self.assertEqual(resp.status_code, 403)

    def test_returns_honest_invalid_report_without_params(self):
        resp = auth(self.viewer).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['valide'])

    def test_valid_params_return_report(self):
        resp = auth(self.viewer).get(URL, {
            'villes': 'Agadir,Essaouira', 'baseline_debut': '2026-01-01',
            'baseline_fin': '2026-01-31', 'test_debut': '2026-02-01',
            'test_fin': '2026-02-28'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['valide'])
        self.assertEqual(resp.data['zone_tenue'], ['agadir', 'essaouira'])


class GeoHoldoutReportCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='GHC Co', slug='ghc-co')

    def test_unknown_company_raises(self):
        with self.assertRaises(CommandError):
            call_command(
                'geo_holdout_report', '--company', 'no-such-slug',
                '--villes', 'Agadir', '--baseline-debut', '2026-01-01',
                '--baseline-fin', '2026-01-31', '--test-debut', '2026-02-01',
                '--test-fin', '2026-02-28')

    def test_invalid_report_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command(
                'geo_holdout_report', '--company', 'ghc-co',
                '--villes', 'Agadir', '--baseline-debut', '2026-02-01',
                '--baseline-fin', '2026-01-31', '--test-debut', '2026-02-01',
                '--test-fin', '2026-02-28')

    def test_valid_run_prints_french_summary(self):
        out = StringIO()
        call_command(
            'geo_holdout_report', '--company', 'ghc-co',
            '--villes', 'Agadir', '--baseline-debut', '2026-01-01',
            '--baseline-fin', '2026-01-31', '--test-debut', '2026-02-01',
            '--test-fin', '2026-02-28', '--json', stdout=out)
        output = out.getvalue()
        self.assertIn('Zone tenue', output)
        self.assertIn('AUCUNE action automatique', output)
        # --json ajoute le rapport complet en plus du résumé.
        self.assertIn('"valide": true', output)
