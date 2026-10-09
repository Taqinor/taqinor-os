"""ADEP35 — l'écran santé Publicité et le webhook WhatsApp Cloud lisent LA MÊME
source (``settings``) pour ``WHATSAPP_CLOUD_VERIFY_TOKEN``,
``WHATSAPP_CLOUD_APP_SECRET`` et ``WHATSAPP_CLOUD_COMPANY_ID``, déclarées dans
``settings/base.py`` (C-ADEP-004, D-ADEP-3).

Avant : ``audit.pending_activation_loops`` lisait ``os.environ`` (boucle
« active ») tandis que le webhook lisait ``settings`` où les clés n'étaient
déclarées nulle part → le GET de vérification Meta répondait 404
« Non configuré. » alors que l'écran affichait « actif ».

Run :
    python manage.py test apps.adsengine.tests.test_adep_ctwa_reglages -v2
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.adsengine import audit
from apps.adsengine.whatsapp_webhook import WhatsAppCloudWebhookView

DJANGO_CORE = Path(__file__).resolve().parents[3]
CLES = ('WHATSAPP_CLOUD_VERIFY_TOKEN', 'WHATSAPP_CLOUD_APP_SECRET',
        'WHATSAPP_CLOUD_COMPANY_ID')
POSEES = {'WHATSAPP_CLOUD_VERIFY_TOKEN': 'vt-adep35',
          'WHATSAPP_CLOUD_APP_SECRET': 'sec-adep35',
          'WHATSAPP_CLOUD_COMPANY_ID': '1'}
VIDES = {k: '' for k in CLES}


def _env_sans_cles():
    return {k: v for k, v in os.environ.items() if k not in CLES}


def _boucle_active():
    loops = {lp['id']: lp for lp in audit.pending_activation_loops()}
    return loops['whatsapp_cloud_ctwa']['actif']


def _get_verification():
    requete = RequestFactory().get('/api/django/adsengine/whatsapp/webhook/', {
        'hub.mode': 'subscribe',
        'hub.verify_token': 'vt-adep35',
        'hub.challenge': '4242',
    })
    return WhatsAppCloudWebhookView.as_view()(requete)


class EcranEtWebhookCoherentsTests(SimpleTestCase):
    def test_ecran_et_webhook_coherents(self):
        # Réglages posés, environnement VIDE : l'écran suit les réglages.
        with mock.patch.dict(os.environ, _env_sans_cles(), clear=True), \
                override_settings(**POSEES):
            reponse = _get_verification()
            self.assertEqual(reponse.status_code, 200)
            self.assertEqual(reponse.content, b'4242')
            self.assertTrue(_boucle_active())
        # Environnement posé, réglages VIDES : le webhook répond 404 ⇒
        # l'écran DOIT dire « inactif » (même source).
        env = dict(_env_sans_cles(), **POSEES)
        with mock.patch.dict(os.environ, env, clear=True), \
                override_settings(**VIDES):
            self.assertEqual(_get_verification().status_code, 404)
            self.assertFalse(_boucle_active())

    def test_actif_implique_get_200(self):
        # Sans société cible, l'écran reste prudent (inactif, AACQ25) ;
        # quand il dit « actif », le GET Meta répond 200.
        for reglages in (POSEES, VIDES,
                         dict(POSEES, WHATSAPP_CLOUD_COMPANY_ID=''),
                         dict(POSEES, WHATSAPP_CLOUD_APP_SECRET='')):
            with self.subTest(reglages=reglages), \
                    override_settings(**reglages):
                if _boucle_active():
                    self.assertEqual(_get_verification().status_code, 200)


_SCRIPT = r"""
import json
from django.conf import settings
from apps.adsengine import whatsapp_webhook
print('RESULTAT=' + json.dumps({
    'cles': {k: getattr(settings, k, 'ABSENTE') for k in (
        'WHATSAPP_CLOUD_VERIFY_TOKEN', 'WHATSAPP_CLOUD_APP_SECRET',
        'WHATSAPP_CLOUD_COMPANY_ID')},
    'active': whatsapp_webhook.boucle_ctwa_active(),
}))
"""


def _charger(env_impose):
    env = _env_sans_cles()
    env['DJANGO_SETTINGS_MODULE'] = 'erp_agentique.settings.dev'
    env.update(env_impose)
    out = subprocess.run(
        [sys.executable, '-c', _SCRIPT], cwd=str(DJANGO_CORE), env=env,
        capture_output=True, text=True, timeout=180)
    for ligne in out.stdout.splitlines():
        if ligne.startswith('RESULTAT='):
            return json.loads(ligne[len('RESULTAT='):])
    raise AssertionError(f'réglages non chargés : {out.stderr[-2000:]}')


class EnvLuParSettingsTests(SimpleTestCase):
    def test_env_lu_par_settings(self):
        res = _charger(POSEES)
        self.assertEqual(res['cles'], POSEES)
        self.assertTrue(res['active'])

    def test_env_absent_inactif(self):
        res = _charger({})
        self.assertFalse(res['active'])
        self.assertEqual(res['cles']['WHATSAPP_CLOUD_VERIFY_TOKEN'], '')
        self.assertEqual(res['cles']['WHATSAPP_CLOUD_APP_SECRET'], '')
        self.assertIsNone(res['cles']['WHATSAPP_CLOUD_COMPANY_ID'])
