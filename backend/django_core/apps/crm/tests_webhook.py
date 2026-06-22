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
        # La mise à jour idempotente est tracée dans le chatter.
        from apps.crm.models import LeadActivity
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='Mis à jour via le site web').exists())

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

    # ── T2 — nouveaux champs de capture toiture-3D (additifs, tolérants) ──
    def test_nouveaux_champs_captures(self):
        res = self.post(payload_site(
            factureHiver='1450.50', factureEte='800', eteDifferente=True,
            raccordement='triphase', adresse='12 Rue des Oliviers, Anfa',
            gpsLat='33.589', gpsLng='-7.603'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        # Company forcée côté serveur (jamais du payload).
        self.assertEqual(lead.company, self.company)
        self.assertEqual(str(lead.facture_hiver), '1450.50')
        self.assertEqual(str(lead.facture_ete), '800.00')
        self.assertTrue(lead.ete_differente)
        self.assertEqual(lead.raccordement, 'triphase')
        self.assertEqual(lead.adresse, '12 Rue des Oliviers, Anfa')
        self.assertEqual(str(lead.gps_lat), '33.589000')
        self.assertEqual(str(lead.gps_lng), '-7.603000')

    def test_nouveaux_champs_snake_case_acceptes(self):
        res = self.post(payload_site(
            facture_hiver='990', ete_differente=False,
            gps_lat='34.0', gps_lng='-6.8', address='Rabat centre'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(str(lead.facture_hiver), '990.00')
        self.assertFalse(lead.ete_differente)
        self.assertEqual(str(lead.gps_lat), '34.000000')
        self.assertEqual(lead.adresse, 'Rabat centre')

    def test_raccordement_inconnu_accepte(self):
        # T1 — nouveau choix « Je ne sais pas ».
        res = self.post(payload_site(raccordement='inconnu'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.raccordement, 'inconnu')

    def test_champs_invalides_ignores_jamais_de_crash(self):
        # Décimales non numériques + raccordement hors choix + GPS hors bornes
        # → tous ignorés, le lead est quand même créé.
        res = self.post(payload_site(
            factureHiver='pas-un-nombre', raccordement='wifi',
            gpsLat='999', gpsLng='abc'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.facture_hiver)
        self.assertIsNone(lead.raccordement)
        self.assertIsNone(lead.gps_lat)
        self.assertIsNone(lead.gps_lng)

    def test_champs_absents_inchanges(self):
        # Payload existant sans les nouveaux champs : comportement identique.
        res = self.post(payload_site())
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.facture_hiver)
        self.assertIsNone(lead.facture_ete)
        self.assertFalse(lead.ete_differente)
        self.assertIsNone(lead.raccordement)
