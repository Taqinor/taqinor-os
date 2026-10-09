"""ADEP7 — seul le process WEB prend le rôle applicatif RLS.

Charge ``erp_agentique.settings.dev`` dans un SOUS-PROCESSUS avec un argv et
un environnement imposés (le choix du rôle se fait au chargement des
réglages, pur argv + env) et lit ``DATABASES['default']['USER']``.

Flag ON (``POSTGRES_RLS_ENABLED=1``, ``DB_APP_USER=app_rls``) :
gunicorn, uvicorn et ``manage.py runserver`` → app_rls ; workers/beat Celery
et toute commande ``manage.py`` (``audit_coherence``,
``publier_documents_meryem``, ``reset_demo_company``, ``migrate``…) → owner.
Flag OFF → owner partout.

Run :
    python manage.py test core.tests.test_adep_role_bdd_process -v2
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE = Path(__file__).resolve().parents[2]
OWNER = 'owner_adep7'
APP = 'app_rls'

_SCRIPT = """
import importlib, json, sys
sys.argv = json.loads(sys.argv[1])
m = importlib.import_module('erp_agentique.settings.dev')
print('DBUSER=' + m.DATABASES['default']['USER'])
"""


def _role(argv, flag=True):
    env = {k: v for k, v in os.environ.items()
           if k not in ('POSTGRES_RLS_ENABLED', 'DB_APP_USER', 'DB_USER',
                        'DJANGO_SETTINGS_MODULE', 'PGBOUNCER')}
    env['DB_USER'] = OWNER
    if flag:
        env['POSTGRES_RLS_ENABLED'] = '1'
        env['DB_APP_USER'] = APP
        env['DB_APP_PASSWORD'] = 'x'
    out = subprocess.run(
        [sys.executable, '-c', _SCRIPT, json.dumps(argv)],
        cwd=str(DJANGO_CORE), env=env, capture_output=True, text=True,
        timeout=180)
    for ligne in out.stdout.splitlines():
        if ligne.startswith('DBUSER='):
            return ligne[len('DBUSER='):]
    raise AssertionError(f'réglages non chargés : {out.stderr[-2000:]}')


CELERY_WORKER = ['/usr/local/bin/celery', '-A', 'erp_agentique', 'worker',
                 '-l', 'info']
CELERY_BEAT = ['/usr/local/bin/celery', '-A', 'erp_agentique', 'beat']
GUNICORN = ['/usr/local/bin/gunicorn', 'erp_agentique.wsgi:application']
UVICORN = ['/usr/local/bin/uvicorn', 'erp_agentique.asgi:application']
RUNSERVER = ['manage.py', 'runserver']
COMMANDES = (['manage.py', 'audit_coherence', '--json'],
             ['manage.py', 'publier_documents_meryem'],
             ['manage.py', 'reset_demo_company'],
             ['manage.py', 'migrate'])


class RoleBddParProcessTests(SimpleTestCase):
    def test_celery_worker_reste_owner(self):
        self.assertEqual(_role(CELERY_WORKER), OWNER)
        self.assertEqual(_role(CELERY_BEAT), OWNER)

    def test_commande_systeme_reste_owner(self):
        for argv in COMMANDES:
            with self.subTest(argv=argv):
                self.assertEqual(_role(argv), OWNER)

    def test_gunicorn_prend_app_rls(self):
        for argv in (GUNICORN, UVICORN, RUNSERVER):
            with self.subTest(argv=argv):
                self.assertEqual(_role(argv), APP)

    def test_flag_off_owner_partout(self):
        for argv in (GUNICORN, CELERY_WORKER, RUNSERVER) + COMMANDES:
            with self.subTest(argv=argv):
                self.assertEqual(_role(argv, flag=False), OWNER)

    def test_relance_meme_role(self):
        self.assertEqual(_role(GUNICORN), _role(GUNICORN))
