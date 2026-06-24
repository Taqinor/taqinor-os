"""QJ1 — Proposal open-tracking on ShareLink.

Tests cover:
  (a) stamping — first GET sets first_viewed_at + view_count=1, second GET
      increments view_count and updates last_viewed_at.
  (b) no buy-price / margin leak in the public JSON payload.
  (c) cross-tenant isolation — a token only stamps its own ShareLink; a request
      with a foreign company's token returns 404.
  (d) serializer fields — nombre_vues / derniere_consultation / deja_consulte
      are correctly exposed on the DevisSerializer.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.serializers import DevisSerializer

User = get_user_model()


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_company(slug='qj1-co', nom='QJ1 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def _make_user(company, username='qj1u'):
    return User.objects.get_or_create(
        username=username,
        defaults={
            'password': 'x',
            'role_legacy': 'responsable',
            'company': company,
        }
    )[0]


def _make_client(company, nom='Client QJ1'):
    return Client.objects.get_or_create(
        company=company, nom=nom,
        defaults={}
    )[0]


def _make_devis(company, client, ref='DEV-QJ1-0001'):
    return Devis.objects.get_or_create(
        company=company, reference=ref,
        defaults={'client': client, 'taux_tva': Decimal('20')},
    )[0]


# ── Fake PDF responses ────────────────────────────────────────────────────────

_PATCH_GEN = patch(
    'apps.ventes.public_views.generate_premium_devis_pdf',
    return_value='devis/1/DEV-QJ1-0001.pdf',
)
_PATCH_DL = patch(
    'apps.ventes.public_views.download_pdf',
    return_value=b'%PDF-1.4 stub',
)


# ═════════════════════════════════════════════════════════════════════════════
# (a) View stamping
# ═════════════════════════════════════════════════════════════════════════════

class TestShareLinkStamping(TestCase):
    """QJ1(a) — first GET sets first_viewed_at + view_count=1; second GET
    increments view_count and updates last_viewed_at."""

    def setUp(self):
        self.company = _make_company('qj1-stamp', 'QJ1 Stamp')
        self.client_obj = _make_client(self.company, 'QJ1 Stamp Client')
        self.devis = _make_devis(self.company, self.client_obj, 'DEV-QJ1-S1')
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    @_PATCH_GEN
    @_PATCH_DL
    def test_first_get_sets_first_viewed_at_and_count_1(self, m_dl, m_gen):
        # Before: no tracking data.
        self.assertIsNone(self.link.first_viewed_at)
        self.assertEqual(self.link.view_count, 0)

        APIClient().get(
            f'/api/django/public/document/{self.link.token}/')

        self.link.refresh_from_db()
        self.assertIsNotNone(self.link.first_viewed_at)
        self.assertEqual(self.link.view_count, 1)
        self.assertIsNotNone(self.link.last_viewed_at)

    @_PATCH_GEN
    @_PATCH_DL
    def test_second_get_increments_count_and_updates_last_viewed(
            self, m_dl, m_gen):
        APIClient().get(
            f'/api/django/public/document/{self.link.token}/')
        self.link.refresh_from_db()
        first_viewed = self.link.first_viewed_at
        self.assertEqual(self.link.view_count, 1)

        APIClient().get(
            f'/api/django/public/document/{self.link.token}/')
        self.link.refresh_from_db()

        self.assertEqual(self.link.view_count, 2)
        # first_viewed_at must NOT change on subsequent views.
        self.assertEqual(self.link.first_viewed_at, first_viewed)
        # last_viewed_at must be >= first_viewed_at (updated each time).
        self.assertGreaterEqual(
            self.link.last_viewed_at, self.link.first_viewed_at)

    @_PATCH_GEN
    @_PATCH_DL
    def test_view_count_tracked_on_proposal_pdf_endpoint(
            self, m_dl, m_gen):
        """proposal_pdf view also stamps."""
        APIClient().get(
            f'/api/django/public/proposal/pdf/{self.link.token}/')
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)

    def test_expired_link_does_not_stamp(self):
        self.link.expires_at = timezone.now() - timedelta(days=1)
        self.link.save(update_fields=['expires_at'])
        APIClient().get(
            f'/api/django/public/document/{self.link.token}/')
        self.link.refresh_from_db()
        # Expired → 404, no stamp.
        self.assertEqual(self.link.view_count, 0)
        self.assertIsNone(self.link.first_viewed_at)


# ═════════════════════════════════════════════════════════════════════════════
# (b) No buy-price / margin leak in public JSON payload
# ═════════════════════════════════════════════════════════════════════════════

class TestPublicPayloadNoPriceAchat(TestCase):
    """QJ1(b) — the public proposal_data JSON payload must never expose
    prix_achat, prix d'achat, or margin-related keys."""

    def setUp(self):
        self.company = _make_company('qj1-leak', 'QJ1 Leak')
        self.client_obj = _make_client(self.company, 'QJ1 Leak Client')
        self.devis = _make_devis(self.company, self.client_obj, 'DEV-QJ1-L1')
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    @patch('apps.ventes.public_views.build_quote_data',
           return_value={
               'ref': 'DEV-QJ1-L1',
               'date': '2026-06-24',
               'client_name': 'Client QJ1',
               'prod_kwh': 5000,
               'prix_achat': 99999,   # must NOT reach the client response
               'marge': 0.3,          # must NOT reach the client response
           })
    def test_prix_achat_not_in_public_response(self, m_bqd):
        resp = APIClient().get(
            f'/api/django/public/proposal/data/{self.link.token}/')
        # The view should succeed (200) and NOT include prix_achat or marge.
        self.assertEqual(resp.status_code, 200)
        import json
        raw = json.dumps(resp.data)
        self.assertNotIn('prix_achat', raw)
        self.assertNotIn('marge', raw)


