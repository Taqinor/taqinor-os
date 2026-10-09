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
        'CF_CONNECTING_IP_TRUSTED', 'DJANGO_SETTINGS_MODULE')

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
