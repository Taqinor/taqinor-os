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


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class QW1DroppedFieldsMappingTests(TestCase):
    """QW1 — plus aucun champ connu du payload réel du site n'est jeté."""

    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor Test QW1', slug='taqinor-test-qw1')
        self.url = reverse('website-lead-webhook')

    def post(self, data, secret=SECRET):
        headers = {'HTTP_X_WEBHOOK_SECRET': secret} if secret is not None else {}
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json', **headers)

    def test_full_realistic_payload_round_trips_with_zero_drops(self):
        """Un payload réaliste complet de /devis/mon-toit ne perd aucun champ connu."""
        res = self.post(payload_site(
            langue_preferee='ar',
            projectTiming='maintenant',
            roofAgeYears=12,
            occupantType='decideur',
            financingIntent='comptant',
            distributeur='inconnu',
            ombrage='partiel',
            batteryInterest=True,
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.langue_preferee, 'darija')
        self.assertEqual(lead.project_timeline, Lead.ProjectTimeline.IMMEDIAT)
        self.assertEqual(lead.roof_age, 12)
        self.assertEqual(lead.ownership, Lead.Ownership.PROPRIETAIRE)
        self.assertEqual(lead.financing_intent, Lead.FinancingIntent.CASH)
        self.assertEqual(lead.distributeur, Lead.Distributeur.AUTRE)
        self.assertEqual(lead.ombrage, Lead.Ombrage.PARTIEL)
        self.assertEqual(lead.batterie_souhaitee, Lead.BatterieSouhaitee.AVEC)

    def test_langue_preferee_key_read(self):
        res = self.post(payload_site(langue_preferee='fr'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.langue_preferee, 'fr')

    def test_project_timing_vocab_mapped(self):
        cases = {
            'maintenant': Lead.ProjectTimeline.IMMEDIAT,
            '3mois': Lead.ProjectTimeline.MOINS_3_MOIS,
            'renseignement': Lead.ProjectTimeline.PLUS_TARD,
        }
        for raw, expected in cases.items():
            res = self.post(payload_site(
                phoneE164=f'+2126{hash(raw) % 10**8:08d}',
                projectTiming=raw))
            lead = Lead.objects.get(pk=res.json()['lead_id'])
            self.assertEqual(lead.project_timeline, expected)

    def test_roof_age_years_key_read(self):
        res = self.post(payload_site(roofAgeYears=30))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.roof_age, 30)

    def test_occupant_type_decideur_mapped_to_proprietaire(self):
        res = self.post(payload_site(occupantType='decideur'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.ownership, Lead.Ownership.PROPRIETAIRE)

    def test_occupant_type_locataire_passthrough(self):
        res = self.post(payload_site(occupantType='locataire'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.ownership, Lead.Ownership.LOCATAIRE)

    def test_financing_intent_vocab_mapped(self):
        cases = {
            'comptant': Lead.FinancingIntent.CASH,
            'financement': Lead.FinancingIntent.CREDIT,
            'indecis': Lead.FinancingIntent.INDECIS,
        }
        for raw, expected in cases.items():
            res = self.post(payload_site(
                phoneE164=f'+2127{hash(raw) % 10**8:08d}',
                financingIntent=raw))
            lead = Lead.objects.get(pk=res.json()['lead_id'])
            self.assertEqual(lead.financing_intent, expected)

    def test_distributeur_inconnu_mapped_to_autre(self):
        res = self.post(payload_site(distributeur='inconnu'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.distributeur, Lead.Distributeur.AUTRE)

    def test_distributeur_onee_passthrough(self):
        res = self.post(payload_site(distributeur='onee'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.distributeur, Lead.Distributeur.ONEE)

    def test_ombrage_previously_omitted_now_read(self):
        res = self.post(payload_site(ombrage='important'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.ombrage, Lead.Ombrage.IMPORTANT)

    def test_battery_interest_previously_omitted_now_read(self):
        res_true = self.post(payload_site(
            phoneE164='+212600000001', batteryInterest=True))
        lead_true = Lead.objects.get(pk=res_true.json()['lead_id'])
        self.assertEqual(lead_true.batterie_souhaitee, Lead.BatterieSouhaitee.AVEC)

        res_false = self.post(payload_site(
            phoneE164='+212600000002', batteryInterest=False))
        lead_false = Lead.objects.get(pk=res_false.json()['lead_id'])
        self.assertEqual(lead_false.batterie_souhaitee, Lead.BatterieSouhaitee.SANS)

    def test_unknown_vocab_never_crashes_lead_still_created(self):
        res = self.post(payload_site(
            projectTiming='garbage', financingIntent='garbage',
            distributeur='garbage', occupantType='garbage',
            ombrage='garbage'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.project_timeline)
        self.assertIsNone(lead.financing_intent)
        self.assertIsNone(lead.distributeur)
        self.assertIsNone(lead.ownership)
        self.assertIsNone(lead.ombrage)


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class QW2SiteFieldsTests(TestCase):
    """QW2 — nouvelles colonnes Lead pour les champs du site sans accueil."""

    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor Test QW2', slug='taqinor-test-qw2')
        self.other_company = Company.objects.create(nom='Autre Société QW2', slug='autre-qw2')
        self.url = reverse('website-lead-webhook')

    def post(self, data, secret=SECRET):
        headers = {'HTTP_X_WEBHOOK_SECRET': secret} if secret is not None else {}
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json', **headers)

    def test_raison_sociale_reuses_societe_column(self):
        res = self.post(payload_site(raisonSociale='ACME Solutions SARL'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.societe, 'ACME Solutions SARL')
        # Pas de colonne dédiée : uniquement `societe`.
        self.assertFalse(hasattr(lead, 'raison_sociale'))

    def test_facility_type_and_site_count_persisted(self):
        res = self.post(payload_site(facilityType='entrepot', siteCount='2-5'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.facility_type, 'entrepot')
        self.assertEqual(lead.site_count, '2-5')

    def test_visit_window_persisted(self):
        res = self.post(payload_site(
            visitWindowPart='matin', visitWindowWeek='cette_semaine'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.visit_window_part, 'matin')
        self.assertEqual(lead.visit_window_week, 'cette_semaine')

    def test_client_ref_persisted_and_garbage_rejected(self):
        res = self.post(payload_site(clientRef='AB12-CD34'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.client_ref, 'AB12-CD34')

        res2 = self.post(payload_site(
            phoneE164='+212600000010', clientRef='a'))  # trop court
        lead2 = Lead.objects.get(pk=res2.json()['lead_id'])
        self.assertIsNone(lead2.client_ref)

    def test_phone_is_foreign_persisted(self):
        res = self.post(payload_site(phoneIsForeign=True))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertTrue(lead.phone_is_foreign)

    def test_page_persisted_and_protected_as_first_touch(self):
        import datetime

        res = self.post(payload_site(
            phoneE164='+212699999999', page='/simulateur'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.page, '/simulateur')

        # Visiteur revenant hors fenêtre de 60 s (même téléphone → dédup
        # couche 2) avec une AUTRE page : le first-touch est préservé.
        lead.date_creation = lead.date_creation - datetime.timedelta(minutes=5)
        lead.save(update_fields=['date_creation'])
        res2 = self.post(payload_site(
            phoneE164='+212699999999', page='/autre-page'))
        self.assertEqual(res2.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.page, '/simulateur')

    def test_company_isolation(self):
        res = self.post(payload_site(facilityType='usine'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.company, self.company)
        self.assertNotEqual(lead.company, self.other_company)


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class QW3ContactPreferenceTests(TestCase):
    """QW3 — "call me" vs "WhatsApp only", distinct de whatsapp_opt_in/Canal."""

    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor Test QW3', slug='taqinor-test-qw3')
        self.url = reverse('website-lead-webhook')

    def post(self, data, secret=SECRET):
        headers = {'HTTP_X_WEBHOOK_SECRET': secret} if secret is not None else {}
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json', **headers)

    def test_phone_ok_preference_persisted(self):
        res = self.post(payload_site(contactPreference='phone_ok'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.contact_preference, 'phone_ok')

    def test_whatsapp_only_preference_persisted(self):
        res = self.post(payload_site(contactPreference='whatsapp_only'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.contact_preference, 'whatsapp_only')

    def test_canal_stays_site_web_regardless_of_contact_preference(self):
        # Le canal marketing d'ORIGINE n'est jamais réécrit par la préférence
        # de contact — deux concepts distincts.
        res = self.post(payload_site(contactPreference='phone_ok'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.canal, Lead.Canal.SITE_WEB)

    def test_distinct_from_whatsapp_opt_in(self):
        # whatsappOptIn=False (pas de consentement marketing WhatsApp) mais
        # contactPreference='phone_ok' (le client veut être rappelé) : les
        # deux signaux coexistent sans se confondre.
        res = self.post(payload_site(
            whatsappOptIn=False, contactPreference='phone_ok'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertFalse(lead.whatsapp_opt_in)
        self.assertEqual(lead.contact_preference, 'phone_ok')

    def test_absent_contact_preference_stays_null(self):
        res = self.post(payload_site())
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.contact_preference)

    def test_garbage_contact_preference_ignored(self):
        res = self.post(payload_site(contactPreference='carrier-pigeon'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.contact_preference)
