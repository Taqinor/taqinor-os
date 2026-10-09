"""AFAC22 — ``PUBLIC_BASE_URL`` est un réglage DÉCLARÉ, lu de l'environnement.

Avant AFAC22 aucun ``settings/*.py`` ne le déclarait : les 4 lecteurs
``getattr(settings, 'PUBLIC_BASE_URL', '')`` (encaissements, cycle de vie,
WhatsApp) voyaient toujours ``''`` même variable posée dans le ``.env``.

Sous-processus ``python -c`` avec le vrai ``DJANGO_SETTINGS_MODULE`` et un
environnement imposé, aucun mock.

Run :
    python manage.py test apps.facturation.tests.test_afac_public_base_url -v2
"""
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE = Path(__file__).resolve().parents[3]

_SCRIPT = (
    "import django; django.setup(); "
    "from django.conf import settings; "
    "print('PBU=' + repr(getattr(settings, 'PUBLIC_BASE_URL', None)))"
)


def _valeur(env_pbu):
    env = {k: v for k, v in os.environ.items() if k != 'PUBLIC_BASE_URL'}
    env.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.dev')
    if env_pbu is not None:
        env['PUBLIC_BASE_URL'] = env_pbu
    out = subprocess.run(
        [sys.executable, '-c', _SCRIPT], cwd=str(DJANGO_CORE), env=env,
        capture_output=True, text=True, timeout=180)
    for ligne in out.stdout.splitlines():
        if ligne.startswith('PBU='):
            return ligne[len('PBU='):]
    raise AssertionError(f'réglages non chargés : {out.stderr[-2000:]}')


class PublicBaseUrlReglageTests(SimpleTestCase):
    def test_reglage_lu_de_l_environnement(self):
        self.assertEqual(_valeur('https://api.taqinor.ma'),
                         repr('https://api.taqinor.ma'))

    def test_absent_vide(self):
        self.assertEqual(_valeur(None), repr(''))
