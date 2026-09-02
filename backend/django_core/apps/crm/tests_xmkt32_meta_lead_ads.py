"""XMKT32 — Sync Meta Lead Ads → leads CRM (gated, API officielle simulée).

Couvre :
  - sans jeton configuré : GET de vérification → 404, POST → no-op 200 (rien
    n'est créé) ;
  - GET de vérification avec le bon hub.verify_token → renvoie hub.challenge ;
  - GET avec un mauvais token → 403 ;
  - POST simulé (Graph API mocké) → lead créé, attribué (canal META_ADS,
    utm_source=facebook, utm_campaign/utm_content = campagne/adset) ;
  - un second POST avec le MÊME leadgen_id (retry Meta) ne crée pas de
    deuxième lead (idempotence sur leadgen_id) ;
  - D-CRX1 (02/09/2026) — un prospect déjà connu (même téléphone) NE fait plus
    absorber la touche Meta : un NOUVEAU lead est créé à chaque fois, le
    doublon est seulement SIGNALÉ (note chatter) et le commercial est HÉRITÉ
    (parité QW11) ; un contact connu mais ARCHIVÉ donne lui aussi un nouveau
    lead, sans héritage d'owner ;
  - CRX2 — chaque entrée du batch est persistée AVANT mapping
    (``WebsiteLeadPayload`` source ``meta_lead_ads``) : un échec Graph laisse
    une ligne REJOUABLE (parité QX16) au lieu de perdre le lead ;
  - aucun scraping : la récupération passe par ``fetch_meta_lead_data``
    (Graph API officiel), jamais par un fetch de page HTML.
  - PUB26 — signature HMAC ``X-Hub-Signature-256`` : bien formée → traité ;
    mal signée → 403 ; QJR414/DR3 — secret ABSENT → **403** (fail-closed), là
    où PUB26 acceptait encore le payload « par rétro-compatibilité » (le test
    permissif correspondant a bien été retiré par QJR414 — vérifié en CRX4) ;
  - CRX4 — ``leadgen_id`` borné (numérique) AVANT toute construction de l'URL
    Graph : une valeur hostile ne part jamais sur le réseau.
"""
import hashlib
import hmac
import json
from unittest import mock

from django.db.models import Q
from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from apps.crm.models import Lead

VERIFY_TOKEN = 'test-verify-token'
ACCESS_TOKEN = 'test-access-token'
APP_SECRET = 'test-app-secret'


def _sign(secret, body: bytes) -> str:
    return 'sha256=' + hmac.new(
        secret.encode(), body, hashlib.sha256).hexdigest()


def _lead_data(leadgen_id='1001', nom='Yassine Bennani',
               telephone='+212661112233', email='yassine@example.com',
               ville='Casablanca'):
    return {
        'field_data': [
            {'name': 'full_name', 'values': [nom]},
            {'name': 'phone_number', 'values': [telephone]},
            {'name': 'email', 'values': [email]},
            {'name': 'city', 'values': [ville]},
        ]
    }


def _batch_notification_payload(leadgen_ids):
    """CRX3 — vrai batch Meta : PLUSIEURS entrées dans une seule notification
    (une par lead), la forme que Meta envoie réellement en pointe de trafic et
    qu'AUCUN test ne couvrait."""
    return {
        'entry': [
            {'changes': [{'field': 'leadgen',
                          'value': {'leadgen_id': lg, 'ad_id': '',
                                    'adgroup_id': '', 'form_id': ''}}]}
            for lg in leadgen_ids
        ]
    }


def _notification_payload(leadgen_id='1001', ad_id='', adgroup_id='',
                          form_id=''):
    # ADSENG1 — le webhook leadgen de Meta pousse UNIQUEMENT des clés de
    # jointure stables (ad_id/adgroup_id/form_id), JAMAIS campaign_name/
    # adset_name : les noms lisibles sont résolus côté ERP via les miroirs
    # adsengine. Ce payload reflète donc la vraie forme Meta.
    return {
        'entry': [{
            'changes': [{
                'field': 'leadgen',
                'value': {
                    'leadgen_id': leadgen_id,
                    'ad_id': ad_id,
                    'adgroup_id': adgroup_id,
                    'form_id': form_id,
                },
            }]
        }]
    }


