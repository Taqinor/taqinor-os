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


class TestAsav103PertesApi(TestCase):
    """ASAV103 — pertes catégorisées rendues utilisables : action
    company-scopée (responsable/admin) conforme au contrat partagé
    ``contract_samples/pertes_categorisees.json``."""

    def setUp(self):
        import json
        from pathlib import Path

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.monitoring.models import MonitoringConfig

        User = get_user_model()
        self.contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'pertes_categorisees.json').read_text(encoding='utf-8'))
        self.company, _ = Company.objects.get_or_create(
            slug='asav103-co', defaults={'nom': 'ASAV103 Co'})
        self.autre, _ = Company.objects.get_or_create(
            slug='asav103-b', defaults={'nom': 'ASAV103 B'})
        inst = make_inst(self.company, 'ASAV103-1')
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=inst)
        UnderperformanceFlag.objects.create(
            company=self.company, installation=inst,
            ratio_pct=Decimal('60'), is_open=True)
        aujourdhui = timezone.localdate()
        ProductionReading.objects.create(
            company=self.company, installation=inst,
            date=aujourdhui - timedelta(days=1), energy_kwh=Decimal('5'),
            motif_limitation='Écrêtement réseau')

        def client_de(username, role, company):
            api = APIClient()
            api.force_authenticate(User.objects.create_user(
                username=username, password='x', role_legacy=role,
                company=company))
            return api
        self.api = client_de('asav103_resp', 'responsable', self.company)
        self.api_b = client_de('asav103_b', 'admin', self.autre)
        self.api_normal = client_de('asav103_n', 'normal', self.company)
        self.url = f'/api/django/monitoring/configs/{self.config.id}/pertes/'

    def test_pertes_affirment_le_contrat_partage(self):
        r = self.api.get(self.url + '?window_days=30')
        self.assertEqual(r.status_code, 200, r.data)
        corps = r.json()
        self.assertEqual(set(corps), set(self.contrat['exemple']))
        self.assertEqual(corps['window_days'], 30)
        self.assertIsNone(corps['ombrage_pct'])
        # Nombres servis en JSON ; panne et écrêtement mesurés (> 0).
        self.assertGreater(corps['panne_pct'], 0)
        self.assertGreater(corps['curtailment_pct'], 0)

    def test_autre_societe_404_et_normal_403(self):
        self.assertEqual(self.api_b.get(self.url).status_code, 404)
        self.assertEqual(self.api_normal.get(self.url).status_code, 403)
