"""ADEP36 — ``WHATSAPP_ENABLED`` (booléen strict) et ``WHATSAPP_ACCESS_TOKEN``
déclarés dans ``settings/base.py`` (C-ADEP-004, D-ADEP-3).

Avant : ``views_whatsapp_bsp._whatsapp_actif()`` lisait les deux clés via
``getattr(settings, …)`` mais aucun fichier de réglages ne les déclarait —
posées dans l'environnement, ``_whatsapp_actif()`` restait ``False``. On charge
``erp_agentique.settings.dev`` dans un SOUS-PROCESSUS avec un environnement
imposé et on appelle la fonction elle-même.

(Fichier frère ``tests_*.py`` et non ``tests/…`` : l'app porte déjà un module
``tests.py`` qu'un paquet ``tests/`` masquerait.)

Run :
    python manage.py test apps.notifications.tests_adep36_whatsapp_reglages -v2
"""
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE = Path(__file__).resolve().parents[2]
CLES = ('WHATSAPP_ENABLED', 'WHATSAPP_ACCESS_TOKEN', 'DJANGO_SETTINGS_MODULE')

_SCRIPT = r"""
from apps.notifications.views_whatsapp_bsp import _whatsapp_actif
print('ACTIF=' + str(_whatsapp_actif()))
"""


def _actif(env_impose):
    env = {k: v for k, v in os.environ.items() if k not in CLES}
    env['DJANGO_SETTINGS_MODULE'] = 'erp_agentique.settings.dev'
    env.update(env_impose)
    out = subprocess.run(
        [sys.executable, '-c', _SCRIPT], cwd=str(DJANGO_CORE), env=env,
        capture_output=True, text=True, timeout=180)
    for ligne in out.stdout.splitlines():
        if ligne.startswith('ACTIF='):
            return ligne[len('ACTIF='):] == 'True'
    raise AssertionError(f'réglages non chargés : {out.stderr[-2000:]}')


class WhatsappReglagesDeclaresTests(SimpleTestCase):
    def test_env_pose_active(self):
        for drapeau in ('1', 'true', 'True'):
            with self.subTest(drapeau=drapeau):
                self.assertTrue(_actif({'WHATSAPP_ENABLED': drapeau,
                                        'WHATSAPP_ACCESS_TOKEN': 'jeton'}))

    def test_absentes_inactif(self):
        self.assertFalse(_actif({}))

    def test_sans_jeton_inactif(self):
        self.assertFalse(_actif({'WHATSAPP_ENABLED': '1'}))

    def test_booleen_strict(self):
        for drapeau in ('0', 'false', 'yes', 'on', ''):
            with self.subTest(drapeau=drapeau):
                self.assertFalse(_actif({'WHATSAPP_ENABLED': drapeau,
                                         'WHATSAPP_ACCESS_TOKEN': 'jeton'}))