class MetaLeadAdsUnconfiguredTests(TestCase):
    """Sans jeton configuré : 404/no-op — jamais d'exception."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta Off', slug='taqinor-meta-off')
        self.url = reverse('meta-lead-ads-webhook')

    @override_settings(META_LEAD_ADS_VERIFY_TOKEN='', META_LEAD_ADS_ACCESS_TOKEN='')
    def test_get_verification_404_without_verify_token(self):
        resp = self.client.get(self.url, {
            'hub.mode': 'subscribe', 'hub.verify_token': 'anything',
            'hub.challenge': 'chal123'})
        self.assertEqual(resp.status_code, 404)

    @override_settings(META_LEAD_ADS_VERIFY_TOKEN='',
                       META_LEAD_ADS_ACCESS_TOKEN='',
                       META_LEAD_ADS_APP_SECRET='')
    def test_post_refuse_sans_secret_d_application(self):
        """QJR414 (DR3) — FAIL-CLOSED : sans ``META_LEAD_ADS_APP_SECRET``, le
        POST est REFUSÉ (403) avant même la résolution du token d'accès.

        Remplace ``test_post_noop_without_access_token`` (200 no-op) : la
        garde de signature passe désormais AVANT, et un POST non signé n'a
        plus le droit d'atteindre quoi que ce soit."""
        resp = self.client.post(
            self.url, data=json.dumps(_notification_payload()),
            content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Lead.objects.count(), 0)


