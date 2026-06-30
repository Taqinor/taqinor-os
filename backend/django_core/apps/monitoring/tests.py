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

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket

from apps.monitoring import providers, services
from apps.monitoring.models import (
    MonitoringConfig, MonitoringSettings, ProductionReading,
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
