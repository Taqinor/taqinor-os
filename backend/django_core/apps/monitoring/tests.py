"""
Tests du module Monitoring (N50/N51/N52).

Couvre :
  * isolation par société (configs, relevés, réglages) ;
  * saisie manuelle d'un relevé (source forcée 'manual' côté serveur) ;
  * synchro sans fournisseur configuré = no-op sûr (0 relevé importé) ;
  * fournisseur swappable : un fournisseur de test injecté importe des relevés,
    idempotent via external_id ;
  * sous-performance N52 : drapeau idempotent + auto-ticket SAV unique, sous
    bascule société (OFF par défaut → rien ne change).

Run :
    python manage.py test apps.monitoring -v 2
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket

from apps.monitoring import providers, services, tasks
from apps.monitoring.models import (
    CleaningEvent, MonitoringConfig, MonitoringSettings, ProductionReading,
    UnderperformanceFlag,
)

User = get_user_model()


def make_company(slug='mon-co', nom='Mon Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return [x['id'] for x in rows]


def make_installation(company, ref='CHT-M-1', kwc='5.00'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'c-{company.id}-{ref}@example.invalid')
    inst = Installation.objects.create(
        company=company, reference=ref, client=client,
        puissance_installee_kwc=Decimal(kwc))
    return inst, client


class TestManualEntry(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='mon_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.company)

    def test_manual_reading_forces_source_and_company(self):
        r = self.api.post('/api/django/monitoring/readings/', {
            'installation': self.inst.id, 'date': '2026-06-01',
            'energy_kwh': '120.5', 'period_days': 30,
            'source': 'auto',  # doit être ignoré → forcé 'manual'
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['source'], 'manual')
        obj = ProductionReading.objects.get(id=r.data['id'])
        self.assertEqual(obj.company_id, self.company.id)
        self.assertEqual(obj.created_by_id, self.user.id)
        self.assertEqual(obj.external_id, '')

    def test_negative_energy_rejected(self):
        r = self.api.post('/api/django/monitoring/readings/', {
            'installation': self.inst.id, 'date': '2026-06-01',
            'energy_kwh': '-5',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_readings_filtered_by_installation(self):
        inst2, _ = make_installation(self.company, ref='CHT-M-2')
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1), energy_kwh=Decimal('10'))
        ProductionReading.objects.create(
            company=self.company, installation=inst2,
            date=date(2026, 6, 1), energy_kwh=Decimal('20'))
        r = self.api.get(
            f'/api/django/monitoring/readings/?installation={self.inst.id}')
        self.assertEqual(r.status_code, 200)
        ids = ids_of(r)
        self.assertEqual(len(ids), 1)


class TestTenantIsolation(TestCase):
    def setUp(self):
        self.c1 = make_company('iso-1', 'Iso 1')
        self.c2 = make_company('iso-2', 'Iso 2')
        self.u1 = User.objects.create_user(
            username='iso_u1', password='x', role_legacy='admin', company=self.c1)
        self.u2 = User.objects.create_user(
            username='iso_u2', password='x', role_legacy='admin', company=self.c2)
        self.inst1, _ = make_installation(self.c1, ref='CHT-ISO-1')
        self.inst2, _ = make_installation(self.c2, ref='CHT-ISO-2')

    def test_reading_isolation(self):
        ProductionReading.objects.create(
            company=self.c1, installation=self.inst1,
            date=date(2026, 6, 1), energy_kwh=Decimal('10'))
        ProductionReading.objects.create(
            company=self.c2, installation=self.inst2,
            date=date(2026, 6, 1), energy_kwh=Decimal('20'))
        r = auth(self.u1).get('/api/django/monitoring/readings/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(ids_of(r)), 1)

    def test_cannot_read_other_company_via_config(self):
        MonitoringConfig.objects.create(
            company=self.c2, installation=self.inst2)
        r = auth(self.u1).get('/api/django/monitoring/configs/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(ids_of(r)), 0)

    def test_settings_singleton_per_company(self):
        r1 = auth(self.u1).get('/api/django/monitoring/settings/')
        r2 = auth(self.u2).get('/api/django/monitoring/settings/')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        # Défaut : auto-ticket OFF (comportement d'aujourd'hui).
        self.assertFalse(r1.data['auto_create_ticket'])
        self.assertEqual(MonitoringSettings.objects.count(), 2)


class TestSyncNoProvider(TestCase):
    def setUp(self):
        self.company = make_company('sync-co', 'Sync Co')
        self.user = User.objects.create_user(
            username='sync_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.company, ref='CHT-SYNC-1')

    def test_sync_no_provider_is_noop(self):
        config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst)  # provider='noop'
        r = self.api.post(
            f'/api/django/monitoring/configs/{config.id}/sync-now/', {},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['imported'], 0)
        self.assertEqual(ProductionReading.objects.count(), 0)

    def test_fusionsolar_without_credentials_is_noop(self):
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            provider='fusionsolar', enabled=True, credentials={})
        imported, _ = services.sync_system(self.inst, user=self.user)
        self.assertEqual(imported, 0)


class TestSwappableProvider(TestCase):
    """Un fournisseur de test injecté dans le registre importe des relevés,
    de façon idempotente via external_id (interface swappable)."""

    def setUp(self):
        self.company = make_company('prov-co', 'Prov Co')
        self.user = User.objects.create_user(
            username='prov_admin', password='x', role_legacy='admin',
            company=self.company)
        self.inst, _ = make_installation(self.company, ref='CHT-PROV-1')

        class FakeProvider(providers.MonitoringProvider):
            key = 'fake'
            label = 'Fake'

            def fetch_recent(self, system, config):
                return [
                    {'date': '2026-06-01', 'energy_kwh': 30,
                     'period_days': 1, 'external_id': 'd-1'},
                    {'date': '2026-06-02', 'energy_kwh': 28,
                     'period_days': 1, 'external_id': 'd-2'},
                ]

        self._orig = dict(providers._REGISTRY)
        providers.register_provider(FakeProvider)
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            provider='fake', enabled=True, credentials={'x': 1})

    def tearDown(self):
        providers._REGISTRY.clear()
        providers._REGISTRY.update(self._orig)

    def test_sync_imports_then_idempotent(self):
        imported, _ = services.sync_system(self.inst, user=self.user)
        self.assertEqual(imported, 2)
        self.assertEqual(
            ProductionReading.objects.filter(source='auto').count(), 2)
        # Deuxième passe : aucun doublon (idempotent via external_id).
        imported2, _ = services.sync_system(self.inst, user=self.user)
        self.assertEqual(imported2, 0)
        self.assertEqual(
            ProductionReading.objects.filter(source='auto').count(), 2)


class TestUnderperformance(TestCase):
    def setUp(self):
        self.company = make_company('perf-co', 'Perf Co')
        self.user = User.objects.create_user(
            username='perf_admin', password='x', role_legacy='admin',
            company=self.company)
        # Attendu = 5 kWc × 1500 = 7500 kWh/an.
        self.inst, _ = make_installation(self.company, ref='CHT-PERF-1', kwc='5.00')
        self.today = date(2026, 6, 1)

    def _add_reading(self, kwh):
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=self.today - timedelta(days=10), energy_kwh=Decimal(str(kwh)),
            period_days=365)

    def test_no_data_is_noop(self):
        res = services.evaluate_underperformance(self.inst, today=self.today)
        self.assertFalse(res['evaluated'])
        self.assertEqual(UnderperformanceFlag.objects.count(), 0)

    def test_underperf_flag_without_auto_ticket(self):
        # Bascule OFF (défaut) : flag posé, AUCUN ticket créé.
        self._add_reading(1000)  # très en dessous de 7500
        res = services.evaluate_underperformance(
            self.inst, user=self.user, today=self.today)
        self.assertTrue(res['evaluated'])
        self.assertTrue(res['underperforming'])
        self.assertIsNotNone(res['flag'])
        self.assertIsNone(res['ticket'])
        self.assertEqual(Ticket.objects.count(), 0)

    def test_underperf_auto_ticket_idempotent(self):
        s = MonitoringSettings.get(self.company)
        s.auto_create_ticket = True
        s.save()
        self._add_reading(1000)
        res1 = services.evaluate_underperformance(
            self.inst, user=self.user, today=self.today)
        self.assertIsNotNone(res1['ticket'])
        self.assertEqual(Ticket.objects.count(), 1)
        # Ré-évaluer : même drapeau ouvert → AUCUN second ticket.
        res2 = services.evaluate_underperformance(
            self.inst, user=self.user, today=self.today)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(res2['ticket'].id, res1['ticket'].id)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 1)

    def test_good_production_closes_open_flag(self):
        # Sous-performe d'abord.
        self._add_reading(1000)
        services.evaluate_underperformance(
            self.inst, user=self.user, today=self.today)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 1)
        # Production correcte ensuite → drapeau fermé.
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=self.today, energy_kwh=Decimal('7000'), period_days=365)
        res = services.evaluate_underperformance(
            self.inst, user=self.user, today=self.today)
        self.assertFalse(res['underperforming'])
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 0)

    def test_reevaluation_does_not_duplicate_open_flag(self):
        """ERR47 — ré-évaluer un système déjà sous-performant ne crée jamais un
        second drapeau ouvert (idempotence préservée par get_or_create atomique
        + contrainte partielle unique), sans lever d'IntegrityError."""
        self._add_reading(1000)
        res1 = services.evaluate_underperformance(
            self.inst, user=self.user, today=self.today)
        self.assertTrue(res1['underperforming'])
        flag_id = res1['flag'].id
        # Deuxième passe : même drapeau ouvert réutilisé, pas de doublon.
        res2 = services.evaluate_underperformance(
            self.inst, user=self.user, today=self.today)
        self.assertEqual(res2['flag'].id, flag_id)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(
                installation=self.inst, is_open=True).count(), 1)

    def test_preexisting_open_flag_is_reused_not_duplicated(self):
        """ERR47 — un drapeau ouvert pré-existant (ex. posé par une évaluation
        concurrente) est verrouillé et réutilisé, pas redoublé."""
        existing = UnderperformanceFlag.objects.create(
            company=self.company, installation=self.inst,
            ratio_pct=Decimal('10.00'))
        self._add_reading(1000)
        res = services.evaluate_underperformance(
            self.inst, user=self.user, today=self.today)
        self.assertEqual(res['flag'].id, existing.id)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(
                installation=self.inst, is_open=True).count(), 1)


