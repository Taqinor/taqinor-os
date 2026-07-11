"""QX10 — OTP e-signature : canal honnête + verrouillage brute-force.

  * ``_send_otp_whatsapp`` renvoie False (stub) → repli email pour un client
    téléphone-seul ;
  * verrouillage après OTP_MAX_ATTEMPTS échecs, réinitialisé par un nouveau code.
"""
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.services import (
    OTP_MAX_ATTEMPTS, request_esign_otp, validate_esign_otp,
    _send_otp_whatsapp, _otp_cache_key, _otp_attempts_key,
)


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class Qx10OtpHardeningTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx10-co', defaults={'nom': 'QX10 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX10',
            telephone='+212600000047', email='qx10@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QX10-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)
        cache.clear()

    def test_whatsapp_stub_returns_false(self):
        self.assertFalse(_send_otp_whatsapp('+212600000047', '123456', 'REF'))

    def test_phone_only_falls_back_to_email(self):
        # Client SANS email → le stub WhatsApp renvoie False → email tenté.
        self.client_obj.email = ''
        self.client_obj.save(update_fields=['email'])
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            with patch('apps.ventes.services._send_otp_email',
                       return_value=True) as em:
                request_esign_otp(self.link)
        em.assert_called_once()

    def test_lockout_after_max_attempts(self):
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            cache.set(_otp_cache_key(self.link.token), '111111', 600)
            # OTP_MAX_ATTEMPTS mauvais essais.
            for _ in range(OTP_MAX_ATTEMPTS):
                err = validate_esign_otp(link=self.link, otp_code='000000')
                self.assertIsNotNone(err)
            # Le bon code est désormais REFUSÉ (verrouillé).
            err = validate_esign_otp(link=self.link, otp_code='111111')
            self.assertIn('Trop de tentatives', err)

    def test_new_code_resets_lockout(self):
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            cache.set(_otp_attempts_key(self.link.token), OTP_MAX_ATTEMPTS, 600)
            with patch('apps.ventes.services._send_otp_whatsapp',
                       return_value=False), \
                    patch('apps.ventes.services._send_otp_email',
                          return_value=True):
                request_esign_otp(self.link)
            self.assertIsNone(cache.get(_otp_attempts_key(self.link.token)))

    def test_correct_code_still_works_before_lockout(self):
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            cache.set(_otp_cache_key(self.link.token), '654321', 600)
            # Un mauvais essai puis le bon → succès (compteur < max).
            self.assertIsNotNone(
                validate_esign_otp(link=self.link, otp_code='000000'))
            self.assertIsNone(
                validate_esign_otp(link=self.link, otp_code='654321'))
