"""Tests du récepteur de leads du site web (apps/crm/webhooks.py)."""

import json

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from .models import Lead, LeadActivity, WebsiteLeadPayload

SECRET = 'test-secret-webhook-123'


def payload_site(**extra):
    """Charge utile exactement de la forme émise par apps/web (lead.ts)."""
    base = {
        'fullName': 'Amina Benali',
        'phoneE164': '+212661850410',
        'whatsappOptIn': True,
        'city': 'Casablanca',
        'roofType': 'villa',
        'billRange': '1500-3000',
        'consent': True,
        'fbclid': 'fb.1.123.ABC',
        'utm': {
            'utm_source': 'facebook',
            'utm_medium': 'cpc',
            'utm_campaign': 'lancement',
        },
        'consentTimestamp': '2026-06-13T10:00:00+00:00',
        'submittedAt': '2026-06-13T10:00:00+00:00',
        'qualified': True,
        'band': {'kwcMin': 5, 'kwcMax': 9, 'kwcLabel': '5 à 9 kWc',
                 'paybackLabel': '4 à 6 ans', 'source': 'local'},
        'page': '/',
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class WebsiteLeadWebhookTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor Test', slug='taqinor-test')
        self.url = reverse('website-lead-webhook')

    def post(self, data, secret=SECRET):
        headers = {'HTTP_X_WEBHOOK_SECRET': secret} if secret is not None else {}
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json', **headers)

    def test_payload_valide_cree_un_lead_complet(self):
        res = self.post(payload_site())
        self.assertEqual(res.status_code, 201)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.company, self.company)
        self.assertEqual(lead.nom, 'Amina Benali')
        self.assertEqual(lead.telephone, '+212661850410')
        self.assertEqual(lead.ville, 'Casablanca')
        self.assertEqual(lead.roof_type, 'villa')
        self.assertEqual(lead.bill_range_bucket, '1500-3000')
        self.assertEqual(lead.roi_band, '5 à 9 kWc · 4 à 6 ans')
        self.assertEqual(lead.fbclid, 'fb.1.123.ABC')
        self.assertEqual(lead.utm_source, 'facebook')
        self.assertEqual(lead.utm_medium, 'cpc')
        self.assertEqual(lead.utm_campaign, 'lancement')
        self.assertTrue(lead.whatsapp_opt_in)
        self.assertEqual(lead.whatsapp, '+212661850410')
        self.assertIsNotNone(lead.consent_timestamp)
        self.assertEqual(lead.source, Lead.Source.SITE_WEB)
        self.assertEqual(lead.canal, Lead.Canal.SITE_WEB)
        # Historique : « créé via le site web »
        activity = LeadActivity.objects.get(lead=lead)
        self.assertEqual(activity.kind, LeadActivity.Kind.CREATION)
        self.assertIn('site web', activity.body)
        # Brut stocké et rattaché
        raw = WebsiteLeadPayload.objects.get()
        self.assertTrue(raw.processed)
        self.assertEqual(raw.lead, lead)

    def test_secret_absent_ou_faux_rejete_401(self):
        self.assertEqual(self.post(payload_site(), secret=None).status_code, 401)
        self.assertEqual(self.post(payload_site(), secret='mauvais').status_code, 401)
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(WebsiteLeadPayload.objects.count(), 0)

    @override_settings(WEBSITE_LEAD_WEBHOOK_SECRET='')
    def test_secret_non_configure_ferme_le_endpoint(self):
        self.assertEqual(self.post(payload_site(), secret='').status_code, 401)

    def test_relance_meme_telephone_meme_minute_ne_duplique_pas(self):
        first = self.post(payload_site())
        self.assertEqual(first.status_code, 201)
        retry = self.post(payload_site(city='Rabat'))
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(Lead.objects.count(), 1)
        lead = Lead.objects.get()
        self.assertEqual(lead.ville, 'Rabat')  # mise à jour, pas de jumeau
        # Les DEUX payloads bruts sont conservés (jamais perdre une trace)
        self.assertEqual(WebsiteLeadPayload.objects.count(), 2)

    def test_sous_seuil_accepte_et_etiquete(self):
        res = self.post(payload_site(
            billRange='800-1000', qualified=False,
            band={'kwcLabel': '2 à 4 kWc', 'paybackLabel': '5 à 7 ans'}))
        self.assertEqual(res.status_code, 201)
        lead = Lead.objects.get()
        self.assertEqual(lead.tags, 'Sous le seuil 1 000 MAD')
        self.assertEqual(lead.bill_range_bucket, '800-1000')

    def test_mapping_echoue_mais_le_brut_survit(self):
        # billRange inattendu + band non-dict → le mapping du band lèvera ;
        # quoi qu'il arrive, le payload brut doit être stocké et signalé.
        res = self.post(payload_site(band='pas-un-objet'))
        self.assertIn(res.status_code, (201, 202))
        self.assertEqual(WebsiteLeadPayload.objects.count(), 1)

    def test_json_invalide_400_sans_crash(self):
        res = self.client.post(
            self.url, data='{pas du json', content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)
        self.assertEqual(res.status_code, 400)
