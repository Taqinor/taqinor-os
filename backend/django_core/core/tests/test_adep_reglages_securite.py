"""ADEP32 — ``GEOIP_PATH``, ``OPENSEARCH_URL`` et ``CF_CONNECTING_IP_TRUSTED``
déclarés dans ``settings/base.py`` (C-ADEP-004, D-ADEP-3).

Avant : les trois clés étaient LUES (``getattr(settings, …)``) mais déclarées
dans AUCUN fichier de réglages — posées dans l'environnement, elles n'avaient
aucun effet. On charge ``erp_agentique.settings.dev`` dans un SOUS-PROCESSUS
avec un environnement imposé, puis on appelle LA fonction qui lit chaque clé :

* ``apps.identity.anomaly._geolocate`` ouvre la base GeoIP au chemin posé
  (``geoip2`` remplacé par un faux module qui note le chemin reçu) ;
* ``core.search_backend.OpenSearchBackend().url`` voit l'URL ;
* ``core.throttling.ip_de_requete`` n'honore ``CF-Connecting-IP`` que si la
  variable vaut ``1``/``true`` — toute autre valeur, ou absente, = comportement
  d'aujourd'hui (``REMOTE_ADDR``).

Run :
    python manage.py test core.tests.test_adep_reglages_securite -v2
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE = Path(__file__).resolve().parents[2]
CLES = ('GEOIP_PATH', 'GEOIP2_CITY_DB', 'OPENSEARCH_URL',
        'CF_CONNECTING_IP_TRUSTED', 'DJANGO_SETTINGS_MODULE',
        'WEBHOOK_AUTO_DISABLE_THRESHOLD', 'WEBHOOK_AUTO_DISABLE_WINDOW_HOURS',
        'VENTES_EXPORT_ASYNC_ROW_THRESHOLD', 'INBOUND_REPLY_EMAIL')

_SCRIPT = r"""
import json, sys, types
vus = []

class _Reader:
    def __init__(self, path):
        vus.append(path)
    def __enter__(self):
        raise RuntimeError('faux geoip2 : chemin noté, rien à lire')
    def __exit__(self, *a):
        return False

geoip2 = types.ModuleType('geoip2')
geoip2.database = types.ModuleType('geoip2.database')
geoip2.database.Reader = _Reader
sys.modules['geoip2'] = geoip2
sys.modules['geoip2.database'] = geoip2.database

from apps.identity import anomaly
from core import search_backend, throttling

anomaly._geolocate('8.8.8.8')

class _Req:
    META = {'HTTP_CF_CONNECTING_IP': '203.0.113.9', 'REMOTE_ADDR': '10.0.0.1'}

print('RESULTAT=' + json.dumps({
    'geoip': vus[0] if vus else None,
    'opensearch': search_backend.OpenSearchBackend().url,
    'ip': throttling.ip_de_requete(_Req()),
}))
"""


# ENF15 (ADEP20) — réglages lus par le code (`getattr(settings, 'X', repli)`) puis déclarés dans
# `settings/reglages_lus.py` : chaque déclaration porte EXACTEMENT le repli de son lecteur, et la
# variable d'environnement documentée atteint ce lecteur.
_SCRIPT_LUS = r"""
import json
import django
django.setup()
from django.conf import settings
from apps.adsengine import tasks
from apps.publicapi import oauth, webhook_health
from apps.ventes import email_service, exports, models as ventes_models

lus = ('ADSENGINE_GRAPH_EOL_ALERT_MONTHS', 'ADSENGINE_ROLLUP_AFTER_MONTHS', 'GEOIP2_CITY_DB',
       'PUBLIC_API_OAUTH_TOKEN_TTL', 'WEBHOOK_AUTO_DISABLE_THRESHOLD',
       'WEBHOOK_AUTO_DISABLE_WINDOW_HOURS', 'LOGIN_PLANCHER_ECHECS', 'LOGIN_PLANCHER_VERROU_MINUTES',
       'DEVIS_NUDGE_DAYS', 'INBOUND_REPLY_EMAIL', 'VENTES_EXPORT_ASYNC_ROW_THRESHOLD',
       'VENTES_COMPTA_ACCOUNT_CODES', 'VENTES_COMPTA_ACCOUNT_CODES_BY_COMPANY')
