"""ASEC36-revue — le webhook Lead Ads du CRM délègue sa vérification HMAC à
la primitive de fondation ``core.webhook_signature`` (partagée avec le
webhook WhatsApp SAV), et le SAV n'importe plus la fonction privée du CRM.
Comportement identique.
"""
import hashlib
import hmac
from pathlib import Path

from django.test import RequestFactory, SimpleTestCase

from apps.crm.webhooks import _check_meta_lead_ads_signature
from core.webhook_signature import signature_hub_sha256_valide

_SECRET = 'secret-asec36-crm'
_CORPS = b'{"object": "page"}'


def _requete(signature=None):
    extra = {}
    if signature is not None:
        extra['HTTP_X_HUB_SIGNATURE_256'] = signature
    return RequestFactory().post(
        '/webhook/', data=_CORPS, content_type='application/json', **extra)


def _signature(secret=_SECRET):
    return 'sha256=' + hmac.new(
        secret.encode(), _CORPS, hashlib.sha256).hexdigest()


class SignatureCoreTests(SimpleTestCase):
    def test_crm_delegue_meme_resultat(self):
        for sig in (_signature(), _signature('autre'), None, 'sha256=é'):
            with self.subTest(sig=sig):
                self.assertEqual(
                    _check_meta_lead_ads_signature(_requete(sig), _SECRET),
                    signature_hub_sha256_valide(_requete(sig), _SECRET))
        self.assertTrue(
            _check_meta_lead_ads_signature(_requete(_signature()), _SECRET))

    def test_sav_n_importe_plus_le_prive_du_crm(self):
        source = (Path(__file__).resolve().parents[1]
                  / 'sav' / 'public_views.py').read_text(encoding='utf-8')
        self.assertNotIn('_check_meta_lead_ads_signature', source)
        self.assertIn('core.webhook_signature', source)
