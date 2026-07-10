"""QJ11 — Optional OTP e-signature confirmation (toggle ESIGN_OTP_ENABLED).

Tests cover both toggle states:
  OFF (default) — byte-identical behaviour to pre-QJ11: no OTP required, no
    extra call, acceptance goes through as before.
  ON (ESIGN_OTP_ENABLED=1) — request_esign_otp stores code in cache; submit
    with wrong/missing code is rejected; correct code is consumed (one-time
    use); re-request regenerates code (idempotent store).

Public endpoint tests:
  proposal_request_otp — POST /proposal/otp/<token>/ is a no-op when OFF,
    returns 200 when ON.
  proposal_accept — accepts without OTP when OFF; requires OTP when ON.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.services import (
    accept_devis,
    request_esign_otp,
    validate_esign_otp,
    _esign_otp_enabled,
    _otp_cache_key,
)

User = get_user_model()


def _make_company(slug='qj11-co', nom='QJ11 Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def _make_client(company, nom='Client QJ11', phone='', email=''):
    return Client.objects.get_or_create(
        company=company, nom=nom,
        defaults={'telephone': phone, 'email': email},
    )[0]


def _make_devis(company, client, ref='DEV-QJ11-0001',
                statut=Devis.Statut.ENVOYE):
    return Devis.objects.create(
        company=company, reference=ref,
        client=client, statut=statut, taux_tva=Decimal('20'))


def _make_share_link(devis):
    return ShareLink.objects.create(company=devis.company, devis=devis)


# ═══════════════════════════════════════════════════════════════════════════
# (a) Toggle OFF (default) — byte-identical to pre-QJ11
# ═══════════════════════════════════════════════════════════════════════════

class TestOtpToggleOff(TestCase):
    """QJ11(a) — ESIGN_OTP_ENABLED unset/0 → OTP is a total no-op."""

    def setUp(self):
        self.company = _make_company('qj11-off', 'QJ11 OFF')
        self.client_obj = _make_client(self.company, 'Client OFF')

    def test_esign_otp_disabled_by_default(self):
        """_esign_otp_enabled returns False when env var is absent."""
        import os
        os.environ.pop('ESIGN_OTP_ENABLED', None)
        self.assertFalse(_esign_otp_enabled())

    def test_request_otp_noop_when_off(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-OF1')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '0'}):
            result = request_esign_otp(link)
        self.assertIsNone(result)  # no error

    def test_validate_otp_noop_when_off(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-OF2')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '0'}):
            # Even with no code provided, validation returns None (pass).
            result = validate_esign_otp(link=link, otp_code='')
        self.assertIsNone(result)

    def test_accept_devis_works_without_otp_when_off(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-OF3')
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '0'}):
            accept_devis(devis=devis, user=None, nom='Client')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')


# ═══════════════════════════════════════════════════════════════════════════
# (b) Toggle ON — OTP required
# ═══════════════════════════════════════════════════════════════════════════

class TestOtpToggleOn(TestCase):
    """QJ11(b) — ESIGN_OTP_ENABLED=1 → OTP is required on accept."""

    def setUp(self):
        self.company = _make_company('qj11-on', 'QJ11 ON')
        self.client_obj = _make_client(
            self.company, 'Client ON',
            phone='+212600000099', email='otp@test.com')

    def test_missing_otp_returns_error(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-ON1')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            err = validate_esign_otp(link=link, otp_code='')
        self.assertIsNotNone(err)
        self.assertIn('code', err.lower())

    def test_wrong_otp_returns_error(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-ON2')
        link = _make_share_link(devis)
        # Store a known code.
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            cache.set(_otp_cache_key(link.token), '123456', 600)
            err = validate_esign_otp(link=link, otp_code='999999')
        self.assertIsNotNone(err)
        self.assertIn('incorrect', err.lower())

    def test_correct_otp_validates_and_is_consumed(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-ON3')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            cache.set(_otp_cache_key(link.token), '654321', 600)
            err = validate_esign_otp(link=link, otp_code='654321')
            self.assertIsNone(err)  # success
            # Code consumed: second attempt with same code fails.
            err2 = validate_esign_otp(link=link, otp_code='654321')
        self.assertIsNotNone(err2)

    def test_expired_otp_returns_error(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-ON4')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            # No code in cache → looks expired.
            err = validate_esign_otp(link=link, otp_code='111111')
        self.assertIsNotNone(err)
        self.assertTrue('expiré' in err.lower() or 'demandé' in err.lower())

    def test_request_otp_stores_code_in_cache(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-ON5')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            request_esign_otp(link)
            stored = cache.get(_otp_cache_key(link.token))
        self.assertIsNotNone(stored)
        self.assertEqual(len(stored), 6)
        self.assertTrue(stored.isdigit())

    def test_request_otp_is_idempotent_overwrite(self):
        """Re-requesting OTP overwrites the previous code (new 10-min window)."""
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-ON6')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            request_esign_otp(link)
            # Re-request: new code (may coincidentally be same, but the call
            # must not raise and cache must be refreshed).
            request_esign_otp(link)
            second = cache.get(_otp_cache_key(link.token))
        self.assertIsNotNone(second)
        self.assertEqual(len(second), 6)


# ═══════════════════════════════════════════════════════════════════════════
# (c) Public endpoint — proposal_request_otp
# ═══════════════════════════════════════════════════════════════════════════

class TestProposalRequestOtpEndpoint(TestCase):
    """QJ11(c) — POST /proposal/otp/<token>/ behaves correctly."""

    def setUp(self):
        self.company = _make_company('qj11-ep', 'QJ11 EP')
        self.client_obj = _make_client(self.company, 'Client EP',
                                       email='ep@test.com')
        self.api = APIClient()

    def test_invalid_token_returns_404(self):
        resp = self.api.post('/api/django/public/proposal/invalid-token/otp/')
        self.assertEqual(resp.status_code, 404)

    def test_noop_when_toggle_off(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-EP1')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '0'}):
            resp = self.api.post(
                f'/api/django/public/proposal/{link.token}/otp/')
        self.assertEqual(resp.status_code, 200)

    def test_returns_200_when_toggle_on(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-EP2')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            resp = self.api.post(
                f'/api/django/public/proposal/{link.token}/otp/')
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════
# (d) Public endpoint — proposal_accept with OTP toggle
# ═══════════════════════════════════════════════════════════════════════════

class TestProposalAcceptOtp(TestCase):
    """QJ11(d) — proposal_accept validates OTP when toggle ON; no-op when OFF."""

    def setUp(self):
        self.company = _make_company('qj11-acc', 'QJ11 ACC')
        self.client_obj = _make_client(self.company, 'Client ACC',
                                       email='acc@test.com')
        self.api = APIClient()

    def test_accept_without_otp_succeeds_when_toggle_off(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-AC1')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '0'}):
            resp = self.api.post(
                f'/api/django/public/proposal/{link.token}/accept/',
                {'nom': 'M. Test', 'consent_esign': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')

    def test_accept_without_otp_fails_when_toggle_on(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-AC2')
        link = _make_share_link(devis)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            resp = self.api.post(
                f'/api/django/public/proposal/{link.token}/accept/',
                {'nom': 'M. Test'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')

    def test_accept_with_correct_otp_succeeds_when_toggle_on(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-AC3')
        link = _make_share_link(devis)
        # Pre-seed OTP in cache.
        cache.set(_otp_cache_key(link.token), '777777', 600)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            resp = self.api.post(
                f'/api/django/public/proposal/{link.token}/accept/',
                {'nom': 'M. Test', 'otp_code': '777777',
                 'consent_esign': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')

    def test_accept_with_wrong_otp_fails_when_toggle_on(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ11-AC4')
        link = _make_share_link(devis)
        cache.set(_otp_cache_key(link.token), '888888', 600)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            resp = self.api.post(
                f'/api/django/public/proposal/{link.token}/accept/',
                {'nom': 'M. Test', 'otp_code': '000000'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')