print('RESULTAT=' + json.dumps({
    'declares': {cle: getattr(settings, cle) for cle in lus},
    'replis': {
        'ADSENGINE_GRAPH_EOL_ALERT_MONTHS': tasks._DEFAULT_GRAPH_EOL_ALERT_MONTHS,
        'ADSENGINE_ROLLUP_AFTER_MONTHS': tasks._DEFAULT_ROLLUP_AFTER_MONTHS,
        'PUBLIC_API_OAUTH_TOKEN_TTL': oauth.DEFAULT_TOKEN_TTL_SECONDS,
        'WEBHOOK_AUTO_DISABLE_THRESHOLD': webhook_health.DEFAULT_AUTO_DISABLE_THRESHOLD,
        'WEBHOOK_AUTO_DISABLE_WINDOW_HOURS': webhook_health.DEFAULT_AUTO_DISABLE_WINDOW_HOURS,
        'DEVIS_NUDGE_DAYS': ventes_models.DEVIS_NUDGE_DEFAULT_DAYS,
    },
    'lecteurs': {
        'seuil': webhook_health._seuil(),
        'fenetre': webhook_health._fenetre_heures(),
        'export': exports.export_async_row_threshold(),
        'reply_to': email_service._reply_to_address(),
    },
}))
"""


def _charger(env_impose, script=_SCRIPT):
    env = {k: v for k, v in os.environ.items() if k not in CLES}
    env['DJANGO_SETTINGS_MODULE'] = 'erp_agentique.settings.dev'
    env.update(env_impose)
    out = subprocess.run(
        [sys.executable, '-c', script], cwd=str(DJANGO_CORE), env=env,
        capture_output=True, text=True, timeout=180)
    for ligne in out.stdout.splitlines():
        if ligne.startswith('RESULTAT='):
            return json.loads(ligne[len('RESULTAT='):])
    raise AssertionError(f'réglages non chargés : {out.stderr[-2000:]}')


class ReglagesSecuriteDeclaresTests(SimpleTestCase):
    def test_trois_cles_posees_vues_par_leur_lecteur(self):
        chemin = os.path.join(tempfile.gettempdir(), 'GeoLite2-City.mmdb')
        res = _charger({
            'GEOIP_PATH': chemin,
            'OPENSEARCH_URL': 'https://opensearch.exemple:9200',
            'CF_CONNECTING_IP_TRUSTED': '1',
        })
        self.assertEqual(res['geoip'], chemin)
        self.assertEqual(res['opensearch'], 'https://opensearch.exemple:9200')
        self.assertEqual(res['ip'], '203.0.113.9')

    def test_cf_true_accepte(self):
        res = _charger({'CF_CONNECTING_IP_TRUSTED': 'true'})
        self.assertEqual(res['ip'], '203.0.113.9')

    def test_cf_booleen_strict(self):
        for valeur in ('yes', '0', 'false', 'on', ''):
            with self.subTest(valeur=valeur):
                res = _charger({'CF_CONNECTING_IP_TRUSTED': valeur})
                self.assertEqual(res['ip'], '10.0.0.1')

    def test_cles_absentes_comportement_actuel(self):
        res = _charger({})
        self.assertIsNone(res['geoip'])
        self.assertEqual(res['opensearch'], '')
        self.assertEqual(res['ip'], '10.0.0.1')


class ReglagesLusDeclaresTests(SimpleTestCase):
    def test_declarations_egales_au_repli_du_lecteur(self):
        res = _charger({}, _SCRIPT_LUS)
        declares = res["declares"]
        for cle, repli in res["replis"].items():
            self.assertEqual(declares[cle], repli, cle)
        self.assertEqual(declares["LOGIN_PLANCHER_ECHECS"], 10)
        self.assertEqual(declares["LOGIN_PLANCHER_VERROU_MINUTES"], 15)
        self.assertEqual(declares["VENTES_EXPORT_ASYNC_ROW_THRESHOLD"], 2000)
        self.assertEqual(declares["GEOIP2_CITY_DB"], "")
        self.assertEqual(declares["INBOUND_REPLY_EMAIL"], "")
        self.assertEqual(declares["VENTES_COMPTA_ACCOUNT_CODES"], {})
        self.assertEqual(declares["VENTES_COMPTA_ACCOUNT_CODES_BY_COMPANY"], {})
        self.assertEqual(res["lecteurs"], {
            "seuil": 20, "fenetre": 24, "export": 2000, "reply_to": ""})

    def test_variables_d_environnement_atteignent_leur_lecteur(self):
        chemin = os.path.join(tempfile.gettempdir(), "GeoLite2-City.mmdb")
        res = _charger({
            "WEBHOOK_AUTO_DISABLE_THRESHOLD": "7",
            "WEBHOOK_AUTO_DISABLE_WINDOW_HOURS": "6",
            "VENTES_EXPORT_ASYNC_ROW_THRESHOLD": "500",
            "INBOUND_REPLY_EMAIL": "retour@exemple.ma",
            "GEOIP2_CITY_DB": chemin,
        }, _SCRIPT_LUS)
        self.assertEqual(res["lecteurs"], {
            "seuil": 7, "fenetre": 6, "export": 500,
            "reply_to": "retour@exemple.ma"})
        self.assertEqual(res["declares"]["GEOIP2_CITY_DB"], chemin)

    def test_seuil_zero_desactive_la_coupure_automatique(self):
        res = _charger({"WEBHOOK_AUTO_DISABLE_THRESHOLD": "0"}, _SCRIPT_LUS)
        self.assertEqual(res["lecteurs"]["seuil"], 0)
