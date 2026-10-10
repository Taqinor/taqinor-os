"""ADEP39 (C-ADEP-004) — ``PAYMENT_PROVIDER`` est un réglage DÉCLARÉ, lu de
l'environnement.

Avant ADEP39 aucun ``settings/*.py`` ne le déclarait : la vue de paiement
public (``apps/ventes/public/paiement_views.py``, lecture
``getattr(settings, 'PAYMENT_PROVIDER', '')``) voyait toujours ``''`` même
variable posée dans l'environnement — le lien carte ne s'affichait jamais.

Sous-processus ``python -c`` avec le vrai ``DJANGO_SETTINGS_MODULE`` et un
environnement imposé, aucun mock. Test-du-test : retirer la ligne de
``settings/base.py`` ⇒ ``test_reglage_lu_de_l_environnement`` échoue.

Run :
    python manage.py test apps.facturation.tests.test_adep_payment_provider -v2
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
    "print('PSP=' + repr(getattr(settings, 'PAYMENT_PROVIDER', None)))"
)


def _valeur(env_psp):
    env = {k: v for k, v in os.environ.items() if k != 'PAYMENT_PROVIDER'}
    env.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.dev')
    if env_psp is not None:
        env['PAYMENT_PROVIDER'] = env_psp
    out = subprocess.run(
        [sys.executable, '-c', _SCRIPT], cwd=str(DJANGO_CORE), env=env,
        capture_output=True, text=True, timeout=180)
    for ligne in out.stdout.splitlines():
        if ligne.startswith('PSP='):
            return ligne[len('PSP='):]
    raise AssertionError(f'réglages non chargés : {out.stderr[-2000:]}')


class PaymentProviderReglageTests(SimpleTestCase):
    def test_reglage_lu_de_l_environnement(self):
        self.assertEqual(_valeur('cmi'), repr('cmi'))

    def test_absent_defaut_actuel_vide(self):
        self.assertEqual(_valeur(None), repr(''))