# ═════════════════════════════════════════════════════════════════════════════
# (c) Cross-tenant isolation
# ═════════════════════════════════════════════════════════════════════════════

class TestCrossTenantIsolation(TestCase):
    """QJ1(c) — a token only stamps its own ShareLink; a different company's
    token cannot be used to access or stamp another company's data."""

    def setUp(self):
        self.co_a = _make_company('qj1-a', 'QJ1 A')
        self.co_b = _make_company('qj1-b', 'QJ1 B')
        cli_a = _make_client(self.co_a, 'ClientA')
        cli_b = _make_client(self.co_b, 'ClientB')
        self.devis_a = _make_devis(self.co_a, cli_a, 'DEV-QJ1-A1')
        self.devis_b = _make_devis(self.co_b, cli_b, 'DEV-QJ1-B1')
        self.link_a = ShareLink.objects.create(
            company=self.co_a, devis=self.devis_a)
        self.link_b = ShareLink.objects.create(
            company=self.co_b, devis=self.devis_b)

    @_PATCH_GEN
    @_PATCH_DL
    def test_accessing_company_a_token_does_not_stamp_company_b(
            self, m_dl, m_gen):
        # GET with company A's token.
        APIClient().get(
            f'/api/django/public/document/{self.link_a.token}/')

        self.link_a.refresh_from_db()
        self.link_b.refresh_from_db()

        # Company A's link stamped.
        self.assertEqual(self.link_a.view_count, 1)
        # Company B's link untouched.
        self.assertEqual(self.link_b.view_count, 0)
        self.assertIsNone(self.link_b.first_viewed_at)

    def test_unknown_token_returns_404_not_another_company_data(self):
        resp = APIClient().get(
            '/api/django/public/document/totally-unknown-token/')
        self.assertEqual(resp.status_code, 404)
        # Must NOT expose any internal details.
        self.assertNotIn('devis', str(resp.data.get('detail', '')))


# ═════════════════════════════════════════════════════════════════════════════
# (d) Serializer fields
# ═════════════════════════════════════════════════════════════════════════════

class TestDevisSerializerTrackingFields(TestCase):
    """QJ1(d) — nombre_vues / derniere_consultation / deja_consulte are
    correctly exposed by DevisSerializer, and never expose prix_achat."""

    def setUp(self):
        self.company = _make_company('qj1-ser', 'QJ1 Ser')
        self.client_obj = _make_client(self.company, 'QJ1 Ser Client')
        self.devis = _make_devis(self.company, self.client_obj, 'DEV-QJ1-SER1')

    def test_no_share_link_returns_defaults(self):
        data = DevisSerializer(self.devis).data
        self.assertIn('nombre_vues', data)
        self.assertIn('derniere_consultation', data)
        self.assertIn('deja_consulte', data)
        self.assertEqual(data['nombre_vues'], 0)
        self.assertIsNone(data['derniere_consultation'])
        self.assertFalse(data['deja_consulte'])

    def test_unviewed_share_link_shows_not_consulted(self):
        ShareLink.objects.create(company=self.company, devis=self.devis)
        data = DevisSerializer(self.devis).data
        self.assertEqual(data['nombre_vues'], 0)
        self.assertFalse(data['deja_consulte'])
        self.assertIsNone(data['derniere_consultation'])

    def test_viewed_share_link_exposes_count_and_date(self):
        now = timezone.now()
        link = ShareLink.objects.create(company=self.company, devis=self.devis)
        link.view_count = 3
        link.first_viewed_at = now - timedelta(days=1)
        link.last_viewed_at = now
        link.save(update_fields=['view_count', 'first_viewed_at', 'last_viewed_at'])

        data = DevisSerializer(self.devis).data
        self.assertEqual(data['nombre_vues'], 3)
        self.assertTrue(data['deja_consulte'])
        self.assertIsNotNone(data['derniere_consultation'])
        # ISO format check (contains the hour portion).
        self.assertIn('T', data['derniere_consultation'])

    def test_prix_achat_not_in_serializer_output(self):
        """prix_achat must never appear in DevisSerializer output."""
        import json
        raw = json.dumps(DevisSerializer(self.devis).data)
        self.assertNotIn('prix_achat', raw)
