"""QJR414 (DÉCISION FONDATEUR DR3) — les deux webhooks entrants sont FAIL-CLOSED.

CE QUE LE ROUGE PROUVAIT. Les deux webhooks ne vérifiaient la signature HMAC
que **si** leur secret était posé, et TRAITAIENT le payload sinon :

    apps/crm/webhooks.py            ``if app_secret:`` … ``else: warning`` puis
                                    traitement (PUB26, « rétro-compatible »)
    apps/notifications/…_bsp.py     motif IDENTIQUE (« scaffold non sécurisé »)

``META_LEAD_ADS_APP_SECRET`` vaut ``''`` par défaut, ``WHATSAPP_BSP_APP_SECRET``
aussi, et **aucun des deux n'était documenté dans ``.env.example``** : le
déploiement par défaut était donc OUVERT *et* SILENCIEUX — n'importe qui
pouvait poster de faux leads.

DR3 TRANCHE : secret absent ⇒ la requête est **refusée** (403), jamais traitée ;
``.env.example`` documente les deux variables ; un avertissement bruyant au
démarrage signale tant qu'elles manquent (contrôles système ``crm.W010`` /
``notifications.W010``, jamais dans les réglages — QJR423 est la seule tâche
qui touche ``settings``).

CONSÉQUENCE VOULUE ET ACCEPTÉE : la synchronisation entrante reste EN PAUSE
jusqu'à ce que Reda pose les secrets au deploy. Ce n'est pas une panne.
"""
import hashlib
import hmac
import json
from unittest import mock

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from apps.crm.models import Lead


_APP_SECRET = 'qjr414-app-secret'


def _signer(secret, body: bytes) -> str:
    return 'sha256=' + hmac.new(
        secret.encode(), body, hashlib.sha256).hexdigest()


def _payload_meta(leadgen_id='qjr414-1'):
    return {'entry': [{'changes': [{
        'field': 'leadgen',
        'value': {'leadgen_id': leadgen_id, 'ad_id': '', 'adgroup_id': '',
                  'form_id': ''},
    }]}]}


def _lead_data():
    return {'field_data': [
        {'name': 'full_name', 'values': ['Client QJR414']},
        {'name': 'phone_number', 'values': ['+212661000414']},
    ]}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Webhook Meta Lead Ads (apps/crm/webhooks.py)
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(META_LEAD_ADS_ACCESS_TOKEN='tok-414')
class MetaLeadAdsFailClosedTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR414 Meta', slug='qjr414-meta')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload, *, signature=None):
        body = json.dumps(payload).encode('utf-8')
        entetes = ({'HTTP_X_HUB_SIGNATURE_256': signature}
                   if signature is not None else {})
        return self.client.post(
            self.url, data=body, content_type='application/json', **entetes)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    @override_settings(META_LEAD_ADS_APP_SECRET='')
    def test_post_non_signe_sans_secret_est_refuse_sans_effet_de_bord(
            self, fetch_mock):
        """ROUGE avant QJR414 : le POST était ACCEPTÉ et créait le lead."""
        fetch_mock.return_value = _lead_data()
        reponse = self._post(_payload_meta())
        self.assertEqual(reponse.status_code, 403)
        # Aucun effet de bord : aucun lead, et pas même un appel Graph API.
        self.assertEqual(Lead.objects.count(), 0)
        fetch_mock.assert_not_called()

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    @override_settings(META_LEAD_ADS_APP_SECRET=_APP_SECRET)
    def test_post_non_signe_avec_secret_reste_refuse(self, fetch_mock):
        fetch_mock.return_value = _lead_data()
        reponse = self._post(_payload_meta())
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(Lead.objects.count(), 0)
        fetch_mock.assert_not_called()

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    @override_settings(META_LEAD_ADS_APP_SECRET=_APP_SECRET)
    def test_post_correctement_signe_est_traite_comme_avant(self, fetch_mock):
        """Second test du `Done` : le chemin nominal est INCHANGÉ."""
        fetch_mock.return_value = _lead_data()
        payload = _payload_meta(leadgen_id='qjr414-ok')
        body = json.dumps(payload).encode('utf-8')
        reponse = self.client.post(
            self.url, data=body, content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=_signer(_APP_SECRET, body))
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)

    @override_settings(META_LEAD_ADS_APP_SECRET=_APP_SECRET)
    def test_signature_invalide_reste_refusee(self):
        reponse = self._post(_payload_meta(), signature='sha256=' + '0' * 64)
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(Lead.objects.count(), 0)

    @override_settings(META_LEAD_ADS_VERIFY_TOKEN='verify-414',
                       META_LEAD_ADS_APP_SECRET='')
    def test_la_poignee_de_main_get_n_est_pas_touchee(self):
        """La garde DR3 vit dans la branche POST : le GET est inchangé."""
        reponse = self.client.get(self.url, {
            'hub.mode': 'subscribe', 'hub.verify_token': 'verify-414',
            'hub.challenge': 'chal-414'})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.content.decode(), 'chal-414')


