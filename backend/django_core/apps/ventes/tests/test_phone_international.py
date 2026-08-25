"""25/08/2026 — LANE NUMÉROS INTERNATIONAUX (ordre fondateur : « i want my
system to accept non moroccan phone numbers »).

Couvre `apps.ventes.utils.phone.normalize_phone_e164` (nouvelle fonction) et
`build_wa_url` (apps.ventes.utils.whatsapp), qui délègue désormais à elle.
Ces tests échouaient sur `main` avant le correctif :
  - `normalize_ma_phone('+33612345678')` renvoyait `'21233612345678'`
    (corruption silencieuse) au lieu de `None` ;
  - `build_wa_url` d'un devis/lead à numéro étranger renvoyait `None`
    (« Aucun numéro de téléphone. ») au lieu d'un lien wa.me valide.

Voir aussi `apps.ventes.tests.test_whatsapp.TestPhoneNormalization` (cas
étrangers ajoutés au même correctif) et `apps.crm.tests_phone_international`
(le lead API garde la saisie étrangère telle quelle).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.utils.phone import normalize_ma_phone, normalize_phone_e164
from apps.ventes.utils.whatsapp import build_wa_url

User = get_user_model()


def make_company(slug='phone-intl-co', nom='Phone Intl Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})[0]


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestNormalizePhoneE164(TestCase):
    def test_moroccan_recognized_same_form_as_normalize_ma_phone(self):
        for raw in ('0612345678', '+212612345678', '00212612345678',
                    '612345678', '0512345678'):
            self.assertEqual(
                normalize_phone_e164(raw), normalize_ma_phone(raw))
        self.assertEqual(normalize_phone_e164('0612345678'), '212612345678')

    def test_foreign_with_explicit_indicator_accepted(self):
        self.assertEqual(normalize_phone_e164('+33612345678'), '33612345678')
        self.assertEqual(normalize_phone_e164('+33 6 12 34 56 78'), '33612345678')
        self.assertEqual(normalize_phone_e164('0033612345678'), '33612345678')
        self.assertEqual(normalize_phone_e164('+34600123456'), '34600123456')
        self.assertEqual(normalize_phone_e164('+1 415 555 2671'), '14155552671')

    def test_ambiguous_local_without_indicator_stays_rejected(self):
        # Jamais deviné étranger sans indicatif explicite tapé — même garde
        # que le contrat apps/web/src/lib/phone.ts (WJ64).
        self.assertIsNone(normalize_phone_e164('33612345678'))
        self.assertIsNone(normalize_phone_e164('0812345678'))
        self.assertIsNone(normalize_phone_e164(''))
        self.assertIsNone(normalize_phone_e164(None))
        self.assertIsNone(normalize_phone_e164('abc'))

    def test_malformed_moroccan_under_plus_never_misclassified_as_foreign(self):
        # Un '212' incomplet (indicatif marocain correct, local trop court)
        # ne doit JAMAIS glisser dans le chemin étranger (212 est exclusif
        # au Maroc — aucun autre pays ne commence par cet indicatif).
        self.assertIsNone(normalize_phone_e164('+2126123456'))
        self.assertIsNone(normalize_phone_e164('002126123456'))

    # 25/08/2026 — finding 10, miroir e164 de `test_whatsapp.
    # TestPhoneNormalization.test_212_prefix_with_rewritten_leading_zero_
    # still_recognized` : `normalize_phone_e164` délègue au chemin marocain
    # de `normalize_ma_phone`, donc hérite du même correctif lstrip('0').
    def test_212_prefix_with_rewritten_leading_zero_still_recognized(self):
        self.assertEqual(
            normalize_phone_e164('+212 (0)6 12 34 56 78'), '212612345678')
        self.assertEqual(
            normalize_phone_e164('+212 06 12 34 56 78'), '212612345678')
        self.assertEqual(
            normalize_phone_e164('00212 0612345678'), '212612345678')

    # 25/08/2026 — finding 10(b) : avant le correctif, `normalize_phone_e164`
    # ne retirait que `[\s.\-()]` (contrairement à `normalize_ma_phone`, qui
    # retire TOUT non-chiffre) — un numéro marocain valide saisi avec `/` ou
    # une mention « Tel: » était donc rejeté ici alors que `normalize_ma_phone`
    # l'acceptait déjà (désarmait le bouton WhatsApp d'un devis/lead valide).
    def test_moroccan_with_slash_or_label_separators_recognized(self):
        self.assertEqual(
            normalize_phone_e164('06/12/34/56/78'), '212612345678')
        self.assertEqual(
            normalize_phone_e164('Tel: 0612345678'), '212612345678')
        self.assertEqual(
            normalize_phone_e164('Tel: 06/12/34/56/78'), '212612345678')


class TestNormalizeMaPhoneNeverCorruptsForeign(TestCase):
    def test_foreign_returns_none_not_a_fabricated_212_number(self):
        self.assertIsNone(normalize_ma_phone('+33612345678'))
        self.assertNotEqual(normalize_ma_phone('+33612345678'), '21233612345678')


class TestBuildWaUrlForeign(TestCase):
    def test_foreign_phone_builds_valid_wa_url(self):
        url = build_wa_url('+33612345678', 'Bonjour')
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith('https://wa.me/33612345678?text='))

    def test_moroccan_phone_still_builds_wa_url(self):
        url = build_wa_url('0612345678', 'Bonjour')
        self.assertTrue(url.startswith('https://wa.me/212612345678?text='))

    def test_empty_phone_returns_none(self):
        self.assertIsNone(build_wa_url('', 'Bonjour'))
        self.assertIsNone(build_wa_url(None, 'Bonjour'))


class TestDevisWhatsAppEndpointForeignPhone(TestCase):
    """Bout-en-bout : un devis dont le client a un numéro étranger peut être
    envoyé par WhatsApp (avant : 400 « Aucun numéro de téléphone »)."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='wa_intl_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Dupont', telephone='+33612345678')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-INTL-1',
            client=self.client_obj)

    def test_whatsapp_preview_builds_foreign_wa_url(self):
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/whatsapp-preview/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['wa_url'].startswith(
            'https://wa.me/33612345678?text='))

    def test_whatsapp_send_builds_foreign_wa_url_and_marks_sent(self):
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/whatsapp/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['wa_url'].startswith(
            'https://wa.me/33612345678?text='))