class TestOmMetrics(TestCase):
    """FG279 — analytique O&M (PR, disponibilité, soiling, dégradation)."""

    def setUp(self):
        self.company = make_company('om-co', 'OM Co')
        self.user = User.objects.create_user(
            username='om_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.company, ref='CHT-OM-1', kwc='10.00')
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        self.today = date(2026, 6, 30)

    def _seed_monthly(self, kwh_by_month):
        for offset, kwh in enumerate(kwh_by_month):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=date(2026, 1, 15) + timedelta(days=30 * offset),
                period_days=30, energy_kwh=Decimal(str(kwh)))

    def test_pr_and_availability_computed(self):
        self._seed_monthly([1000, 1000, 1000])
        from apps.monitoring.analytics import om_metrics
        m = om_metrics(self.inst, window_days=365, today=self.today)
        self.assertIsNotNone(m['pr_pct'])
        self.assertIsNotNone(m['availability_pct'])
        self.assertEqual(m['production_kwh'], Decimal('3000.00'))

    def test_declining_pr_flags_soiling(self):
        # PR mensuel qui décroît nettement → soiling suspecté.
        self._seed_monthly([1000, 900, 800, 700, 600, 500])
        from apps.monitoring.analytics import om_metrics
        m = om_metrics(self.inst, window_days=365, today=self.today)
        self.assertTrue(m['soiling_suspected'])
        self.assertIsNotNone(m['degradation_pct_per_year'])

    def test_no_data_graceful(self):
        from apps.monitoring.analytics import om_metrics
        m = om_metrics(self.inst, window_days=365, today=self.today)
        self.assertEqual(m['production_kwh'], Decimal('0.00'))
        self.assertEqual(m['monthly_pr'], [])

    def test_om_metrics_endpoint(self):
        self._seed_monthly([1000, 1000])
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.id}/om-metrics/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('pr_pct', r.data)
        self.assertEqual(r.data['installation'], self.inst.id)


