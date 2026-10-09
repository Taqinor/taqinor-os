"""AACQ79 — Garde permanente des webhooks PUBLICS de lead.

Invariant : un webhook public de lead (site, Meta Lead Ads, demande de
rendez-vous) qui répond 2xx a écrit une ligne DURABLE (charge utile brute
``WebsiteLeadPayload`` portant l'éventuelle erreur, ou le lead lui-même) ;
sinon il répond non-2xx. Prouvé en forçant une panne interne du mapping, puis
une livraison dédupliquée, puis un ping sans lead — vraies vues, requêtes
signées (secrets de test), seules les E/S externes simulées
(``fetch_meta_lead_data``, Celery ``apply_async``).

Les vues sont ÉNUMÉRÉES depuis l'URLconf (toute route ``webhook`` des apps
``crm`` et ``adsengine``) : une nouvelle vue non classée ci-dessous fait
échouer la garde.
"""
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from authentication.models import Company

from apps.crm.models import Lead, WebsiteLeadPayload

SECRET_SITE = 'aacq79-secret-site'
APP_SECRET = 'aacq79-app-secret'
SECRET_RDV = 'r' * 64
APPLY_ASYNC = 'apps.ventes.tasks.task_devis_automatique_depuis_lead.apply_async'

# Vues publiques de lead COUVERTES par cette garde (nom de la vue → test).
COUVERTES = {
    'website_lead_webhook': 'test_site_web',
    'meta_lead_ads_webhook': 'test_meta_lead_ads',
    'demande_rdv_webhook': 'test_demande_rdv',
}
# Routes « webhook » qui ne sont PAS des récepteurs de formulaire de lead —
# chacune avec sa raison (une vue nouvelle doit être classée ici ou ci-dessus).
HORS_GARDE = {
    'MetaWebhookLeadgenSubscribeView':
        "geste AUTHENTIFIÉ (adsengine_manage) d'abonnement de la Page au "
        "champ leadgen : pas un récepteur public",
    'WhatsAppCloudWebhookView':
        "messagerie WhatsApp Cloud (referral CTWA → CtwaReferral, upsert "
        "idempotent par message) : pas un formulaire de lead",
}


def _routes_webhook(patterns=None, prefixe=''):
    """[(route, nom de la vue, module)] de toute route contenant « webhook »."""
    patterns = get_resolver().url_patterns if patterns is None else patterns
    trouvees = []
    for p in patterns:
        route = prefixe + str(p.pattern)
        if isinstance(p, URLResolver):
            trouvees.extend(_routes_webhook(p.url_patterns, route))
        elif isinstance(p, URLPattern) and 'webhook' in route:
            cb = p.callback
            classe = getattr(cb, 'view_class', None) or getattr(cb, 'cls', None)
            nom = classe.__name__ if classe is not None else cb.__name__
            module = (classe.__module__ if classe is not None
                      else getattr(cb, '__module__', ''))
            trouvees.append((route, nom, module))
    return trouvees


def _sign_hub(secret, body):
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _sign_rdv(secret, corps):
    t = int(time.time())
    hexa = hmac.new(secret.encode('utf-8'), f'{t}.'.encode('utf-8') + corps,
                    hashlib.sha256).hexdigest()
    return f't={t},v1={hexa}'


