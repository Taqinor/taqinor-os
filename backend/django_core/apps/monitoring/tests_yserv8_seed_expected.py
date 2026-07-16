"""Tests YSERV8 — semer ``MonitoringConfig.expected_annual_kwh`` à la réception.

À la mise en service d'un chantier (événement ``core.events.chantier_receptionne``,
YSERV4), le satellite monitoring câble la production attendue déjà calculée en
amont, par priorité :
  1. le test de performance de réception FG278 (``energie_attendue_kwh``) ;
  2. sinon la production annuelle de l'``etude_params`` du devis lié.
Lectures cross-app via ``apps.ventes.selectors`` uniquement.

Couvre :
  * réception avec PR FG278 → config semée depuis le PR (prime sur l'étude) ;
  * réception sans PR mais avec étude devis → config semée depuis l'étude ;
  * valeur manuelle déjà présente → JAMAIS écrasée ;
  * chantier sans étude ni PR → comportement inchangé (reste NULL) ;
  * la valeur semée est bien celle qu'utilise ``evaluate_underperformance``.

Run :
    python manage.py test apps.monitoring.tests_yserv8_seed_expected -v 2
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from core.events import chantier_receptionne
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.ventes.models import Devis, TestPerformanceReception

from apps.monitoring import services
from apps.monitoring.models import MonitoringConfig


def _company(slug='yserv8-co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': 'YS8'})
    return company


def _client(company):
    return Client.objects.create(
        company=company, nom='Client', prenom='YS8',
        email=f'ys8-{company.id}@example.invalid')


def _devis(company, client, *, production=None, num=1):
    etude = {'production_annuelle': production} if production is not None else {}
    return Devis.objects.create(
        company=company, reference=f'DEV-YS8-{num:04d}', client=client,
        taux_tva=Decimal('20'), etude_params=etude)


def _installation(company, client, *, devis=None, ref='CHT-YS8-1'):
    return Installation.objects.create(
        company=company, reference=ref, client=client, devis=devis,
        puissance_installee_kwc=Decimal('5.00'))


class SeedExpectedFromReceptionTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.client_obj = _client(self.company)

    def _receptionner(self, installation):
        chantier_receptionne.send(
            sender=self.__class__, installation=installation,
            user=None, ancien_statut='en_cours')

    def test_seed_priorise_le_pr_de_recette_fg278(self):
        """Le PR FG278 prime sur l'étude devis quand les deux existent."""
        devis = _devis(self.company, self.client_obj, production=8000)
        inst = _installation(self.company, self.client_obj, devis=devis)
        TestPerformanceReception.objects.create(
            company=self.company, chantier=inst,
            energie_attendue_kwh=Decimal('9500'))

        self._receptionner(inst)

        config = MonitoringConfig.objects.get(installation=inst)
        self.assertEqual(config.expected_annual_kwh, Decimal('9500'))

    def test_seed_depuis_etude_devis_sans_pr(self):
        """Sans PR, la production de l'étude du devis est semée."""
        devis = _devis(self.company, self.client_obj, production=8000)
        inst = _installation(self.company, self.client_obj, devis=devis)

        self._receptionner(inst)

        config = MonitoringConfig.objects.get(installation=inst)
        self.assertEqual(config.expected_annual_kwh, Decimal('8000'))

    def test_valeur_manuelle_jamais_ecrasee(self):
        """Une valeur déjà saisie sur la config n'est jamais écrasée."""
        devis = _devis(self.company, self.client_obj, production=8000)
        inst = _installation(self.company, self.client_obj, devis=devis)
        MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            expected_annual_kwh=Decimal('11111'))

        self._receptionner(inst)

        config = MonitoringConfig.objects.get(installation=inst)
        self.assertEqual(config.expected_annual_kwh, Decimal('11111'))

    def test_sans_etude_ni_pr_reste_null(self):
        """Chantier sans étude ni PR → comportement inchangé (reste NULL)."""
        devis = _devis(self.company, self.client_obj, production=None)
        inst = _installation(self.company, self.client_obj, devis=devis)

        self._receptionner(inst)

        config = MonitoringConfig.objects.get(installation=inst)
        self.assertIsNone(config.expected_annual_kwh)

    def test_sans_devis_reste_null(self):
        """Chantier sans devis lié → aucune source, reste NULL."""
        inst = _installation(self.company, self.client_obj, devis=None)

        self._receptionner(inst)

        config = MonitoringConfig.objects.get(installation=inst)
        self.assertIsNone(config.expected_annual_kwh)

    def test_valeur_semee_utilisee_par_evaluation(self):
        """La valeur semée alimente ``_expected_recent_kwh`` (donc l'évaluation)."""
        devis = _devis(self.company, self.client_obj, production=7300)
        inst = _installation(self.company, self.client_obj, devis=devis)

        self._receptionner(inst)

        config = MonitoringConfig.objects.get(installation=inst)
        # 7300 kWh/an → sur la fenêtre récente (services.RECENT_WINDOW_DAYS).
        expected = services._expected_recent_kwh(
            inst, config, services.RECENT_WINDOW_DAYS)
        self.assertIsNotNone(expected)
        annuel = expected * Decimal('365') / Decimal(services.RECENT_WINDOW_DAYS)
        self.assertEqual(annuel.quantize(Decimal('1')), Decimal('7300'))
