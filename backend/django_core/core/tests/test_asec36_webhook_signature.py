"""ASEC36-revue — ``core.webhook_signature`` : la vérification HMAC Meta
partagée par le webhook Lead Ads (crm) et le webhook WhatsApp SAV (sav).

Comportement identique à l'ancienne fonction du CRM (valide / absente / mal
formée / non-ASCII). La délégation crm + l'import sav sont couverts dans
``apps/crm/test_asec36_revue_signature_core.py`` (``core`` n'importe aucune
app, même en test — contrat import-linter).
"""
import hashlib
import hmac

from django.test import RequestFactory, SimpleTestCase

from core.webhook_signature import signature_hub_sha256_valide

_SECRET = 'secret-asec36'
_CORPS = b'{"entry": []}'


def _requete(signature=None):
    extra = {}
    if signature is not None:
        extra['HTTP_X_HUB_SIGNATURE_256'] = signature
    return RequestFactory().post(
        '/webhook/', data=_CORPS, content_type='application/json', **extra)


def _signature(corps=_CORPS, secret=_SECRET):
    return 'sha256=' + hmac.new(
        secret.encode(), corps, hashlib.sha256).hexdigest()


class SignatureHubTests(SimpleTestCase):
    def test_signature_valide(self):
        self.assertTrue(signature_hub_sha256_valide(
            _requete(_signature()), _SECRET))

    def test_signature_absente_ou_mal_formee(self):
        for sig in (None, '', 'md5=abc', _signature(secret='autre')):
            with self.subTest(sig=sig):
                self.assertFalse(signature_hub_sha256_valide(
                    _requete(sig), _SECRET))

    def test_entete_non_ascii_refuse_sans_erreur(self):
        self.assertFalse(signature_hub_sha256_valide(
            _requete('sha256=é' + 'a' * 63), _SECRET))