@override_settings(META_LEAD_ADS_VERIFY_TOKEN=VERIFY_TOKEN)
class MetaLeadAdsVerificationTests(TestCase):
    def setUp(self):
        self.url = reverse('meta-lead-ads-webhook')

    def test_correct_token_returns_challenge(self):
        resp = self.client.get(self.url, {
            'hub.mode': 'subscribe', 'hub.verify_token': VERIFY_TOKEN,
            'hub.challenge': 'chal-xyz'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode(), 'chal-xyz')

    def test_wrong_token_is_refused(self):
        resp = self.client.get(self.url, {
            'hub.mode': 'subscribe', 'hub.verify_token': 'wrong',
            'hub.challenge': 'chal-xyz'})
        self.assertEqual(resp.status_code, 403)


@override_settings(META_LEAD_ADS_ACCESS_TOKEN=ACCESS_TOKEN,
                   META_LEAD_ADS_APP_SECRET=APP_SECRET)
class MetaLeadAdsIngestTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta On', slug='taqinor-meta-on')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload):
        # QJR414 (DR3) — le webhook est FAIL-CLOSED : ces tests portent sur
        # l'INGESTION, pas sur la signature (couverte par
        # MetaLeadAdsSignatureTests), ils signent donc leur corps.
        body = json.dumps(payload).encode('utf-8')
        return self.client.post(
            self.url, data=body, content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=_sign(APP_SECRET, body))

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_simulated_payload_creates_attributed_lead(self, fetch_mock):
        """Payload Lead Ads simulé (API officielle mockée) → lead créé,
        attribué canal META_ADS + utm_source facebook ; le NOM de campagne est
        résolu via les miroirs adsengine (ADSENG1 : Meta ne pousse que
        ad_id/adgroup_id), utm_content = ad-<ad_id> (convention ADSENG23)."""
        from apps.adsengine.models import AdCampaignMirror, AdSetMirror
        campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='CMP-1', name='Campagne Été',
            status='PAUSED')
        AdSetMirror.objects.create(
            company=self.company, meta_id='ASET-1', name='Adset Casablanca',
            campaign=campaign)
        fetch_mock.return_value = _lead_data(leadgen_id='2001')
        resp = self._post(_notification_payload(
            leadgen_id='2001', ad_id='AD-2001', adgroup_id='ASET-1',
            form_id='FORM-1'))
        self.assertEqual(resp.status_code, 200)
        fetch_mock.assert_called_once_with('2001', ACCESS_TOKEN)

        lead = Lead.objects.get(company=self.company)
        self.assertEqual(lead.canal, Lead.Canal.META_ADS)
        self.assertEqual(lead.source, Lead.Source.META_LEAD_ADS)
        self.assertEqual(lead.utm_source, 'facebook')
        # Nom de campagne résolu localement via le miroir (ad_id/adgroup_id).
        self.assertEqual(lead.utm_campaign, 'Campagne Été')
        # Convention ADSENG23 : utm_content = ad-<ad_id>, jamais l'adset_name.
        self.assertEqual(lead.utm_content, 'ad-AD-2001')
        self.assertEqual(lead.external_system, 'meta_lead_ads')
        self.assertEqual(lead.external_id, '2001')
        self.assertEqual(lead.nom, 'Yassine Bennani')

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_duplicate_leadgen_id_is_absorbed_not_duplicated(self, fetch_mock):
        """Un retry Meta (même leadgen_id) ne crée pas un deuxième lead."""
        fetch_mock.return_value = _lead_data(leadgen_id='3001')
        self._post(_notification_payload(leadgen_id='3001'))
        self._post(_notification_payload(leadgen_id='3001'))
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_contact_connu_cree_toujours_un_nouveau_lead(self, fetch_mock):
        """D-CRX1 : un prospect déjà connu (même téléphone, autre canal) ne
        fait PLUS absorber la touche Meta — un NOUVEAU lead est créé.

        La fiche d'origine ressort INTACTE (aucune écriture sur ce chemin :
        ni ``external_id``, ni canal, ni utm), le nouveau lead porte toute
        l'attribution Meta, hérite du commercial de la fiche d'origine (parité
        QW11) et porte la note chatter de doublon."""
        from apps.crm.models import LeadActivity
        from django.contrib.auth import get_user_model
        commercial = get_user_model().objects.create_user(
            username='meta_crx1_owner', password='x',
            company=self.company, role_legacy='responsable')
        existing = Lead.objects.create(
            company=self.company, nom='Yassine Ancien',
            telephone='+212661112233', canal=Lead.Canal.TELEPHONE,
            owner=commercial)
        fetch_mock.return_value = _lead_data(
            leadgen_id='4001', telephone='+212661112233')
        resp = self._post(_notification_payload(leadgen_id='4001'))
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 2)
        nouveau = Lead.objects.get(
            company=self.company, external_id='4001')
        self.assertNotEqual(nouveau.pk, existing.pk)
        self.assertEqual(nouveau.canal, Lead.Canal.META_ADS)
        self.assertEqual(nouveau.source, Lead.Source.META_LEAD_ADS)
        self.assertEqual(nouveau.utm_source, 'facebook')
        # Héritage du commercial (QW11) — jamais deux commerciaux sur le
        # même client. La note le dit explicitement (c'est la seule preuve
        # que l'owner vient de l'HÉRITAGE et non du round-robin par défaut).
        self.assertEqual(nouveau.owner_id, commercial.pk)
        note = LeadActivity.objects.filter(
            lead=nouveau, body__startswith='Doublon possible').first()
        self.assertIsNotNone(note)
        self.assertIn(f"comme la fiche d'origine #{existing.pk}", note.body)
        # La fiche d'origine n'a PAS été touchée.
        existing.refresh_from_db()
        self.assertEqual(existing.external_id, None)
        self.assertEqual(existing.canal, Lead.Canal.TELEPHONE)
        # Signalement du doublon sur le NOUVEAU lead uniquement.
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=nouveau, body__startswith='Doublon possible').exists())
        self.assertFalse(
            LeadActivity.objects.filter(
                lead=existing, body__startswith='Doublon possible').exists())

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_contact_archive_cree_aussi_un_nouveau_lead(self, fetch_mock):
        """D-CRX1 — cas explicitement refusé à l'adoucissement : un contact
        connu mais ARCHIVÉ donne LUI AUSSI un nouveau lead.

        L'archivé est mentionné dans la note de doublon (signalement) mais ne
        transmet PAS son owner (``_pick_owner_from_duplicates``) : une fiche
        classée au rebut ne ressuscite plus silencieusement."""
        from apps.crm.models import LeadActivity
        from django.contrib.auth import get_user_model
        ancien_commercial = get_user_model().objects.create_user(
            username='meta_crx1_archive', password='x',
            company=self.company, role_legacy='responsable')
        archive = Lead.objects.create(
            company=self.company, nom='Yassine Archivé',
            telephone='+212661114444', canal=Lead.Canal.TELEPHONE,
            owner=ancien_commercial, is_archived=True)
        fetch_mock.return_value = _lead_data(
            leadgen_id='4002', telephone='+212661114444')
        resp = self._post(_notification_payload(leadgen_id='4002'))
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 2)
        nouveau = Lead.objects.get(company=self.company, external_id='4002')
        self.assertNotEqual(nouveau.pk, archive.pk)
        # L'archivé reste archivé et intact.
        archive.refresh_from_db()
        self.assertTrue(archive.is_archived)
        self.assertEqual(archive.external_id, None)
        # Il est tout de même SIGNALÉ sur le nouveau lead — mais SANS
        # héritage (la note ne mentionne aucune fiche d'origine).
        note = LeadActivity.objects.filter(
            lead=nouveau, body__startswith='Doublon possible').first()
        self.assertIsNotNone(note)
        self.assertIn(f'#{archive.pk}', note.body)
        self.assertNotIn("comme la fiche d'origine", note.body)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_fetch_failure_is_skipped_not_fatal(self, fetch_mock):
        """Un échec de récupération Graph API pour UN lead n'empêche pas la
        réponse 200 (jamais d'exception au webhook)."""
        fetch_mock.side_effect = Exception('boom')
        resp = self._post(_notification_payload(leadgen_id='5001'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)


@override_settings(META_LEAD_ADS_ACCESS_TOKEN=ACCESS_TOKEN,
                   META_LEAD_ADS_APP_SECRET=APP_SECRET)
class MetaLeadAdsStoreAndReplayTests(TestCase):
    """CRX2 — « jamais perdre un lead », parité site (QX16).

    Chaque entrée du batch Meta est PERSISTÉE avant tout mapping ; une
    récupération Graph en échec laisse une ligne REJOUABLE au lieu de perdre
    définitivement la touche (l'ancien ``continue`` la jetait)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta Store', slug='taqinor-meta-store')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload):
        body = json.dumps(payload).encode('utf-8')
        return self.client.post(
            self.url, data=body, content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=_sign(APP_SECRET, body))

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_entree_traitee_laisse_une_ligne_brute_reliee(self, fetch_mock):
        """Succès : la ligne brute existe, marquée traitée et reliée au lead."""
        from apps.crm.models import WebsiteLeadPayload
        fetch_mock.return_value = _lead_data(leadgen_id='8001')
        resp = self._post(_notification_payload(
            leadgen_id='8001', ad_id='AD-8001'))
        self.assertEqual(resp.status_code, 200)

        raw = WebsiteLeadPayload.objects.get(company=self.company)
        self.assertEqual(raw.source, WebsiteLeadPayload.Source.META_LEAD_ADS)
        self.assertTrue(raw.processed)
        self.assertIsNotNone(raw.lead_id)
        # Le brut conserve l'entrée Meta TELLE QUELLE (clés de jointure).
        self.assertEqual(raw.payload.get('leadgen_id'), '8001')
        self.assertEqual(raw.payload.get('ad_id'), 'AD-8001')

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_echec_graph_laisse_une_ligne_rejouable(self, fetch_mock):
        """Échec Graph : AUCUN lead, mais la touche est conservée, non traitée
        et avec son erreur — donc rejouable ; le rejeu (une fois le Graph de
        nouveau joignable) crée bien le lead et clôt la ligne."""
        from apps.crm.models import WebsiteLeadPayload
        from apps.crm.webhooks import replay_meta_lead_payload

        fetch_mock.side_effect = Exception('graph down')
        resp = self._post(_notification_payload(leadgen_id='8002'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)

        raw = WebsiteLeadPayload.objects.get(company=self.company)
        self.assertEqual(raw.source, WebsiteLeadPayload.Source.META_LEAD_ADS)
        self.assertFalse(raw.processed)
        self.assertIsNone(raw.lead_id)
        self.assertIn('graph down', raw.error)
        # La ligne ressort bien dans la file « à rejouer » du viewset QX16.
        self.assertIn(
            raw,
            list(WebsiteLeadPayload.objects.filter(
                Q(error__gt='') | Q(lead__isnull=True))))

        # Rejeu : même chemin de mapping que le webhook, Graph rétabli.
        fetch_mock.side_effect = None
        fetch_mock.return_value = _lead_data(leadgen_id='8002')
        ok, detail, lead = replay_meta_lead_payload(raw)
        self.assertTrue(ok, msg=detail)
        self.assertIsNotNone(lead)
        raw.refresh_from_db()
        self.assertTrue(raw.processed)
        self.assertEqual(raw.lead_id, lead.pk)
        self.assertEqual(raw.error, '')
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)


@override_settings(META_LEAD_ADS_ACCESS_TOKEN=ACCESS_TOKEN,
                   META_LEAD_ADS_APP_SECRET=APP_SECRET)
class MetaLeadAdsBatchIsolationTests(TestCase):
    """CRX3 — isolation PAR ENTRÉE du batch (premier test multi-entrées).

    Un batch Meta porte plusieurs leads : l'échec de l'un ne doit plus
    abandonner les SUIVANTS (Meta ne les rejoue pas, le webhook ayant
    répondu), et la réponse doit dire combien ont réussi/échoué."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta Batch', slug='taqinor-meta-batch')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload):
        body = json.dumps(payload).encode('utf-8')
        return self.client.post(
            self.url, data=body, content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=_sign(APP_SECRET, body))

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_batch_multi_entrees_toutes_traitees(self, fetch_mock):
        """Trois entrées saines → trois leads, compteurs cohérents."""
        fetch_mock.side_effect = lambda lg, tok: _lead_data(
            leadgen_id=lg, telephone=f'+21266000{lg}',
            email=f'lead{lg}@example.com')
        resp = self._post(_batch_notification_payload(
            ['9101', '9102', '9103']))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['created'], 3)
        self.assertEqual(body['failed'], 0)
        self.assertEqual(len(body['lead_ids']), 3)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 3)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_une_entree_en_echec_n_abandonne_pas_les_suivantes(self, fetch_mock):
        """L'entrée du MILIEU échoue : les deux autres sont créées quand même,
        la réponse compte 2 réussies / 1 échouée, et l'échouée laisse une
        ligne brute rejouable (CRX2)."""
        from apps.crm.models import WebsiteLeadPayload

        def _fetch(leadgen_id, token):
            if leadgen_id == '9202':
                raise Exception('graph 500')
            return _lead_data(leadgen_id=leadgen_id,
                              telephone=f'+21266000{leadgen_id}',
                              email=f'lead{leadgen_id}@example.com')

        fetch_mock.side_effect = _fetch
        resp = self._post(_batch_notification_payload(
            ['9201', '9202', '9203']))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['created'], 2)
        self.assertEqual(body['failed'], 1)

        # La 3e entrée — celle qui suivait l'échec — existe bien.
        self.assertTrue(Lead.objects.filter(
            company=self.company, external_id='9203').exists())
        self.assertFalse(Lead.objects.filter(
            company=self.company, external_id='9202').exists())
        # Et la touche perdue est conservée, rejouable.
        raw = WebsiteLeadPayload.objects.get(
            company=self.company, payload__leadgen_id='9202')
        self.assertFalse(raw.processed)
        self.assertIn('graph 500', raw.error)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_exception_de_creation_n_abandonne_pas_le_batch(self, fetch_mock):
        """Cas que l'ancien try/except du BATCH perdait : ce n'est pas le
        fetch qui casse mais la CRÉATION du lead. Avant, l'exception remontait
        au niveau batch et toutes les entrées suivantes étaient abandonnées."""
        from apps.crm import services as crm_services
        from apps.crm.models import WebsiteLeadPayload

        # Capturé AVANT le patch : sinon le repli appellerait le mock
        # lui-même (récursion infinie).
        vrai = crm_services.create_lead_from_meta_lead_ads

        fetch_mock.side_effect = lambda lg, tok: _lead_data(
            leadgen_id=lg, telephone=f'+21266000{lg}',
            email=f'lead{lg}@example.com')

        def _create(**kwargs):
            if str(kwargs.get('leadgen_id')) == '9301':
                raise RuntimeError('create casse')
            return vrai(**kwargs)

        with mock.patch.object(
                crm_services, 'create_lead_from_meta_lead_ads', _create):
            resp = self._post(_batch_notification_payload(['9301', '9302']))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['created'], 1)
        self.assertEqual(body['failed'], 1)
        self.assertTrue(Lead.objects.filter(
            company=self.company, external_id='9302').exists())
        raw = WebsiteLeadPayload.objects.get(
            company=self.company, payload__leadgen_id='9301')
        self.assertFalse(raw.processed)
        self.assertIn('create casse', raw.error)