class TestFleetOverview(TestCase):
    """FG281 — tableau de bord parc/flotte multi-systèmes."""

    def setUp(self):
        self.company = make_company('fleet-co', 'Fleet Co')
        self.other = make_company('fleet-other', 'Fleet Other')
        self.user = User.objects.create_user(
            username='fleet_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.today = date(2026, 6, 30)
        self.inst1, _ = make_installation(self.company, ref='F-1', kwc='5.00')
        self.inst2, _ = make_installation(self.company, ref='F-2', kwc='10.00')
        for inst, exp in ((self.inst1, '6000'), (self.inst2, '12000')):
            MonitoringConfig.objects.create(
                company=self.company, installation=inst,
                expected_annual_kwh=Decimal(exp))
            ProductionReading.objects.create(
                company=self.company, installation=inst,
                date=date(2026, 6, 1), period_days=365,
                energy_kwh=Decimal('5000'))

    def test_fleet_totals(self):
        from apps.monitoring.selectors import fleet_overview
        ov = fleet_overview(self.company, today=self.today)
        self.assertEqual(ov['systems_active'], 2)
        self.assertEqual(ov['total_kwc'], Decimal('15.00'))
        self.assertEqual(ov['total_production_kwh'], Decimal('10000.00'))
        self.assertIsNotNone(ov['fleet_pr_pct'])

    def test_inactive_system_excluded(self):
        self.inst2.parc_actif = False
        self.inst2.save(update_fields=['parc_actif'])
        from apps.monitoring.selectors import fleet_overview
        ov = fleet_overview(self.company, today=self.today)
        self.assertEqual(ov['systems_active'], 1)

    def test_fleet_endpoint_isolation(self):
        # L'autre société ne voit pas les systèmes de la première.
        other_user = User.objects.create_user(
            username='fleet_other_admin', password='x', role_legacy='admin',
            company=self.other)
        r = auth(other_user).get('/api/django/monitoring/configs/fleet/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['systems_active'], 0)

    def test_fleet_endpoint_ok(self):
        r = self.api.get('/api/django/monitoring/configs/fleet/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['systems_active'], 2)


class TestProductionWarranty(TestCase):
    """FG282 — garantie de production + compensation de manque."""

    def setUp(self):
        self.company = make_company('war-co', 'War Co')
        self.user = User.objects.create_user(
            username='war_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.company, ref='W-1', kwc='10.00')

    def _make_warranty(self, **kw):
        from apps.monitoring.models import ProductionWarranty
        defaults = dict(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0.50'),
            start_year=2025,
            compensation_mad_per_kwh=Decimal('1.4000'))
        defaults.update(kw)
        return ProductionWarranty.objects.create(**defaults)

    def test_degraded_guarantee_year2(self):
        w = self._make_warranty()
        # Année 2 (2026) : 12000 × (1 - 0.005) = 11940.
        g = w.guaranteed_kwh_for_year(2026)
        self.assertEqual(g.quantize(Decimal('0.01')), Decimal('11940.00'))

    def test_shortfall_and_compensation(self):
        self._make_warranty()
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1), period_days=365, energy_kwh=Decimal('10000'))
        from apps.monitoring.services import production_warranty_status
        st = production_warranty_status(self.inst, year=2026)
        self.assertTrue(st['has_warranty'])
        # Manque = 11940 - 10000 = 1940 ; compensation = 1940 × 1.4 = 2716.
        self.assertEqual(st['shortfall_kwh'], Decimal('1940.00'))
        self.assertEqual(st['compensation_mad'], Decimal('2716.00'))

    def test_no_shortfall_when_overproducing(self):
        self._make_warranty()
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1), period_days=365, energy_kwh=Decimal('13000'))
        from apps.monitoring.services import production_warranty_status
        st = production_warranty_status(self.inst, year=2026)
        self.assertEqual(st['shortfall_kwh'], Decimal('0.00'))
        self.assertEqual(st['compensation_mad'], Decimal('0.00'))

    def test_no_warranty_graceful(self):
        from apps.monitoring.services import production_warranty_status
        st = production_warranty_status(self.inst, year=2026)
        self.assertFalse(st['has_warranty'])

    def test_warranty_viewset_forces_company(self):
        r = self.api.post('/api/django/monitoring/warranties/', {
            'installation': self.inst.id,
            'guaranteed_year1_kwh': '12000',
            'degradation_pct_per_year': '0.5',
            'start_year': 2025,
            'compensation_mad_per_kwh': '1.4',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        from apps.monitoring.models import ProductionWarranty
        w = ProductionWarranty.objects.get(id=r.data['id'])
        self.assertEqual(w.company_id, self.company.id)

    def test_status_endpoint(self):
        w = self._make_warranty()
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1), period_days=365, energy_kwh=Decimal('10000'))
        r = self.api.get(
            f'/api/django/monitoring/warranties/{w.id}/status/?year=2026')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['has_warranty'])


