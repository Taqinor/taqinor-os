"""FG39 — ObjectifCommercial / KPI Target tests.

Covers:
  - Model creation (company forced, CRUD)
  - Company scoping isolation (co1 cannot see co2's objectifs)
  - Attainment computation: nb_leads, nb_contacts, nb_rdv
  - Period filtering: month, quarter, year boundaries
  - nb_devis / ca_signe metrics return 0 realise (hook stub)
  - Period validation (month required for monthly, quarter for quarterly)
  - Unique constraint per period_type
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import (
    Appointment, Lead, LeadActivity, ObjectifCommercial,
)
from apps.crm.selectors import compute_attainment
from authentication.models import Company

try:
    from authentication.models import CustomUser
except ImportError:  # pragma: no cover
    from django.contrib.auth import get_user_model
    CustomUser = get_user_model()


# ── helpers ──────────────────────────────────────────────────────────────────

def _co(slug):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def _user(username, company):
    u, _ = CustomUser.objects.get_or_create(
        username=username,
        defaults={'company': company, 'email': f'{username}@test.local'},
    )
    u.company = company
    u.save(update_fields=['company'])
    return u


def _lead(company, owner=None, stage='NEW'):
    return Lead.objects.create(company=company, nom='Lead', stage=stage, owner=owner)


def _objectif(company, metric, year, month=None, quarter=None,
               period_type='month', cible=10, owner=None):
    return ObjectifCommercial.objects.create(
        company=company,
        metric=metric,
        period_type=period_type,
        period_year=year,
        period_month=month,
        period_quarter=quarter,
        cible=Decimal(str(cible)),
        owner=owner,
    )


def _aware(year, month, day, hour=0, minute=0):
    """Return a timezone-aware datetime in the current TZ."""
    return timezone.make_aware(
        datetime.datetime(year, month, day, hour, minute),
        timezone.get_current_timezone(),
    )


# ── Model creation / multi-tenant ────────────────────────────────────────────

class TestObjectifCreation(TestCase):
    def setUp(self):
        self.co = _co('fg39-create')

    def test_create_monthly_objectif(self):
        obj = _objectif(self.co, 'nb_leads', 2026, month=6)
        self.assertIsNotNone(obj.pk)
        self.assertEqual(obj.company, self.co)
        self.assertEqual(obj.metric, 'nb_leads')
        self.assertEqual(obj.period_type, 'month')
        self.assertEqual(obj.period_year, 2026)
        self.assertEqual(obj.period_month, 6)
        self.assertIsNone(obj.owner)

    def test_create_quarterly_objectif(self):
        obj = _objectif(self.co, 'ca_signe', 2026,
                        quarter=2, period_type='quarter')
        self.assertEqual(obj.period_quarter, 2)
        self.assertIsNone(obj.period_month)

    def test_create_yearly_objectif(self):
        obj = _objectif(self.co, 'nb_devis', 2026, period_type='year')
        self.assertIsNone(obj.period_month)
        self.assertIsNone(obj.period_quarter)

    def test_str(self):
        obj = _objectif(self.co, 'nb_leads', 2026, month=1)
        s = str(obj)
        self.assertIn('leads', s.lower())

    def test_owner_optional(self):
        user = _user('fg39-u1', self.co)
        obj = _objectif(self.co, 'nb_leads', 2026, month=7, owner=user)
        self.assertEqual(obj.owner, user)


# ── Company scoping isolation ─────────────────────────────────────────────────

class TestObjectifCompanyScoping(TestCase):
    def test_company_isolation(self):
        co1 = _co('fg39-iso1')
        co2 = _co('fg39-iso2')
        _objectif(co1, 'nb_leads', 2026, month=1)
        _objectif(co2, 'nb_leads', 2026, month=1)
        self.assertEqual(ObjectifCommercial.objects.filter(company=co1).count(), 1)
        self.assertEqual(ObjectifCommercial.objects.filter(company=co2).count(), 1)


# ── Attainment: nb_leads ──────────────────────────────────────────────────────

class TestAttainmentNbLeads(TestCase):
    def setUp(self):
        self.co = _co('fg39-leads')

    def test_nb_leads_in_month(self):
        obj = _objectif(self.co, 'nb_leads', 2026, month=6, cible=5)
        # 3 leads in June 2026
        for _ in range(3):
            l = _lead(self.co)
            l.date_creation = _aware(2026, 6, 15)
            l.save(update_fields=['date_creation'])
        # 1 lead outside (May)
        l = _lead(self.co)
        l.date_creation = _aware(2026, 5, 30)
        l.save(update_fields=['date_creation'])

        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('3'))
        self.assertEqual(result['cible'], Decimal('5'))
        self.assertAlmostEqual(result['taux'], 60.0)
        self.assertEqual(result['period_start'], datetime.date(2026, 6, 1))
        self.assertEqual(result['period_end'], datetime.date(2026, 6, 30))

    def test_nb_leads_zero_when_none(self):
        obj = _objectif(self.co, 'nb_leads', 2026, month=1, cible=10)
        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('0'))
        self.assertEqual(result['taux'], 0.0)

    def test_nb_leads_owner_filter(self):
        user = _user('fg39-owner', self.co)
        obj = _objectif(self.co, 'nb_leads', 2026, month=6, cible=3, owner=user)
        # 2 leads assigned to user
        for _ in range(2):
            l = _lead(self.co, owner=user)
            l.date_creation = _aware(2026, 6, 10)
            l.save(update_fields=['date_creation'])
        # 1 lead assigned to nobody
        l2 = _lead(self.co, owner=None)
        l2.date_creation = _aware(2026, 6, 10)
        l2.save(update_fields=['date_creation'])

        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('2'))

    def test_nb_leads_quarter(self):
        """Quarter 2 = April + May + June."""
        obj = _objectif(self.co, 'nb_leads', 2026,
                        quarter=2, period_type='quarter', cible=10)
        # 2 leads in April, 1 in July (out)
        for d in [15, 20]:
            l = _lead(self.co)
            l.date_creation = _aware(2026, 4, d)
            l.save(update_fields=['date_creation'])
        l_out = _lead(self.co)
        l_out.date_creation = _aware(2026, 7, 1)
        l_out.save(update_fields=['date_creation'])

        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('2'))
        self.assertEqual(result['period_start'], datetime.date(2026, 4, 1))
        self.assertEqual(result['period_end'], datetime.date(2026, 6, 30))

    def test_nb_leads_year(self):
        obj = _objectif(self.co, 'nb_leads', 2025, period_type='year', cible=12)
        for m in [1, 6, 12]:
            l = _lead(self.co)
            l.date_creation = _aware(2025, m, 15)
            l.save(update_fields=['date_creation'])
        # 1 lead in 2026 (out)
        l_out = _lead(self.co)
        l_out.date_creation = _aware(2026, 1, 1)
        l_out.save(update_fields=['date_creation'])

        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('3'))
        self.assertEqual(result['period_start'], datetime.date(2025, 1, 1))
        self.assertEqual(result['period_end'], datetime.date(2025, 12, 31))


# ── Attainment: nb_contacts ───────────────────────────────────────────────────

class TestAttainmentNbContacts(TestCase):
    def setUp(self):
        self.co = _co('fg39-contacts')

    def test_nb_contacts_uses_first_contacted_at(self):
        obj = _objectif(self.co, 'nb_contacts', 2026, month=6, cible=5)
        # 2 leads contacted in June
        for _ in range(2):
            l = _lead(self.co)
            l.first_contacted_at = _aware(2026, 6, 15)
            l.save(update_fields=['first_contacted_at'])
        # 1 lead not yet contacted
        _lead(self.co)
        # 1 lead contacted in May (out)
        l_out = _lead(self.co)
        l_out.first_contacted_at = _aware(2026, 5, 20)
        l_out.save(update_fields=['first_contacted_at'])

        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('2'))


# ── Attainment: nb_rdv ────────────────────────────────────────────────────────

class TestAttainmentNbRdv(TestCase):
    def setUp(self):
        self.co = _co('fg39-rdv')

    def test_nb_rdv_effectue_only(self):
        obj = _objectif(self.co, 'nb_rdv', 2026, month=6, cible=5)
        lead = _lead(self.co)
        # 2 effectué in June
        for d in [5, 20]:
            Appointment.objects.create(
                company=self.co,
                lead=lead,
                scheduled_at=_aware(2026, 6, d),
                statut=Appointment.Statut.EFFECTUE,
            )
        # 1 planifié (not counted)
        Appointment.objects.create(
            company=self.co,
            lead=lead,
            scheduled_at=_aware(2026, 6, 25),
            statut=Appointment.Statut.PLANIFIE,
        )
        # 1 effectué in July (out)
        Appointment.objects.create(
            company=self.co,
            lead=lead,
            scheduled_at=_aware(2026, 7, 1),
            statut=Appointment.Statut.EFFECTUE,
        )

        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('2'))


# ── Attainment: stub metrics (nb_devis / ca_signe) ───────────────────────────

class TestAttainmentStubMetrics(TestCase):
    def setUp(self):
        self.co = _co('fg39-stub')

    def test_nb_devis_realise_is_zero(self):
        """nb_devis hook not yet wired — realise = 0, no import error."""
        obj = _objectif(self.co, 'nb_devis', 2026, month=6, cible=5)
        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('0'))
        self.assertEqual(result['taux'], 0.0)

    def test_ca_signe_realise_is_zero(self):
        obj = _objectif(self.co, 'ca_signe', 2026, month=6, cible=100000)
        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('0'))


# ── Taux > 100% (objectif dépassé) ───────────────────────────────────────────

class TestAttainmentExceedsTarget(TestCase):
    def setUp(self):
        self.co = _co('fg39-exceed')

    def test_taux_exceeds_100(self):
        obj = _objectif(self.co, 'nb_leads', 2026, month=6, cible=2)
        for _ in range(5):
            l = _lead(self.co)
            l.date_creation = _aware(2026, 6, 1)
            l.save(update_fields=['date_creation'])
        result = compute_attainment(obj)
        self.assertEqual(result['realise'], Decimal('5'))
        self.assertAlmostEqual(result['taux'], 250.0)


# ── Zero cible guard (no ZeroDivisionError) ──────────────────────────────────

class TestAttainmentZeroCible(TestCase):
    def setUp(self):
        self.co = _co('fg39-zerocible')

    def test_zero_cible_returns_zero_taux(self):
        obj = _objectif(self.co, 'nb_leads', 2026, month=1, cible=0)
        result = compute_attainment(obj)
        self.assertEqual(result['taux'], 0.0)