@override_settings(
    META_LEAD_ADS_ACCESS_TOKEN=ACCESS_TOKEN, META_LEAD_ADS_APP_SECRET=APP_SECRET)
class MetaLeadAdsSignatureTests(TestCase):
    """PUB26 — vérification HMAC ``X-Hub-Signature-256`` du POST de notification."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta Sig', slug='taqinor-meta-sig')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload, *, signature=None):
        body = json.dumps(payload).encode('utf-8')
        headers = {}
        if signature is not None:
            headers['HTTP_X_HUB_SIGNATURE_256'] = signature
        return self.client.post(
            self.url, data=body, content_type='application/json', **headers)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_valid_signature_is_processed(self, fetch_mock):
        fetch_mock.return_value = _lead_data(leadgen_id='6001')
        payload = _notification_payload(leadgen_id='6001')
        body = json.dumps(payload).encode('utf-8')
        resp = self._post(payload, signature=_sign(APP_SECRET, body))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)

    def test_missing_signature_is_rejected_403(self):
        resp = self._post(_notification_payload(leadgen_id='6002'))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)

    def test_wrong_signature_is_rejected_403(self):
        resp = self._post(
            _notification_payload(leadgen_id='6003'),
            signature='sha256=' + ('0' * 64))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    @override_settings(META_LEAD_ADS_APP_SECRET='')
    def test_absent_secret_est_fail_closed(self, fetch_mock):
        """QJR414 (DR3) — secret non configuré : le webhook REFUSE (403) et ne
        crée AUCUN lead.

        Remplace ``test_absent_secret_stays_backward_compatible`` : la
        rétro-compatibilité de PUB26 laissait le déploiement par défaut OUVERT
        (le réglage vaut '' et n'était documenté nulle part). La
        synchronisation entrante reste en pause tant que Reda n'a pas posé le
        secret au deploy — c'est la décision, pas une panne."""
        fetch_mock.return_value = _lead_data(leadgen_id='6004')
        resp = self._post(_notification_payload(leadgen_id='6004'))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)
        fetch_mock.assert_not_called()


