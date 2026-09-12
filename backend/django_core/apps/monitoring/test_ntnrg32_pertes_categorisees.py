"""NTNRG32 — Pertes catégorisées (soiling/ombrage/panne/curtailment).

Couvre :
  * un système avec un drapeau de sous-performance OUVERT expose sa part de
    perte « panne » distincte du soiling ;
  * un système avec des relevés `motif_limitation` renseigné expose une part
    « curtailment » ;
  * l'ombrage reste TOUJOURS `None` explicite (pas de relevé infra-journalier
    dans ce module) — jamais un 0 trompeur ;
  * un système sans aucun flag/motif renvoie 0 % pour panne/curtailment (des
    catégories réellement mesurables à zéro, pas des données manquantes).

Run :
    python manage.py test apps.monitoring.test_ntnrg32_pertes_categorisees -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.analytics import pertes_categorisees
from apps.monitoring.models import ProductionReading, UnderperformanceFlag


def make_inst(company, ref):
    client = Client.objects.create(
        company=company, nom='Cli', prenom=ref,
        email=f'{ref.lower()}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        puissance_installee_kwc=Decimal('10'))


class TestPertesCategorisees(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg32-co', defaults={'nom': 'NTNRG32 Co'})
        self.today = date(2026, 6, 30)

    def test_ombrage_est_toujours_none(self):
        inst = make_inst(self.company, 'NTNRG32-1')
        result = pertes_categorisees(inst, window_days=10, today=self.today)
        self.assertIsNone(result['ombrage_pct'])

    def test_sans_flag_ni_motif_zero_pourcent(self):
        inst = make_inst(self.company, 'NTNRG32-2')
        result = pertes_categorisees(inst, window_days=10, today=self.today)
        self.assertEqual(result['panne_pct'], Decimal('0.00'))
        self.assertEqual(result['curtailment_pct'], Decimal('0.00'))

    def test_flag_ouvert_compte_dans_la_fenetre(self):
        inst = make_inst(self.company, 'NTNRG32-3')
        flag = UnderperformanceFlag.objects.create(
            company=self.company, installation=inst, is_open=True)
        # Force la date de création à 5 jours avant `today` (fenêtre 10 j).
        flag.date_creation = timezone.make_aware(
            timezone.datetime.combine(
                self.today - timedelta(days=5), timezone.datetime.min.time()))
        flag.save(update_fields=['date_creation'])
        result = pertes_categorisees(inst, window_days=10, today=self.today)
        # 6 jours couverts (du jour de création à aujourd'hui inclus) / 10.
        self.assertEqual(result['panne_pct'], Decimal('60.00'))

    def test_flag_ferme_hors_fenetre_ne_compte_pas(self):
        inst = make_inst(self.company, 'NTNRG32-4')
        flag = UnderperformanceFlag.objects.create(
            company=self.company, installation=inst, is_open=False)
        vieux = timezone.make_aware(
            timezone.datetime.combine(
                self.today - timedelta(days=100), timezone.datetime.min.time()))
        flag.date_creation = vieux
        flag.date_cloture = vieux + timedelta(days=1)
        flag.save(update_fields=['date_creation', 'date_cloture'])
        result = pertes_categorisees(inst, window_days=10, today=self.today)
        self.assertEqual(result['panne_pct'], Decimal('0.00'))

    def test_curtailment_compte_les_jours_avec_motif_structure(self):
        inst = make_inst(self.company, 'NTNRG32-5')
        ProductionReading.objects.create(
            company=self.company, installation=inst,
            date=self.today - timedelta(days=1), energy_kwh=Decimal('50'),
            motif_limitation='Limitation réseau ONEE')
        ProductionReading.objects.create(
            company=self.company, installation=inst,
            date=self.today - timedelta(days=2), energy_kwh=Decimal('60'))
        result = pertes_categorisees(inst, window_days=10, today=self.today)
        # 1 jour sur 10 porte un motif de limitation → 10 %.
        self.assertEqual(result['curtailment_pct'], Decimal('10.00'))

    def test_soiling_reste_relaye_tel_quel(self):
        inst = make_inst(self.company, 'NTNRG32-6')
        result = pertes_categorisees(inst, window_days=10, today=self.today)
        # Sans historique de PR mensuel exploitable, le soiling est None
        # (comportement de `soiling_assessment` inchangé, jamais réimplémenté
        # ici).
        self.assertIsNone(result['soiling_pct'])