class TestSoiling(TestCase):
    """FG283 — détection de pertes par salissure + reco de nettoyage."""

    def setUp(self):
        self.company = make_company('soil-co', 'Soil Co')
        self.user = User.objects.create_user(
            username='soil_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.company, ref='S-1', kwc='10.00')
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        self.today = date(2026, 6, 30)

    def _seed(self, kwh_by_month):
        for offset, kwh in enumerate(kwh_by_month):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=date(2026, 1, 15) + timedelta(days=30 * offset),
                period_days=30, energy_kwh=Decimal(str(kwh)))

    def test_pr_drop_recommends_cleaning(self):
        # PR descend de 1000 → 700 (≈ -25 pts de PR), chute > seuil.
        self._seed([1000, 950, 850, 700])
        from apps.monitoring.analytics import soiling_assessment
        a = soiling_assessment(self.inst, today=self.today)
        self.assertIsNotNone(a['estimated_soiling_loss_pct'])
        self.assertTrue(a['recommend_cleaning'])

    def test_recent_cleaning_no_days_alert(self):
        self._seed([1000, 1000, 1000])
        CleaningEvent.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1))
        from apps.monitoring.analytics import soiling_assessment
        a = soiling_assessment(self.inst, today=self.today)
        self.assertEqual(a['days_since_cleaning'], 29)
        self.assertFalse(a['recommend_cleaning'])

    def test_cleaning_viewset_forces_company_and_user(self):
        r = self.api.post('/api/django/monitoring/cleanings/', {
            'installation': self.inst.id, 'date': '2026-06-15',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        ev = CleaningEvent.objects.get(id=r.data['id'])
        self.assertEqual(ev.company_id, self.company.id)
        self.assertEqual(ev.created_by_id, self.user.id)

    def test_soiling_endpoint(self):
        self._seed([1000, 700])
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.id}/soiling/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('recommend_cleaning', r.data)


class TestWarrantyCurveOverlay(TestCase):
    """FG284 — production mesurée vs courbe garantie → dérive → recours."""

    def setUp(self):
        self.company = make_company('curve-co', 'Curve Co')
        self.user = User.objects.create_user(
            username='curve_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.company, ref='C-1', kwc='10.00')
        from apps.monitoring.models import ProductionWarranty
        self.warranty = ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0.50'),
            start_year=2025, tolerance_pct=Decimal('5'))
        self.today = date(2026, 6, 30)

    def test_anomalous_drift_flags_recourse(self):
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1), period_days=365, energy_kwh=Decimal('8000'))
        from apps.monitoring.services import warranty_curve_overlay
        ov = warranty_curve_overlay(self.inst, today=self.today)
        self.assertTrue(ov['has_warranty'])
        self.assertTrue(ov['manufacturer_recourse'])
        p2026 = next(p for p in ov['points'] if p['year'] == 2026)
        self.assertTrue(p2026['anomalous'])

    def test_on_curve_no_recourse(self):
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1), period_days=365, energy_kwh=Decimal('11900'))
        from apps.monitoring.services import warranty_curve_overlay
        ov = warranty_curve_overlay(self.inst, today=self.today)
        self.assertFalse(ov['manufacturer_recourse'])

    def test_no_data_year_not_anomalous(self):
        from apps.monitoring.services import warranty_curve_overlay
        ov = warranty_curve_overlay(self.inst, today=self.today)
        for p in ov['points']:
            self.assertFalse(p['anomalous'])
            self.assertIsNone(p['actual_kwh'])

    def test_curve_endpoint(self):
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1), period_days=365, energy_kwh=Decimal('8000'))
        r = self.api.get(
            f'/api/django/monitoring/warranties/{self.warranty.id}/curve/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['manufacturer_recourse'])


class TestAdditionalProviders(TestCase):
    """FG285 — adaptateurs SolarEdge/Sungrow/Solis (gated, no-op par défaut)."""

    def setUp(self):
        self.company = make_company('adp-co', 'Adp Co')
        self.user = User.objects.create_user(
            username='adp_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.company, ref='ADP-1')

    def test_new_providers_registered(self):
        keys = dict(providers.available_providers())
        for key in ('solaredge', 'sungrow', 'solis'):
            self.assertIn(key, keys)

    def test_provider_noop_without_credentials(self):
        for key in ('solaredge', 'sungrow', 'solis'):
            cfg = MonitoringConfig.objects.create(
                company=self.company, installation=self.inst,
                provider=key, enabled=True, credentials={})
            prov = providers.get_provider(key)
            self.assertEqual(prov.fetch_recent(self.inst, cfg), [])
            cfg.delete()

    def test_provider_noop_when_disabled_even_with_credentials(self):
        cfg = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            provider='solaredge', enabled=False,
            credentials={'api_key': 'x', 'site_id': '1'})
        prov = providers.get_provider('solaredge')
        self.assertEqual(prov.fetch_recent(self.inst, cfg), [])

    def test_providers_endpoint_lists_new(self):
        r = self.api.get('/api/django/monitoring/configs/providers/')
        self.assertEqual(r.status_code, 200, r.data)
        keys = [p['key'] for p in r.data]
        self.assertIn('solaredge', keys)
        self.assertIn('solis', keys)


class TestCo2Reporting(TestCase):
    """FG286 — CO₂ évité par système & cumulé sur le parc."""

    def setUp(self):
        self.company = make_company('co2-co', 'CO2 Co')
        self.user = User.objects.create_user(
            username='co2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst1, _ = make_installation(self.company, ref='CO2-1', kwc='5')
        self.inst2, _ = make_installation(self.company, ref='CO2-2', kwc='10')
        for inst in (self.inst1, self.inst2):
            self.config = MonitoringConfig.objects.create(
                company=self.company, installation=inst)
            ProductionReading.objects.create(
                company=self.company, installation=inst,
                date=date(2026, 6, 1), period_days=30,
                energy_kwh=Decimal('1000'))

    def test_co2_per_system(self):
        from apps.monitoring.selectors import co2_for_installation
        r = co2_for_installation(self.inst1)
        # 1000 kWh × 0.81 = 810 kg.
        self.assertEqual(r['co2_kg'], Decimal('810.00'))

    def test_co2_fleet_cumulative(self):
        from apps.monitoring.selectors import co2_fleet
        r = co2_fleet(self.company)
        # 2000 kWh × 0.81 = 1620 kg.
        self.assertEqual(r['total_co2_kg'], Decimal('1620.00'))
        self.assertEqual(len(r['systems']), 2)

    def test_co2_fleet_endpoint(self):
        r = self.api.get('/api/django/monitoring/configs/co2-fleet/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['systems']), 2)


class TestClientEnvironmentalPortal(TestCase):
    """FG288 — tableau de bord environnemental client (portail)."""

    def setUp(self):
        self.company = make_company('portal-co', 'Portal Co')
        self.user = User.objects.create_user(
            username='portal_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        # Deux systèmes du MÊME client.
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='Ent',
            email='portal-cli@example.invalid')
        self.inst1 = Installation.objects.create(
            company=self.company, reference='P-1', client=self.client_obj,
            puissance_installee_kwc=Decimal('5'))
        self.inst2 = Installation.objects.create(
            company=self.company, reference='P-2', client=self.client_obj,
            puissance_installee_kwc=Decimal('5'))
        for inst in (self.inst1, self.inst2):
            ProductionReading.objects.create(
                company=self.company, installation=inst,
                date=date(2026, 6, 1), period_days=30,
                energy_kwh=Decimal('1000'))

    def test_cumulative_dashboard(self):
        from apps.monitoring.selectors import client_environmental_dashboard
        d = client_environmental_dashboard(self.company, self.client_obj.id)
        self.assertEqual(d['total_production_kwh'], Decimal('2000.00'))
        # 2000 × 1.4 = 2800 MAD ; 2000 × 0.81 = 1620 kg CO₂.
        self.assertEqual(d['economies_mad'], Decimal('2800.00'))
        self.assertEqual(d['co2_kg'], Decimal('1620.00'))
        self.assertEqual(d['systems_count'], 2)

    def test_portal_endpoint(self):
        r = self.api.get(
            f'/api/django/monitoring/configs/client-portal/?client={self.client_obj.id}')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['systems_count'], 2)

    def test_portal_requires_client(self):
        r = self.api.get('/api/django/monitoring/configs/client-portal/')
        self.assertEqual(r.status_code, 400, r.data)


class TestOmReport(TestCase):
    """FG289 — rapport O&M périodique automatisé (données + email)."""

    def setUp(self):
        self.company = make_company('rep-co', 'Rep Co')
        self.user = User.objects.create_user(
            username='rep_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='Rep',
            email='rep-cli@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='R-1', client=self.client_obj,
            puissance_installee_kwc=Decimal('10'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        self.today = date(2026, 6, 30)
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 10), period_days=30, energy_kwh=Decimal('900'))

    def test_report_data(self):
        from apps.monitoring.report import build_om_report_data
        d = build_om_report_data(self.inst, period='monthly', today=self.today)
        self.assertEqual(d['period_kwh'], Decimal('900.00'))
        self.assertIn('recommendations', d)
        self.assertTrue(len(d['recommendations']) >= 1)

    def test_report_quarterly_window(self):
        from apps.monitoring.report import build_om_report_data
        d = build_om_report_data(
            self.inst, period='quarterly', today=self.today)
        self.assertEqual(d['period_days'], 91)

    def test_email_no_recipient_is_noop(self):
        from apps.monitoring.report import email_om_report
        # Client sans email → aucun destinataire → no-op (False).
        # (Installation exige un client ; le cas « sans destinataire » réel est
        # un client dont l'email est vide, pas une installation sans client.)
        client_sans_email = Client.objects.create(
            company=self.company, nom='SansMail', prenom='X', email='')
        inst2 = Installation.objects.create(
            company=self.company, reference='R-2', client=client_sans_email,
            puissance_installee_kwc=Decimal('5'))
        self.assertFalse(email_om_report(inst2, today=self.today))

    def test_email_sends_with_client_email(self):
        from django.core import mail
        from apps.monitoring.report import email_om_report
        ok = email_om_report(self.inst, period='monthly', today=self.today)
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('rep-cli@example.invalid', mail.outbox[0].to)
        self.assertEqual(len(mail.outbox[0].attachments), 1)

    def test_report_json_endpoint(self):
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.id}/om-report/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('period_kwh', r.data)

    def test_email_sends_via_client_email_and_notifies_internally(self):
        # ARC39 — l'envoi CLIENT (PDF joint) reste un EmailMessage direct
        # (exception documentée), mais une notification INTERNE centrale
        # doit désormais être émise en plus (best-effort, non bloquante).
        from django.core import mail
        from apps.monitoring.report import email_om_report
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            ok = email_om_report(self.inst, period='monthly', today=self.today)
        self.assertTrue(ok)
        # L'email client part toujours (comportement inchangé).
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('rep-cli@example.invalid', mail.outbox[0].to)
        # La notification interne est bien routée par le système central.
        notify_many.assert_called_once()
        args, kwargs = notify_many.call_args
        self.assertEqual(args[1], 'monitoring_rapport')
        self.assertEqual(kwargs.get('company'), self.company)

    def test_notification_interne_persiste_reellement(self):
        # Bout en bout sans mock : preuve que l'EventType est bien enregistré.
        from apps.monitoring.report import email_om_report
        from apps.notifications.models import Notification
        email_om_report(self.inst, period='monthly', today=self.today)
        qs = Notification.objects.filter(
            company=self.company, recipient=self.user,
            event_type='monitoring_rapport')
        self.assertEqual(qs.count(), 1)

    def test_echec_notification_interne_non_bloquant_pour_email_client(self):
        from django.core import mail
        from apps.monitoring.report import email_om_report
        with mock.patch(
                'apps.notifications.services.notify_many',
                side_effect=RuntimeError('boom')):
            ok = email_om_report(self.inst, period='monthly', today=self.today)
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)

    def test_sans_destinataire_aucune_notification_interne(self):
        # No-op AVANT même la génération du PDF : pas de notification non plus.
        client_sans_email = Client.objects.create(
            company=self.company, nom='SansMail2', prenom='X', email='')
        inst2 = Installation.objects.create(
            company=self.company, reference='R-3', client=client_sans_email,
            puissance_installee_kwc=Decimal('5'))
        from apps.monitoring.report import email_om_report
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            ok = email_om_report(inst2, today=self.today)
        self.assertFalse(ok)
        notify_many.assert_not_called()