@override_settings(META_LEAD_ADS_ACCESS_TOKEN='',
                   META_LEAD_ADS_APP_SECRET=APP_SECRET)
class MetaLeadAdsConnectionFallbackTests(TestCase):
    """FIXPUB1 — sans ``META_LEAD_ADS_ACCESS_TOKEN`` (env), le webhook utilise le
    token de la ``MetaConnection`` activée de la société ; l'env, quand présent,
    gagne toujours. Corrige le compte historique qui n'a QU'une connexion
    tokenisée (pas d'env) et dont la capture ne partait jamais."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta Conn', slug='taqinor-meta-conn')
        from apps.adsengine.models import MetaConnection
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'CONN-TOKEN'}, ad_account_id='act_7')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload):
        # QJR414 (DR3) — corps signé : le webhook est FAIL-CLOSED. Ces tests
        # portent sur la RÉSOLUTION du token d'accès, pas sur la signature.
        body = json.dumps(payload).encode('utf-8')
        return self.client.post(
            self.url, data=body, content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=_sign(APP_SECRET, body))

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_uses_connection_token_when_env_absent(self, fetch_mock):
        """Sans env : le fetch Graph API part avec le token de la connexion."""
        fetch_mock.return_value = _lead_data(leadgen_id='7001')
        resp = self._post(_notification_payload(leadgen_id='7001'))
        self.assertEqual(resp.status_code, 200)
        fetch_mock.assert_called_once_with('7001', 'CONN-TOKEN')
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)

    @override_settings(META_LEAD_ADS_ACCESS_TOKEN='ENV-TOKEN')
    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_env_token_wins_over_connection(self, fetch_mock):
        """Env présent : il l'emporte sur le token de la connexion."""
        fetch_mock.return_value = _lead_data(leadgen_id='7002')
        resp = self._post(_notification_payload(leadgen_id='7002'))
        self.assertEqual(resp.status_code, 200)
        fetch_mock.assert_called_once_with('7002', 'ENV-TOKEN')