class WebhookEnregistreOuEchecTests(TestCase):
    def _cle_rdv(self):
        # Clé unique par test : le compteur de débit (cache) ne fuit jamais.
        if not hasattr(self, '_cle'):
            self._cle = f'k79-{uuid.uuid4().hex[:8]}'
        return self._cle

    def setUp(self):
        self.company = Company.objects.create(nom='AACQ79', slug='aacq79')
        reglages = override_settings(
            WEBSITE_LEAD_WEBHOOK_SECRET=SECRET_SITE,
            WEBSITE_LEADS_COMPANY_ID=self.company.pk,
            META_LEAD_ADS_APP_SECRET=APP_SECRET,
            META_LEAD_ADS_ACCESS_TOKEN='aacq79-token',
            META_LEAD_ADS_COMPANY_ID=self.company.pk,
            SITE_RDV_CLES=f'{self._cle_rdv()}:aacq79:{SECRET_RDV}')
        reglages.enable()
        self.addCleanup(reglages.disable)
        # Une panne interne doit donner un non-2xx, pas lever dans le test.
        self.http = Client(raise_request_exception=False)

    def _assert_durable(self, resp, avant, *, erreur=False):
        """2xx ⇒ une ligne brute durable (erreur consignée si demandée)."""
        if not 200 <= resp.status_code < 300:
            return None
        lignes = WebsiteLeadPayload.objects.filter(
            company=self.company).order_by('pk')
        self.assertGreater(lignes.count(), avant,
                           f'2xx sans ligne durable : {resp.content!r}')
        ligne = lignes.last()
        self.assertIsNotNone(ligne.payload)
        if erreur:
            ligne.refresh_from_db()
            self.assertTrue(ligne.error, '2xx sur panne sans erreur consignée')
        return ligne

    # ── Énumération : aucune vue publique de lead hors garde ───────────────
    def test_toutes_les_routes_webhook_sont_classees(self):
        routes = [(r, n, m) for r, n, m in _routes_webhook()
                  if m.startswith(('apps.crm', 'apps.adsengine'))]
        self.assertTrue(routes)
        inconnues = sorted({n for _r, n, _m in routes
                            if n not in COUVERTES and n not in HORS_GARDE})
        self.assertEqual(
            inconnues, [],
            "Webhook public non couvert par la garde AACQ79 : "
            f"{inconnues} — ajoutez-le à COUVERTES (avec son test) ou à "
            "HORS_GARDE (avec sa raison).")
        for nom, test in COUVERTES.items():
            self.assertTrue(hasattr(self, test), f'{nom} : test {test} absent')

    # ── Site web ────────────────────────────────────────────────────────────
    def _post_site(self, data):
        return self.http.post(
            reverse('website-lead-webhook'), data=json.dumps(data),
            content_type='application/json', HTTP_X_WEBHOOK_SECRET=SECRET_SITE)

    def test_site_web(self):
        # (a) panne interne du mapping → 2xx seulement avec la ligne + erreur.
        avant = WebsiteLeadPayload.objects.count()
        with mock.patch('apps.crm.webhooks._map_and_link_lead',
                        side_effect=RuntimeError('panne transitoire')):
            resp = self._post_site({'fullName': 'Panne', 'consent': True,
                                    'phoneE164': '+212600790001'})
        ligne = self._assert_durable(resp, avant, erreur=True)
        self.assertIsNotNone(ligne)
        self.assertIn('panne transitoire', ligne.error)
        # (b) livraison dédupliquée → la seconde réponse a aussi sa ligne.
        corps = {'fullName': 'Dédup', 'consent': True,
                 'phoneE164': '+212600790002'}
        with mock.patch(APPLY_ASYNC):
            self._post_site(corps)
            avant = WebsiteLeadPayload.objects.count()
            resp = self._post_site(corps)
        self.assertIsNotNone(self._assert_durable(resp, avant))
        # (c) ping d'engagement sans lead → 2xx avec sa ligne.
        avant = WebsiteLeadPayload.objects.count()
        resp = self._post_site({'qualified': False,
                                'event_type': 'proposal_first_view',
                                'phoneE164': '+212600790003'})
        self.assertIsNotNone(self._assert_durable(resp, avant))

    # ── Meta Lead Ads ───────────────────────────────────────────────────────
    def _post_meta(self, leadgen_id):
        body = json.dumps({'entry': [{'changes': [{
            'field': 'leadgen',
            'value': {'leadgen_id': leadgen_id, 'ad_id': '', 'adgroup_id': '',
                      'form_id': ''}}]}]}).encode('utf-8')
        return self.http.post(
            reverse('meta-lead-ads-webhook'), data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=_sign_hub(APP_SECRET, body))

    def test_meta_lead_ads(self):
        # (a) panne de récupération Graph → 2xx avec ligne + erreur.
        avant = WebsiteLeadPayload.objects.count()
        with mock.patch('apps.crm.webhooks.fetch_meta_lead_data',
                        side_effect=RuntimeError('Graph injoignable')):
            resp = self._post_meta('7901')
        ligne = self._assert_durable(resp, avant, erreur=True)
        self.assertIsNotNone(ligne)
        # (b) même leadgen re-livré → chaque 2xx a sa ligne brute.
        donnees = {'field_data': [
            {'name': 'full_name', 'values': ['Meta Dédup']},
            {'name': 'phone_number', 'values': ['+212600790004']}]}
        with mock.patch('apps.crm.webhooks.fetch_meta_lead_data',
                        return_value=donnees), mock.patch(APPLY_ASYNC):
            self._post_meta('7902')
            avant = WebsiteLeadPayload.objects.count()
            resp = self._post_meta('7902')
        self.assertIsNotNone(self._assert_durable(resp, avant))

    # ── Demande de rendez-vous (YanBow) ────────────────────────────────────
    def _post_rdv(self, corps):
        brut = json.dumps(corps).encode('utf-8')
        return self.http.post(
            reverse('demande-rdv-webhook'), data=brut,
            content_type='application/json', HTTP_X_SITE_CLE=self._cle_rdv(),
            HTTP_X_SIGNATURE=_sign_rdv(SECRET_RDV, brut))

    def test_demande_rdv(self):
        contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'demande_rdv_site.json').read_text(encoding='utf-8'))
        corps = dict(contrat['corps'])
        corps['idempotency_key'] = str(uuid.uuid4())
        # (a) panne interne de la création → JAMAIS un 2xx, rien d'écrit.
        with mock.patch('apps.crm.webhooks._rdv_creer_lead',
                        side_effect=RuntimeError('panne transitoire')):
            resp = self._post_rdv(corps)
        self.assertFalse(200 <= resp.status_code < 300, resp.status_code)
        # (b) livraison puis re-livraison : chaque 2xx a son lead durable.
        for _ in range(2):
            resp = self._post_rdv(corps)
            self.assertTrue(200 <= resp.status_code < 300, resp.content)
            lead_id = resp.json()['id']
            self.assertTrue(Lead.all_objects.filter(
                pk=lead_id, company=self.company).exists())