# ═══════════════════════════════════════════════════════════════════════════
# 2. Webhook BSP WhatsApp (apps/notifications/views_whatsapp_bsp.py)
# ═══════════════════════════════════════════════════════════════════════════

class WhatsAppBspFailClosedTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def _post(self, secret_env, *, signature=None, corps=b'{"entry": []}'):
        from apps.notifications.views_whatsapp_bsp import (
            WhatsAppBspWebhookView,
        )
        entetes = ({'HTTP_X_HUB_SIGNATURE_256': signature}
                   if signature is not None else {})
        requete = self.factory.post(
            '/fake/webhook/', corps, content_type='application/json',
            **entetes)
        with mock.patch.dict('os.environ',
                             {'WHATSAPP_BSP_APP_SECRET': secret_env}):
            return WhatsAppBspWebhookView.as_view()(requete)

    def test_post_non_signe_sans_secret_est_refuse(self):
        """ROUGE avant QJR414 : le POST était ACCEPTÉ (200) avec un warning."""
        self.assertEqual(self._post('').status_code, 403)

    def test_post_non_signe_avec_secret_reste_refuse(self):
        self.assertEqual(self._post(_APP_SECRET).status_code, 403)

    def test_post_correctement_signe_est_traite_comme_avant(self):
        """Second test du `Done` : le chemin nominal est INCHANGÉ."""
        corps = b'{"entry": []}'
        reponse = self._post(
            _APP_SECRET, signature=_signer(_APP_SECRET, corps), corps=corps)
        self.assertEqual(reponse.status_code, 200)

    def test_aucun_statut_n_est_mis_a_jour_par_un_post_non_signe(self):
        """Aucun effet de bord : le log de message reste intact."""
        from apps.notifications.models import WhatsAppMessageLog

        company = Company.objects.create(
            nom='QJR414 BSP', slug='qjr414-bsp')
        log = WhatsAppMessageLog.objects.create(
            company=company, recipient='212600000414', body='Test',
            status=WhatsAppMessageLog.Status.SENT,
            provider=WhatsAppMessageLog.Provider.BSP,
            external_id='wamid.qjr414')
        corps = json.dumps({'entry': [{'changes': [{'value': {'statuses': [{
            'id': 'wamid.qjr414', 'status': 'delivered',
            'timestamp': '1719000000', 'recipient_id': '212600000414',
        }]}}]}]}).encode()
        self.assertEqual(self._post('', corps=corps).status_code, 403)
        log.refresh_from_db()
        self.assertEqual(log.status, WhatsAppMessageLog.Status.SENT)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Troisième test du `Done` : .env.example + avertissements de démarrage
# ═══════════════════════════════════════════════════════════════════════════

class DocumentationEtAvertissementsTests(TestCase):

    def test_les_deux_variables_sont_dans_env_example(self):
        from pathlib import Path

        # …/backend/django_core/apps/crm/tests/<ce fichier> → racine du dépôt.
        racine = Path(__file__).resolve().parents[5]
        contenu = (racine / '.env.example').read_text(encoding='utf-8')
        for variable in ('META_LEAD_ADS_APP_SECRET',
                         'WHATSAPP_BSP_APP_SECRET'):
            self.assertIn('%s=' % variable, contenu,
                          '%s absent de .env.example' % variable)

    @override_settings(META_LEAD_ADS_APP_SECRET='')
    def test_avertissement_crm_quand_le_secret_manque(self):
        from apps.crm.apps import _qjr414_meta_lead_ads_app_secret_check

        avertissements = _qjr414_meta_lead_ads_app_secret_check(None)
        self.assertEqual([a.id for a in avertissements], ['crm.W010'])

    @override_settings(META_LEAD_ADS_APP_SECRET=_APP_SECRET)
    def test_aucun_avertissement_crm_quand_le_secret_est_pose(self):
        from apps.crm.apps import _qjr414_meta_lead_ads_app_secret_check

        self.assertEqual(_qjr414_meta_lead_ads_app_secret_check(None), [])

    def test_avertissement_notifications_quand_le_secret_manque(self):
        from apps.notifications.apps import (
            _qjr414_whatsapp_bsp_app_secret_check,
        )

        with mock.patch.dict('os.environ',
                             {'WHATSAPP_BSP_APP_SECRET': ''}):
            avertissements = _qjr414_whatsapp_bsp_app_secret_check(None)
        self.assertEqual([a.id for a in avertissements],
                         ['notifications.W010'])

    def test_aucun_avertissement_notifications_quand_le_secret_est_pose(self):
        from apps.notifications.apps import (
            _qjr414_whatsapp_bsp_app_secret_check,
        )

        with mock.patch.dict('os.environ',
                             {'WHATSAPP_BSP_APP_SECRET': _APP_SECRET}):
            self.assertEqual(
                _qjr414_whatsapp_bsp_app_secret_check(None), [])