class FetchMetaLeadDataVersionTests(TestCase):
    """Garde anti-dérive : le fetch Graph du webhook suit la SOURCE UNIQUE de
    version (apps.adsengine.api_version), jamais une version codée en dur —
    la v19.0 restée ici était morte depuis 02/2025 (même dérive que l'émetteur
    CAPI ventes avant ADSENG2)."""

    def test_fetch_builds_url_from_shared_graph_base(self):
        from unittest.mock import patch

        from apps.adsengine.api_version import GRAPH_BASE_URL
        from apps.crm.webhooks import fetch_meta_lead_data

        seen = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"field_data": []}'

        def fake_urlopen(url, timeout=None):
            seen['url'] = url
            return _Resp()

        with patch('urllib.request.urlopen', fake_urlopen):
            data = fetch_meta_lead_data('42', 'tok')
        self.assertEqual(data, {'field_data': []})
        self.assertTrue(
            seen['url'].startswith(f'{GRAPH_BASE_URL}/42'),
            msg=f"URL Graph inattendue : {seen['url']}")
        self.assertNotIn('v19.0', seen['url'])


class MetaLeadgenIdValidationTests(TestCase):
    """CRX4 (résidu post-QJR414) — ``leadgen_id`` vient du corps du webhook et
    était interpolé TEL QUEL dans l'URL Graph. Il est désormais borné à un
    identifiant numérique AVANT toute construction d'URL : aucune requête ne
    part pour une valeur douteuse."""

    def _urlopen_espion(self):
        appels = []

        def fake_urlopen(url, timeout=None):  # pragma: no cover - jamais
            appels.append(url)                # atteint sur les cas refusés
            raise AssertionError(
                f'urlopen ne doit pas être appelé : {url}')

        return appels, fake_urlopen

    def test_valeurs_hostiles_sont_refusees_sans_appel_reseau(self):
        from unittest.mock import patch

        from apps.crm.webhooks import fetch_meta_lead_data

        appels, fake_urlopen = self._urlopen_espion()
        hostiles = [
            '123/../../me?fields=id',   # sortie du chemin
            '123&fields=access_token',  # paramètre injecté
            'lg-web-1',                 # non numérique
            '',                         # vide
            None,                       # absent
            '9' * 33,                   # au-delà de la borne
        ]
        for valeur in hostiles:
            with self.subTest(valeur=valeur):
                with patch('urllib.request.urlopen', fake_urlopen):
                    with self.assertRaises(ValueError):
                        fetch_meta_lead_data(valeur, 'tok')
        self.assertEqual(appels, [])

    def test_identifiant_numerique_reste_accepte(self):
        from unittest.mock import patch

        from apps.adsengine.api_version import GRAPH_BASE_URL
        from apps.crm.webhooks import fetch_meta_lead_data

        seen = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"field_data": []}'

        def fake_urlopen(url, timeout=None):
            seen['url'] = url
            return _Resp()

        with patch('urllib.request.urlopen', fake_urlopen):
            data = fetch_meta_lead_data(' 123456789 ', 'tok')
        self.assertEqual(data, {'field_data': []})
        # Normalisé (espaces retirés) puis interpolé.
        self.assertTrue(seen['url'].startswith(f'{GRAPH_BASE_URL}/123456789?'))
