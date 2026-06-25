"""QJ17 — from-layout idempotency + pre-flight composition check.

Two acceptance criteria:
  (a) Re-clicking « Générer » returns the EXISTING brouillon (HTTP 200,
      deduplicated=True) — no duplicate devis created.
  (b) An invalid composition (catalogue gap) returns HTTP 422 with clear
      French inline guidance instead of raising a 500 / PDF error.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \\
        python manage.py test apps.ventes.tests.test_qj17_idempotency -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import layout_hash, validate_composition_for_layout

User = get_user_model()

FROM_LAYOUT_URL = '/api/django/ventes/devis/from-layout/'


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def auth_client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def seed_catalogue(company, with_reseau=True, with_hybride=True, with_battery=True):
    def mk(nom, sku, prix):
        return Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
    if with_reseau:
        mk('Onduleur réseau Huawei 5kW', f'ONDR-{company.pk}', 14000)
    if with_hybride:
        mk('Onduleur hybride Deye 5kW', f'ONDH-{company.pk}', 17000)
    if with_battery:
        mk('Batterie Deyness 5 kWh', f'BAT-{company.pk}', 17000)


SAMPLE_LAYOUT = {
    'version': 1,
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
    'zones': [{
        'id': 'z1', 'label': 'Pan Sud',
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'flat',
        'pitchDeg': 15,
        'facingAzimuthDeg': 0,
        'neededPanels': 12,
        'neededAuto': True,
    }],
}

BATTERY_LAYOUT = {
    'version': 1,
    'scenario': 'avec_batterie',
    'result': {'panels': 10, 'kwc': 5.5, 'annualKwh': 9000, 'savings': 7500},
    'zones': [{
        'id': 'z1', 'label': 'Toit',
        'vertices': [[0, 0], [8, 0], [8, 5], [0, 5]],
        'obstacles': [],
        'roofType': 'flat',
        'pitchDeg': 10,
        'facingAzimuthDeg': 0,
        'neededPanels': 10,
        'neededAuto': True,
    }],
}


# ── Unit tests for service helpers ────────────────────────────────────────────

class TestLayoutHash(TestCase):
    """layout_hash produces stable, geometry-sensitive fingerprints."""

    def test_same_layout_same_hash(self):
        h1 = layout_hash(SAMPLE_LAYOUT)
        h2 = layout_hash(SAMPLE_LAYOUT)
        self.assertEqual(h1, h2)
        self.assertTrue(h1)

    def test_different_panels_different_hash(self):
        other = dict(SAMPLE_LAYOUT)
        other['result'] = dict(SAMPLE_LAYOUT['result'])
        other['result']['panels'] = 8
        self.assertNotEqual(layout_hash(SAMPLE_LAYOUT), layout_hash(other))

    def test_different_scenario_different_hash(self):
        bat = dict(SAMPLE_LAYOUT)
        bat['scenario'] = 'avec_batterie'
        self.assertNotEqual(layout_hash(SAMPLE_LAYOUT), layout_hash(bat))

    def test_transient_keys_ignored(self):
        """pin / outline / billKwh / activeAreaId do not affect the hash."""
        enriched = dict(SAMPLE_LAYOUT)
        enriched['pin'] = {'lat': 33.5, 'lng': -7.6}
        enriched['outline'] = [[33.5, -7.6]]
        enriched['billKwh'] = 500
        enriched['activeAreaId'] = 'z1'
        self.assertEqual(layout_hash(SAMPLE_LAYOUT), layout_hash(enriched))

    def test_none_layout_returns_empty(self):
        self.assertEqual(layout_hash(None), '')
        self.assertEqual(layout_hash({}), layout_hash({}))


class TestValidateComposition(TestCase):
    """validate_composition_for_layout returns None on valid, list on error."""

    def setUp(self):
        self.company = make_company('qj17-val')
        self.user = User.objects.create_user(
            username='qj17val', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def test_valid_reseau_returns_none(self):
        errors = validate_composition_for_layout(SAMPLE_LAYOUT, self.company)
        self.assertIsNone(errors)

    def test_valid_battery_returns_none(self):
        errors = validate_composition_for_layout(BATTERY_LAYOUT, self.company)
        self.assertIsNone(errors)

    def test_no_panels_returns_error(self):
        layout = dict(SAMPLE_LAYOUT)
        layout['result'] = {'panels': 0, 'kwc': 0}
        layout['zones'] = []
        errors = validate_composition_for_layout(layout, self.company)
        self.assertIsNotNone(errors)
        self.assertTrue(any('panneau' in e.lower() for e in errors))

    def test_missing_reseau_inverter_returns_error(self):
        Produit.objects.filter(nom__icontains='réseau').delete()
        errors = validate_composition_for_layout(SAMPLE_LAYOUT, self.company)
        self.assertIsNotNone(errors)
        self.assertTrue(any('onduleur' in e.lower() for e in errors))

    def test_missing_battery_returns_error(self):
        Produit.objects.filter(nom__icontains='Batterie').delete()
        errors = validate_composition_for_layout(BATTERY_LAYOUT, self.company)
        self.assertIsNotNone(errors)
        self.assertTrue(any('batterie' in e.lower() for e in errors))

    def test_missing_hybrid_inverter_returns_error(self):
        Produit.objects.filter(nom__icontains='hybride').delete()
        errors = validate_composition_for_layout(BATTERY_LAYOUT, self.company)
        self.assertIsNotNone(errors)
        self.assertTrue(any('hybride' in e.lower() for e in errors))

    def test_priceless_reseau_inverter_counts_as_missing(self):
        Produit.objects.filter(nom__icontains='réseau').update(prix_vente=0)
        errors = validate_composition_for_layout(SAMPLE_LAYOUT, self.company)
        self.assertIsNotNone(errors)

    def test_invalid_layout_type_returns_error(self):
        errors = validate_composition_for_layout('not-a-dict', self.company)
        self.assertIsNotNone(errors)
        self.assertEqual(len(errors), 1)


# ── HTTP endpoint tests ───────────────────────────────────────────────────────

class TestQJ17Idempotency(TestCase):
    """QJ17 (a) — re-click returns existing brouillon (HTTP 200, no duplicate)."""

    def setUp(self):
        self.company = make_company('qj17-idem')
        self.user = User.objects.create_user(
            username='qj17idem', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Idem', prenom='Test',
            email='idem@ex.com', **extra)

    def test_first_call_creates_devis_201(self):
        lead = self._lead()
        resp = self.api.post(FROM_LAYOUT_URL,
                             {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('id', resp.data)
        self.assertFalse(resp.data.get('deduplicated', False))

    def test_second_call_returns_same_devis_200(self):
        """Re-clicking « Générer » must return the existing brouillon."""
        lead = self._lead()
        r1 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                           format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                           format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        # Same devis, no duplicate.
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(r1.data['reference'], r2.data['reference'])
        self.assertTrue(r2.data.get('deduplicated'))
        total = Devis.objects.filter(
            company=self.company, lead=lead).count()
        self.assertEqual(total, 1)

    def test_different_layout_creates_new_devis(self):
        """A geometrically different layout should produce a new devis."""
        lead = self._lead()
        r1 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                           format='json')
        different = dict(SAMPLE_LAYOUT)
        different['result'] = dict(SAMPLE_LAYOUT['result'])
        different['result']['panels'] = 20  # changed geometry
        r2 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': different, 'lead': lead.id},
                           format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r1.data['id'], r2.data['id'])

    def test_different_lead_creates_new_devis(self):
        """Same layout for a different lead is not a duplicate."""
        lead1 = self._lead()
        lead2 = Lead.objects.create(
            company=self.company, nom='Other', prenom='Lead',
            email='other@ex.com')
        r1 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': SAMPLE_LAYOUT, 'lead': lead1.id},
                           format='json')
        r2 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': SAMPLE_LAYOUT, 'lead': lead2.id},
                           format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r1.data['id'], r2.data['id'])

    def test_transient_ui_fields_do_not_prevent_dedup(self):
        """pin/outline/billKwh added by the UI should not break deduplication."""
        lead = self._lead()
        r1 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                           format='json')
        # Same geometry but with transient fields added.
        with_pin = dict(SAMPLE_LAYOUT)
        with_pin['pin'] = {'lat': 33.5, 'lng': -7.6}
        with_pin['billKwh'] = 600
        r2 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': with_pin, 'lead': lead.id},
                           format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r1.data['id'], r2.data['id'])

    def test_company_scoped_no_cross_tenant_dedup(self):
        """Dedup only matches within the same company."""
        other_co = make_company('qj17-other')
        other_user = User.objects.create_user(
            username='qj17other', password='x', role_legacy='responsable',
            company=other_co)
        seed_catalogue(other_co)
        other_api = auth_client(other_user)
        other_lead = Lead.objects.create(
            company=other_co, nom='Cross', prenom='Tenant',
            email='cross@ex.com')

        lead = self._lead()
        r1 = self.api.post(FROM_LAYOUT_URL,
                           {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                           format='json')
        # Other company, same hash — must get a fresh 201.
        r2 = other_api.post(FROM_LAYOUT_URL,
                            {'layout': SAMPLE_LAYOUT, 'lead': other_lead.id},
                            format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r1.data['id'], r2.data['id'])


class TestQJ17CompositionCheck(TestCase):
    """QJ17 (b) — invalid composition → HTTP 422 with clear French message."""

    def setUp(self):
        self.company = make_company('qj17-comp')
        self.user = User.objects.create_user(
            username='qj17comp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Comp', prenom='Test',
            email='comp@ex.com', **extra)

    def test_valid_composition_succeeds(self):
        lead = self._lead()
        resp = self.api.post(FROM_LAYOUT_URL,
                             {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                             format='json')
        self.assertIn(resp.status_code, (200, 201), resp.data)

    def test_empty_catalogue_returns_422_not_500(self):
        """No inverter in catalogue → 422 with a readable French error, not 500."""
        Produit.objects.filter(nom__icontains='réseau').delete()
        lead = self._lead()
        resp = self.api.post(FROM_LAYOUT_URL,
                             {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                             format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
        # Must carry a readable French message.
        self.assertIn('detail', resp.data)
        detail = resp.data['detail']
        self.assertTrue(len(detail) > 10, f'Message too short: {detail!r}')
        # Must NOT create a devis.
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_missing_battery_for_battery_layout_returns_422(self):
        Produit.objects.filter(nom__icontains='Batterie').delete()
        lead = self._lead()
        resp = self.api.post(FROM_LAYOUT_URL,
                             {'layout': BATTERY_LAYOUT, 'lead': lead.id},
                             format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
        detail = resp.data['detail']
        self.assertIn('batterie', detail.lower())

    def test_no_panels_in_layout_returns_422(self):
        layout_no_panels = dict(SAMPLE_LAYOUT)
        layout_no_panels['result'] = {'panels': 0, 'kwc': 0}
        layout_no_panels['zones'] = []
        lead = self._lead()
        resp = self.api.post(FROM_LAYOUT_URL,
                             {'layout': layout_no_panels, 'lead': lead.id},
                             format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertIn('panneau', resp.data['detail'].lower())

    def test_errors_list_present_in_response(self):
        """Response body must also carry an ``errors`` list."""
        Produit.objects.filter(nom__icontains='réseau').delete()
        lead = self._lead()
        resp = self.api.post(FROM_LAYOUT_URL,
                             {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                             format='json')
        self.assertEqual(resp.status_code, 422)
        self.assertIn('errors', resp.data)
        self.assertIsInstance(resp.data['errors'], list)
        self.assertGreater(len(resp.data['errors']), 0)

    def test_priceless_inverter_returns_422(self):
        Produit.objects.filter(nom__icontains='réseau').update(prix_vente=0)
        lead = self._lead()
        resp = self.api.post(FROM_LAYOUT_URL,
                             {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
                             format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
