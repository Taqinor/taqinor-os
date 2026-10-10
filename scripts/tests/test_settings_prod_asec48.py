"""Tests ASEC48 — `settings.prod` prouvé pour la chaîne réelle Caddy → nginx → Django.

Un interpréteur NEUF charge `erp_agentique.settings.prod` avec un environnement
type production (valeurs FACTICES, aucun secret réel), lance les contrôles
système `--deploy`, puis rejoue des requêtes via le client de test Django
(`X-Forwarded-Proto: https` comme nginx le relaie depuis Caddy, ASEC52). Aucune
base de données ni Redis : Postgres/Redis pointent sur un port fermé, et rien
ici ne doit les toucher (une requête qui le ferait échouerait le test).

Le procédé et chaque avertissement accepté sont documentés dans
`docs/production.md` (section « Bascule vers settings.prod »).

Run (image backend, qui porte Django et WeasyPrint) :
    python -m unittest scripts.tests.test_settings_prod_asec48 -v
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DJANGO_CORE = RACINE / 'backend' / 'django_core'
MARQUEUR = 'RAPPORT_ASEC48='
HOTE = 'api.taqinor.ma'

#: Avertissements `check --deploy` ACCEPTÉS (documentés dans docs/production.md) :
#: fonctionnalités à clé, inertes tant que la clé n'est pas posée sur le serveur.
AVERTISSEMENTS_ACCEPTES = frozenset({
    'crm.W010',            # META_LEAD_ADS_APP_SECRET absent : webhook Meta Lead Ads fail-closed
    'notifications.W010',  # WHATSAPP_BSP_APP_SECRET absent : webhook BSP fail-closed
})

#: Environnement type production — valeurs factices, jamais un secret réel.
ENV_PROD = {
    'DJANGO_SETTINGS_MODULE': 'erp_agentique.settings.prod',
    'DJANGO_DEBUG': 'False',
    'DJANGO_SECRET_KEY': 'factice-asec48-0123456789abcdefghijklmnopqrstuvwxyzABCDEF',
    'DJANGO_ALLOWED_HOSTS': f'{HOTE}, 178-105-192-116.sslip.io',
    'CORS_ALLOWED_ORIGINS': 'https://taqinor.ma,https://www.taqinor.ma',
    'CSRF_TRUSTED_ORIGINS': f'https://{HOTE},https://178-105-192-116.sslip.io',
    'MINIO_ROOT_PASSWORD': 'factice-asec48-minio-0123456789',
    'TENANT_SIGNUP_ENABLED': '0',
    'ODOO_COMPANY_ID': '1',
    'DB_HOST': '127.0.0.1', 'DB_PORT': '9',
    'REDIS_HOST': '127.0.0.1', 'REDIS_PORT': '9',
    'PYTHONIOENCODING': 'utf-8',
}

#: Variables qui, héritées du shell ou du CI, fausseraient l'environnement prod.
A_RETIRER = ('PYTEST_CURRENT_TEST', 'NUM_PROXIES', 'AUTH_COOKIE_SECURE',
             'DJANGO_ENV', 'ENVIRONMENT', 'APP_ENV', 'ENV', 'LOG_FORMAT',
             'EMAIL_BACKEND', 'BREVO_API_KEY', 'SENDGRID_API_KEY',
             'POSTGRES_RLS_ENABLED', 'DJANGO_ADMIN_URL',
             'META_LEAD_ADS_APP_SECRET', 'WHATSAPP_BSP_APP_SECRET', 'ESIGN_OTP_ENABLED')

SONDE = r'''
import json, sys
import django
django.setup()
from django.conf import settings
from django.core import checks
from django.test import Client, RequestFactory
from authentication.views import _cookie_secure
from core.checks import environnement_de_production, verifier_reglages_production
from core.throttling import ip_de_requete

HOTE = sys.argv[1]
rf = RequestFactory()
https = rf.get('/', HTTP_HOST=HOTE, HTTP_X_FORWARDED_PROTO='https')
http = rf.get('/', HTTP_HOST=HOTE)
client = Client()


def reponse(chemin, proto=None):
    extra = {'HTTP_HOST': HOTE}
    if proto:
        extra['HTTP_X_FORWARDED_PROTO'] = proto
    r = client.get(chemin, **extra)
    return {'statut': r.status_code, 'location': r.get('Location', ''),
            'hsts': r.get('Strict-Transport-Security', ''),
            'corps': r.content[:4000].decode('utf-8', 'replace')}


xff = rf.get('/', HTTP_X_FORWARDED_FOR='6.6.6.6, 203.0.113.7', REMOTE_ADDR='172.18.0.5')
rapport = {
    'checks': [[m.id, m.level, m.msg[:300]] for m in
               checks.run_checks(include_deployment_checks=True)],
    'qjr423': [m.id for m in verifier_reglages_production()],
    'prod': environnement_de_production(),
    'debug': settings.DEBUG,
    'allowed_hosts': list(settings.ALLOWED_HOSTS),
    'cors_all': settings.CORS_ALLOW_ALL_ORIGINS,
    'cors': list(settings.CORS_ALLOWED_ORIGINS),
    'csrf': list(settings.CSRF_TRUSTED_ORIGINS),
    'session_secure': settings.SESSION_COOKIE_SECURE,
    'csrf_secure': settings.CSRF_COOKIE_SECURE,
    'hsts_seconds': settings.SECURE_HSTS_SECONDS,
    'ssl_redirect': settings.SECURE_SSL_REDIRECT,
    'num_proxies': [settings.NUM_PROXIES, settings.REST_FRAMEWORK.get('NUM_PROXIES')],
    'ip_visiteur': ip_de_requete(xff),
    'is_secure': [https.is_secure(), http.is_secure()],
    'jwt_secure': [_cookie_secure(https), _cookie_secure(http)],
    'sante_http': reponse('/api/django/core/health/live/'),
    'sante_https': reponse('/api/django/core/health/live/', 'https'),
    'api_https': reponse('/api/django/ventes/devis/', 'https'),
    'api_http': reponse('/api/django/ventes/devis/'),
    'page_404': reponse('/page-inexistante-asec48/', 'https'),
}
print('RAPPORT_ASEC48=' + json.dumps(rapport))
'''


def executer_sonde():
    """Lance la sonde dans un interpréteur neuf ; renvoie le rapport décodé."""
    env = {k: v for k, v in os.environ.items()
           if k not in A_RETIRER and k not in ENV_PROD}
    env.update(ENV_PROD)
    acheve = subprocess.run(
        [sys.executable, '-c', SONDE, HOTE], cwd=str(DJANGO_CORE), env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=600)
    for ligne in reversed((acheve.stdout or '').splitlines()):
        if ligne.startswith(MARQUEUR):
            return json.loads(ligne[len(MARQUEUR):])
    raise AssertionError(
        f'la sonde settings.prod a échoué (code {acheve.returncode}) :\n'
        f'{(acheve.stdout or "")[-3000:]}\n{(acheve.stderr or "")[-5000:]}')


class SettingsProdAsec48(unittest.TestCase):
    rapport = None

    @classmethod
    def setUpClass(cls):
        cls.rapport = executer_sonde()

    def test_settings_prod_charge_et_durci(self):
        r = self.rapport
        self.assertTrue(r['prod'], 'environnement_de_production() doit être vrai')
        self.assertFalse(r['debug'])
        self.assertEqual(r['allowed_hosts'], [HOTE, '178-105-192-116.sslip.io'])
        self.assertFalse(r['cors_all'])
        self.assertEqual(r['cors'], ['https://taqinor.ma', 'https://www.taqinor.ma'])
        self.assertEqual(r['csrf'], [
            f'https://{HOTE}', 'https://178-105-192-116.sslip.io',
            'https://taqinor.ma', 'https://www.taqinor.ma'])
        self.assertTrue(r['session_secure'])
        self.assertTrue(r['csrf_secure'])
        self.assertGreater(r['hsts_seconds'], 0)
        self.assertTrue(r['ssl_redirect'])
        self.assertEqual(r['qjr423'], [], 'QJR423 (core/checks.py) doit être silencieux')
        bloquants = [c for c in r['checks'] if c[1] >= 40]  # ERROR (40) / CRITICAL (50)
        self.assertEqual(bloquants, [], 'check --deploy ne doit lever aucune erreur')
        inattendus = [c for c in r['checks'] if c[0] not in AVERTISSEMENTS_ACCEPTES]
        self.assertEqual(
            inattendus, [],
            'avertissement --deploy non documenté : le corriger, ou l\'ajouter à '
            'AVERTISSEMENTS_ACCEPTES ET à docs/production.md')

    def test_is_secure_derriere_proxy(self):
        r = self.rapport
        self.assertEqual(r['is_secure'], [True, False],
                         'X-Forwarded-Proto: https (relayé par nginx) ⇒ is_secure()')
        self.assertEqual(r['jwt_secure'], [True, True], 'cookies JWT toujours Secure en prod')
        self.assertEqual(r['num_proxies'], [1, 1])
        self.assertEqual(r['ip_visiteur'], '203.0.113.7',
                         'NUM_PROXIES=1 : le saut ajouté par nginx, jamais celui de l\'appelant')
        self.assertEqual(r['api_https']['statut'], 401, r['api_https'])
        self.assertIn('max-age=', r['sante_https']['hsts'])
        self.assertEqual(r['api_http']['statut'], 301)
        self.assertEqual(r['api_http']['location'], f'https://{HOTE}/api/django/ventes/devis/')
        self.assertEqual(r['page_404']['statut'], 404)
        self.assertNotIn('URLconf', r['page_404']['corps'])

    def test_sante_sans_redirection(self):
        r = self.rapport
        for cle in ('sante_http', 'sante_https'):
            with self.subTest(sonde=cle):
                self.assertEqual(r[cle]['statut'], 200, r[cle])
                self.assertEqual(r[cle]['location'], '')


if __name__ == '__main__':
    unittest.main()
