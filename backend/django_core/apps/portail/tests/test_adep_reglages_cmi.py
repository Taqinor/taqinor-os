"""ADEP38 — CMI_ENABLED et CMI_MERCHANT_KEY sont déclarés dans
``settings/base.py`` et lus de l'environnement : ``cmi_actif()`` les suit
(C-ADEP-004, D-ADEP-3).

Run :
    python manage.py test apps.portail.tests.test_adep_reglages_cmi -v2
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE = Path(__file__).resolve().parents[3]
CLES = ('CMI_ENABLED', 'CMI_MERCHANT_KEY')

_SCRIPT = r"""
import json
from apps.portail import services
print('RESULTAT=' + json.dumps({'actif': services.cmi_actif()}))
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


class ReglagesCmiEnvTests(SimpleTestCase):
    def test_env_pose_cmi_actif(self):
        res = _charger({'CMI_ENABLED': '1', 'CMI_MERCHANT_KEY': 'k'})
        self.assertTrue(res['actif'])

    def test_env_absent_faux_comme_avant(self):
        self.assertFalse(_charger({})['actif'])

    def test_sans_cle_marchande_faux(self):
        self.assertFalse(_charger({'CMI_ENABLED': '1'})['actif'])
