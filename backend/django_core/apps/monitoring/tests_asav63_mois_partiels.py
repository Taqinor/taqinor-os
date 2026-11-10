"""ASAV63 — le premier et le dernier mois PARTIELS sont normalisés par jours
couverts avant tout PR mensuel, pente de dégradation et baseline de soiling.

Run :
    python manage.py test apps.monitoring.tests_asav63_mois_partiels -v2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring import analytics, services
from apps.monitoring.models import MonitoringConfig, ProductionReading
from authentication.models import Company

TODAY = date(2026, 10, 8)


class MoisPartielsTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav63-co', defaults={'nom': 'ASAV63 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV63')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV63', client=client,
            puissance_installee_kwc=Decimal('7.00'))
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))

    def _releves(self, chute_dernier_mois=None):
        # AMON29 — journaliers au profil mensuel du devis (l'attendu n'est
        # plus annuel / 365 à plat).
        for i in range(366):
            jour = TODAY - timedelta(days=365 - i)
            kwh = services.attendu_entre(Decimal('12000'), jour, jour)
            if chute_dernier_mois and jour.month == 9 and jour.year == 2026:
                kwh = kwh * Decimal('0.8')
            kwh = kwh.quantize(Decimal('0.01'))
            ProductionReading.objects.create(
                company=self.company, installation=self.inst, date=jour,
                energy_kwh=kwh, period_days=1)

    def test_nominal_sans_degradation(self):
        self._releves()
        m = analytics.om_metrics(self.inst, today=TODAY)
        self.assertGreaterEqual(float(m['degradation_pct_per_year']), -1.0)
        self.assertLessEqual(float(m['degradation_pct_per_year']), 1.0)
        dernier = m['monthly_pr'][-1]
        self.assertAlmostEqual(float(dernier['pr_pct']), 100.0, delta=2.0)
        self.assertFalse(m['soiling_suspected'])

    def test_nominal_sans_soiling(self):
        self._releves()
        s = analytics.soiling_assessment(self.inst, today=TODAY)
        self.assertFalse(s['recommend_cleaning'])
        self.assertLess(float(s['estimated_soiling_loss_pct']), 5.0)

    def test_vraie_chute_signalee(self):
        self._releves(chute_dernier_mois=True)
        m = analytics.om_metrics(self.inst, today=TODAY)
        septembre = next(p for p in m['monthly_pr'] if p['month'] == '2026-09')
        self.assertAlmostEqual(float(septembre['pr_pct']), 80.0, delta=2.0)
        s = analytics.soiling_assessment(self.inst, today=TODAY)
        # Le dernier mois (1-8 octobre) est nominal ; la chute de septembre
        # reste visible dans la série et dans la baseline.
        self.assertIsNotNone(s['baseline_pr_pct'])

    def test_releves_arretes_et_trente_jours_sans_fausse_derive(self):
        """AMON99 — chaque relevé au prorata de ses jours dans les mois,
        attendu de chaque mois sur ses jours couverts, pente sur les seuls
        mois complets : journaliers sains arrêtés au 15/10, lus le 15/11, et
        relevés de 30 j contigus depuis le 15/01 ⇒ dégradation ∈ [−1 ; 1],
        aucun soiling, aucune reco de nettoyage (et non −33,78 / −92,80)."""
        from apps.monitoring.report import build_om_report_data
        quinze = date(2026, 11, 15)
        arrete = Installation.objects.create(
            company=self.company, reference='CHT-AMON99-J',
            client=self.inst.client, puissance_installee_kwc=Decimal('7.00'))
        trente = Installation.objects.create(
            company=self.company, reference='CHT-AMON99-30',
            client=self.inst.client, puissance_installee_kwc=Decimal('7.00'),
            date_mise_en_service=date(2026, 1, 15))
        for inst in (arrete, trente):
            MonitoringConfig.objects.create(
                company=self.company, installation=inst,
                expected_annual_kwh=Decimal('12000'))
        jour = date(2025, 11, 15)
        while jour <= date(2026, 10, 15):
            ProductionReading.objects.create(
                company=self.company, installation=arrete, date=jour,
                energy_kwh=services.attendu_entre(
                    Decimal('12000'), jour, jour).quantize(Decimal('0.01')),
                period_days=1)
            jour += timedelta(days=1)
        jour = date(2026, 1, 15)
        while jour + timedelta(days=30) <= quinze + timedelta(days=1):
            ProductionReading.objects.create(
                company=self.company, installation=trente, date=jour,
                energy_kwh=services.attendu_entre(
                    Decimal('12000'), jour, jour + timedelta(days=29),
                ).quantize(Decimal('0.01')),
                period_days=30)
            jour += timedelta(days=30)
        for inst in (arrete, trente):
            data = build_om_report_data(inst, period='monthly', today=quinze)
            derive = float(data['degradation_pct_per_year'])
            self.assertGreaterEqual(derive, -1.0, inst.reference)
            self.assertLessEqual(derive, 1.0, inst.reference)
            self.assertFalse(data['soiling_suspected'], inst.reference)
            self.assertNotIn('Nettoyage des panneaux recommandé.',
                             data['recommendations'], inst.reference)

    def test_historique_egal_pr_mensuel_analytique(self):
        """AMON100 — l'historique mensuel (JSON et CSV) sert les MÊMES PR
        mensuels que l'analytique O&M (prorata, attendu au profil mensuel),
        jamais un attendu à plat ``annuel × jours / 365``."""
        import calendar
        import csv
        import io

        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        today = timezone.localdate()
        for i in range(365):
            jour = today - timedelta(days=364 - i)
            ProductionReading.objects.create(
                company=self.company, installation=self.inst, date=jour,
                energy_kwh=services.attendu_entre(
                    Decimal('12000'), jour, jour).quantize(Decimal('0.01')),
                period_days=1)
        user = get_user_model().objects.create_user(
            username='amon100_admin', password='x', role_legacy='admin',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        config = MonitoringConfig.objects.get(installation=self.inst)
        url = f'/api/django/monitoring/configs/{config.pk}/history/?months=12'
        reponse = api.get(url)
        self.assertEqual(reponse.status_code, 200)
        rows = reponse.data['data']
        self.assertEqual(set(rows[0]), {
            'month', 'actual_kwh', 'expected_kwh', 'ratio_pct'})
        pr = {m['month']: m['pr_pct'] for m in analytics.om_metrics(
            self.inst, today=today)['monthly_pr']}
        self.assertEqual([r['month'] for r in rows], list(pr))
        for row in rows:
            self.assertAlmostEqual(
                row['ratio_pct'], float(pr[row['month']]), delta=0.1,
                msg=row['month'])
        # Au profil : l'attendu par jour des mois pleins varie (hiver ≠ été).
        par_jour = [
            r['expected_kwh'] / calendar.monthrange(
                *(int(x) for x in r['month'].split('-')))[1]
            for r in rows[1:-1]]
        self.assertGreater(max(par_jour) / min(par_jour), 1.5)
        contenu = b''.join(api.get(url + '&export=csv').streaming_content)
        lignes = list(csv.DictReader(io.StringIO(contenu.decode())))
        self.assertEqual([float(ligne['ratio_pct']) for ligne in lignes],
                         [r['ratio_pct'] for r in rows])
