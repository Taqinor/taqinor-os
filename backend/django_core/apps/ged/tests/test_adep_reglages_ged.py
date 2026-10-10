"""ADEP37 — ESIGN_*, GED_OFFICE_URL et GED_PADES_* sont déclarés dans
``settings/base.py`` et lus de l'environnement (C-ADEP-004, D-ADEP-3).

Run :
    python manage.py test apps.ged.tests.test_adep_reglages_ged -v2
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE = Path(__file__).resolve().parents[3]
CLES = ('ESIGN_ENABLED', 'ESIGN_PROVIDER', 'GED_OFFICE_URL',
        'GED_PADES_CERT_PATH', 'GED_PADES_KEY_PATH')

_SCRIPT = r"""
import json
import django
django.setup()
from django.conf import settings
from apps.ged import services
print('RESULTAT=' + json.dumps({
    'esign': services.esign_active(),
    'office': services.office_edit_active(),
    'provider': services.esign_provider_name(),
    'pades': [getattr(settings, 'GED_PADES_CERT_PATH', 'ABSENTE'),
              getattr(settings, 'GED_PADES_KEY_PATH', 'ABSENTE')],
}))
"""


def _charger(env_impose):
    env = {k: v for k, v in os.environ.items() if k not in CLES}
    env['DJANGO_SETTINGS_MODULE'] = 'erp_agentique.settings.dev'
    env.update(env_impose)
    out = subprocess.run(
        [sys.executable, '-c', _SCRIPT], cwd=str(DJANGO_CORE), env=env,
        capture_output=True, text=True, timeout=180)
    for ligne in out.stdout.splitlines():
        if ligne.startswith('RESULTAT='):
            return json.loads(ligne[len('RESULTAT='):])
    raise AssertionError(f'réglages non chargés : {out.stderr[-2000:]}')


class ReglagesGedEnvTests(SimpleTestCase):
    def test_env_pose_active_les_deux_fonctions(self):
        res = _charger({
            'ESIGN_ENABLED': '1', 'ESIGN_PROVIDER': 'yousign',
            'GED_OFFICE_URL': 'https://office.example',
            'GED_PADES_CERT_PATH': '/etc/c.pem',
            'GED_PADES_KEY_PATH': '/etc/k.pem'})
        self.assertTrue(res['esign'])
        self.assertTrue(res['office'])
        self.assertEqual(res['provider'], 'yousign')
        self.assertEqual(res['pades'], ['/etc/c.pem', '/etc/k.pem'])

    def test_env_absent_comme_avant(self):
        res = _charger({})
        self.assertFalse(res['esign'])
        self.assertFalse(res['office'])
        self.assertEqual(res['provider'], 'aucun')
        self.assertEqual(res['pades'], ['', ''])

    def test_booleen_strict(self):
        self.assertFalse(_charger({'ESIGN_ENABLED': '0'})['esign'])
        self.assertTrue(_charger({'ESIGN_ENABLED': 'true'})['esign'])