class TestBalayageQuotidien(TestCase):
    """YSERV3 — job Celery Beat : synchro + évaluation de sous-performance
    pour chaque système supervisé, sans action humaine."""

    def setUp(self):
        self.company = make_company('bal-co', 'Bal Co')
        self.today = date(2026, 6, 1)
        # YSERV3 — self.api : requis par test_email_endpoint (endpoint API
        # email-om-report). Un utilisateur seul n'affecte pas
        # balayage_quotidien() (scopé aux MonitoringConfig existants), donc
        # ne pollue aucun des autres tests de cette classe qui comptent des
        # systèmes traités — contrairement à une config/installation créée
        # ici, que test_email_endpoint crée donc lui-même plutôt qu'en setUp.
        self.user = User.objects.create_user(
            username='bal_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)

        class FakeProvider(providers.MonitoringProvider):
            key = 'fake-bal'
            label = 'Fake Bal'

            def fetch_recent(self, system, config):
                return [
                    {'date': '2026-06-01', 'energy_kwh': 5,
                     'period_days': 1, 'external_id': 'bal-1'},
                ]

        self._orig = dict(providers._REGISTRY)
        providers.register_provider(FakeProvider)

    def tearDown(self):
        providers._REGISTRY.clear()
        providers._REGISTRY.update(self._orig)

    def test_noop_provider_no_crash_no_effect(self):
        """Système sur le fournisseur NoOp (défaut) : aucune synchro, aucun
        crash — comportement actuel inchangé, juste appelé automatiquement."""
        inst, _ = make_installation(self.company, ref='BAL-NOOP', kwc='5.00')
        MonitoringConfig.objects.create(company=self.company, installation=inst)
        result = tasks.balayage_quotidien()
        self.assertEqual(result['systemes'], 1)
        self.assertEqual(result['releves_importes'], 0)
        self.assertEqual(ProductionReading.objects.count(), 0)

    def test_sync_and_evaluate_active_provider(self):
        """Fournisseur actif : la tâche importe le relevé ET évalue la
        sous-performance (aucune synchro auto n'existait avant ce job)."""
        inst, _ = make_installation(self.company, ref='BAL-ACTIVE', kwc='5.00')
        MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            provider='fake-bal', enabled=True, credentials={'x': 1},
            expected_annual_kwh=Decimal('7500'))
        result = tasks.balayage_quotidien()
        self.assertEqual(result['systemes'], 1)
        self.assertEqual(result['releves_importes'], 1)
        self.assertEqual(
            ProductionReading.objects.filter(
                installation=inst, source='auto').count(), 1)

    def test_persistent_underperformance_creates_one_flag_and_ticket(self):
        """Sous-performance persistante → exactement un drapeau + un ticket,
        idempotent au re-run (aucun doublon)."""
        inst, client = make_installation(
            self.company, ref='BAL-PERF', kwc='5.00')
        MonitoringSettings.objects.create(
            company=self.company, underperf_threshold_pct=Decimal('20'),
            auto_create_ticket=True)
        # Relevé manuel très sous l'attendu (5 kWc × 1500 = 7500 kWh/an).
        ProductionReading.objects.create(
            company=self.company, installation=inst,
            date=self.today - timedelta(days=10), period_days=365,
            energy_kwh=Decimal('100'))
        MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            expected_annual_kwh=Decimal('7500'))

        tasks.balayage_quotidien()
        self.assertEqual(
            UnderperformanceFlag.objects.filter(
                installation=inst, is_open=True).count(), 1)
        self.assertEqual(
            Ticket.objects.filter(installation=inst).count(), 1)

        # Re-run : idempotent, pas de second flag/ticket.
        tasks.balayage_quotidien()
        self.assertEqual(
            UnderperformanceFlag.objects.filter(
                installation=inst, is_open=True).count(), 1)
        self.assertEqual(
            Ticket.objects.filter(installation=inst).count(), 1)

    def test_company_isolation(self):
        """Un système d'une autre société n'est jamais mélangé dans le
        décompte d'une société (chaque société traitée séparément)."""
        other = make_company('bal-co-2', 'Bal Co 2')
        inst1, _ = make_installation(self.company, ref='BAL-ISO-1', kwc='5.00')
        inst2, _ = make_installation(other, ref='BAL-ISO-2', kwc='5.00')
        MonitoringConfig.objects.create(company=self.company, installation=inst1)
        MonitoringConfig.objects.create(company=other, installation=inst2)
        result = tasks.balayage_quotidien()
        self.assertEqual(result['systemes'], 2)

    def test_broken_system_does_not_block_others(self):
        """Un système qui échoue (ex. installation orpheline sans client pour
        le ticket) n'empêche jamais les systèmes suivants d'être traités."""
        inst_ok, _ = make_installation(self.company, ref='BAL-OK', kwc='5.00')
        MonitoringConfig.objects.create(company=self.company, installation=inst_ok)

        inst_bad, _ = make_installation(self.company, ref='BAL-BAD', kwc='5.00')
        bad_config = MonitoringConfig.objects.create(
            company=self.company, installation=inst_bad,
            provider='fake-bal', enabled=True, credentials={'x': 1})

        # Force sync_system à lever pour ce système précis pour vérifier
        # l'isolement best-effort (le système suivant reste traité).
        orig_sync = services.sync_system

        def _boom(installation, *, user=None):
            if installation.pk == bad_config.installation_id:
                raise RuntimeError('boom')
            return orig_sync(installation, user=user)

        services.sync_system = _boom
        try:
            result = tasks.balayage_quotidien()
        finally:
            services.sync_system = orig_sync
        self.assertEqual(result['systemes'], 1)

    def test_email_endpoint(self):
        from django.core import mail
        # Système propre à ce test (jamais en setUp — balayage_quotidien()
        # scanne TOUS les MonitoringConfig de la société et les autres tests
        # de cette classe comptent des systèmes traités).
        inst, _client = make_installation(self.company, ref='BAL-EMAIL', kwc='5.00')
        config = MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            expected_annual_kwh=Decimal('7500'))
        r = self.api.post(
            f'/api/django/monitoring/configs/{config.id}/email-om-report/',
            {'period': 'monthly'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['sent'])
        self.assertEqual(len(mail.outbox), 1)


class TestODX16AbonnementMonitoringRelocation(TestCase):
    """ODX16 — ``AbonnementMonitoring`` relogé de compta vers monitoring, table
    physique préservée (``compta_abonnementmonitoring``), nouvelle route
    ``/api/django/monitoring/abonnements-monitoring/`` + ancienne route compta
    conservée, scoping société côté serveur."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='mon_subs_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, self.client_obj = make_installation(
            self.company, ref='CHT-SUBS-1')

    def test_model_lives_in_monitoring_with_preserved_db_table(self):
        from apps.monitoring.models import AbonnementMonitoring
        from apps.compta.models import (
            AbonnementMonitoring as ComptaShimAbonnement)
        # Le shim compta ré-exporte EXACTEMENT la même classe (ODX22 le retirera).
        self.assertIs(AbonnementMonitoring, ComptaShimAbonnement)
        self.assertEqual(
            AbonnementMonitoring._meta.db_table,
            'compta_abonnementmonitoring')
        self.assertEqual(
            AbonnementMonitoring._meta.app_label, 'monitoring')

    def test_new_monitoring_route_creates_scoped_and_computes_echeance(self):
        r = self.api.post(
            '/api/django/monitoring/abonnements-monitoring/', {
                'client_id': self.client_obj.id,
                'installation_id': self.inst.id,
                'periodicite': 'mensuel', 'montant': '199.00',
            }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        from apps.monitoring.models import AbonnementMonitoring
        obj = AbonnementMonitoring.objects.get(id=r.data['id'])
        self.assertEqual(obj.company_id, self.company.id)
        # ``renouveler_abonnement_monitoring`` (perform_create) calcule la 1re
        # échéance à la création.
        self.assertIsNotNone(obj.prochaine_echeance)

    def test_legacy_compta_route_still_serves_same_data(self):
        from apps.monitoring.models import AbonnementMonitoring
        obj = AbonnementMonitoring.objects.create(
            company=self.company, client_id=self.client_obj.id,
            periodicite='mensuel', montant=Decimal('50.00'))
        r = self.api.get('/api/django/compta/abonnements-monitoring/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(obj.id, ids_of(r))
