"""NTAPI28 — SDK Python généré depuis l'OpenAPI.

Critère d'acceptation : « le SDK généré liste des leads et gère une pagination
sur ≥2 pages dans un test d'intégration local ». Ce test GÉNÈRE réellement le
client, l'ÉCRIT dans un dossier temporaire, l'IMPORTE, puis l'exécute contre un
transport simulé — c'est-à-dire qu'il exerce le code émis, pas une maquette de
ce que le générateur est censé produire.

Couvre en plus les deux comportements qui distinguent un vrai client d'un
`requests.get` : le respect de `Retry-After` sur 429 (jamais un backoff
inventé) et la lecture des en-têtes `X-RateLimit-*` (NTAPI6).
"""
import importlib.util
import io
import json
import pathlib
import tempfile
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from . import sdk_python
from .openapi import build_openapi_schema


def _charger_client_genere(tmpdir, **kwargs):
    """Écrit le SDK puis l'importe RÉELLEMENT comme un module Python."""
    source = sdk_python.generer(build_openapi_schema(), **kwargs)
    chemin = pathlib.Path(tmpdir) / sdk_python.NOM_MODULE
    chemin.write_text(source, encoding='utf-8')
    spec = importlib.util.spec_from_file_location(
        'taqinor_client_genere', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FausseReponse(io.BytesIO):
    """Réponse HTTP simulée (contexte + `.headers`), comme `urlopen`."""

    def __init__(self, charge, headers=None):
        super().__init__(json.dumps(charge).encode('utf-8'))
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class Ntapi28GenerationTests(SimpleTestCase):
    """Le générateur lui-même (aucun réseau, aucune base)."""

    def test_le_sdk_expose_une_methode_par_collection(self):
        source = sdk_python.generer(build_openapi_schema())
        for attendu in ('def list_leads', 'def iter_leads',
                        'def list_devis', 'def list_factures',
                        'def list_chantiers', 'def list_produits'):
            self.assertIn(attendu, source)

    def test_les_endpoints_utilitaires_ne_deviennent_pas_des_collections(self):
        noms = sdk_python.collections(build_openapi_schema())
        for exclu in ('errors', 'changelog', 'events', 'exports', 'imports'):
            self.assertNotIn(exclu, noms)

    def test_le_flux_a_curseur_a_sa_propre_methode(self):
        source = sdk_python.generer(build_openapi_schema())
        # `events/` ne se pagine pas en `?page=` : le confondre avec une
        # collection ferait sauter des lignes du flux.
        self.assertIn('def iter_events', source)
        self.assertNotIn('def iter_events(self, **filtres)', source)

    def test_aucune_dependance_externe(self):
        source = sdk_python.generer(build_openapi_schema())
        for interdit in ('import requests', 'import httpx', 'import pydantic'):
            self.assertNotIn(interdit, source)

    def test_le_code_genere_est_du_python_valide(self):
        compile(sdk_python.generer(build_openapi_schema()),
                sdk_python.NOM_MODULE, 'exec')

    def test_ecrire_cree_le_dossier_et_le_fichier(self):
        with tempfile.TemporaryDirectory() as tmp:
            cible = pathlib.Path(tmp) / 'sdk' / 'python'
            fichier = sdk_python.ecrire(cible)
            self.assertTrue(fichier.exists())
            self.assertEqual(fichier.name, sdk_python.NOM_MODULE)


class Ntapi28ClientGenereTests(SimpleTestCase):
    """Le client GÉNÉRÉ, importé et exécuté contre un transport simulé."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.module = _charger_client_genere(self._tmp.name)

    def _client(self, reponses):
        """Client dont `_ouvrir` sert `reponses` (liste) dans l'ordre."""
        client = self.module.TaqinorClient('tqk_live_test')
        appels = []

        def _faux_ouvrir(url):
            appels.append(url)
            suivante = reponses.pop(0)
            if isinstance(suivante, Exception):
                raise suivante
            return suivante

        client._ouvrir = _faux_ouvrir
        client.appels = appels
        return client

    # ── Le cœur du critère : lister des leads sur ≥ 2 pages ───────────────
    def test_iter_leads_parcourt_deux_pages(self):
        client = self._client([
            _FausseReponse({'count': 3, 'next': 'page=2',
                            'results': [{'id': 1}, {'id': 2}]}),
            _FausseReponse({'count': 3, 'next': None,
                            'results': [{'id': 3}]}),
        ])
        leads = list(client.iter_leads())
        self.assertEqual([lead['id'] for lead in leads], [1, 2, 3])
        self.assertEqual(len(client.appels), 2)
        self.assertIn('page=1', client.appels[0])
        self.assertIn('page=2', client.appels[1])

    def test_les_filtres_sont_transmis(self):
        client = self._client([
            _FausseReponse({'count': 0, 'next': None, 'results': []})])
        list(client.iter_leads(stage='nouveau'))
        self.assertIn('stage=nouveau', client.appels[0])

    def test_une_page_vide_arrete_l_iteration(self):
        client = self._client([
            _FausseReponse({'count': 99, 'next': 'page=2', 'results': []})])
        self.assertEqual(list(client.iter_leads()), [])

    def test_un_next_menteur_ne_fait_pas_boucler_indefiniment(self):
        """Une API qui renverrait éternellement `next` avec `count` atteint ne
        doit pas figer l'appelant."""
        client = self._client([
            _FausseReponse({'count': 1, 'next': 'page=2',
                            'results': [{'id': 1}]}),
        ])
        self.assertEqual(len(list(client.iter_leads())), 1)

    # ── 429 : `Retry-After` respecté, jamais un backoff inventé ───────────
    #
    # `time.sleep` est patché par `mock.patch`, JAMAIS par une affectation sur
    # `module.time.sleep` : le module `time` du client généré EST le module
    # stdlib partagé — une affectation directe resterait en place pour tout le
    # reste de la suite (et ferait dormir, ou pas, des tests sans rapport).
    def test_429_est_rejoue_en_respectant_retry_after(self):
        client = self._client([
            urllib.error.HTTPError(
                'u', 429, 'Too Many Requests', {'Retry-After': '7'},
                io.BytesIO(b'{"error": {"code": "throttled"}}')),
            _FausseReponse({'count': 1, 'next': None, 'results': [{'id': 1}]}),
        ])
        with mock.patch('time.sleep') as dormir:
            self.assertEqual(len(list(client.iter_leads())), 1)
        dormir.assert_called_once_with(7)

    def test_429_sans_retry_after_utilise_le_repli(self):
        client = self._client([
            urllib.error.HTTPError(
                'u', 429, 'Too Many Requests', {},
                io.BytesIO(b'{"error": {"code": "throttled"}}')),
            _FausseReponse({'count': 1, 'next': None, 'results': [{'id': 1}]}),
        ])
        with mock.patch('time.sleep') as dormir:
            list(client.iter_leads())
        dormir.assert_called_once_with(self.module.ATTENTE_429_DEFAUT)

    def test_429_persistant_finit_par_lever(self):
        module = _charger_client_genere(self._tmp.name, max_reprises=1)
        client = module.TaqinorClient('tqk_live_test')

        def _toujours_429(_url):
            raise urllib.error.HTTPError(
                'u', 429, 'Too Many Requests', {},
                io.BytesIO(b'{"error": {"code": "throttled",'
                           b' "message": "Quota"}}'))

        client._ouvrir = _toujours_429
        with mock.patch('time.sleep'):
            with self.assertRaises(module.TaqinorApiError) as ctx:
                client.list_leads()
        self.assertEqual(ctx.exception.code, 'throttled')

    # ── Enveloppe d'erreur NTAPI3 et en-têtes NTAPI6 ──────────────────────
    def test_erreur_api_expose_le_code_stable(self):
        client = self._client([
            urllib.error.HTTPError(
                'u', 403, 'Forbidden', {},
                io.BytesIO(b'{"error": {"code": "permission_denied",'
                           b' "message": "Scope manquant",'
                           b' "request_id": "abc"}}')),
        ])
        with self.assertRaises(self.module.TaqinorApiError) as ctx:
            client.list_leads()
        self.assertEqual(ctx.exception.code, 'permission_denied')
        self.assertEqual(ctx.exception.request_id, 'abc')

    def test_les_entetes_rate_limit_sont_lus(self):
        client = self._client([
            _FausseReponse({'count': 0, 'next': None, 'results': []},
                           headers={'X-RateLimit-Limit': '1000',
                                    'X-RateLimit-Remaining': '42',
                                    'X-RateLimit-Reset': '1800000000'}),
        ])
        client.list_leads()
        self.assertEqual(client.rate_limit['limit'], 1000)
        self.assertEqual(client.rate_limit['remaining'], 42)

    def test_entete_rate_limit_illisible_ne_leve_jamais(self):
        client = self._client([
            _FausseReponse({'results': []},
                           headers={'X-RateLimit-Limit': 'beaucoup'}),
        ])
        client.list_leads()
        self.assertNotIn('limit', client.rate_limit)

    # ── Authentification ─────────────────────────────────────────────────
    def test_cle_api_ou_jeton_oauth(self):
        avec_cle = self.module.TaqinorClient('tqk_live_x')
        self.assertEqual(avec_cle._entetes()['Authorization'],
                         'Api-Key tqk_live_x')
        avec_jeton = self.module.TaqinorClient(token='jwt-abc')
        self.assertEqual(avec_jeton._entetes()['Authorization'],
                         'Bearer jwt-abc')

    def test_sans_justificatif_le_client_refuse_de_se_construire(self):
        with self.assertRaises(ValueError):
            self.module.TaqinorClient()

    # ── Flux d'évènements par curseur ────────────────────────────────────
    def test_iter_events_suit_le_curseur(self):
        client = self._client([
            _FausseReponse({'results': [{'sequence': 1}, {'sequence': 2}],
                            'next_after': 2}),
            _FausseReponse({'results': [{'sequence': 3}], 'next_after': 3}),
            _FausseReponse({'results': [], 'next_after': None}),
        ])
        sequences = [e['sequence'] for e in client.iter_events()]
        self.assertEqual(sequences, [1, 2, 3])
        self.assertIn('after=0', client.appels[0])
        self.assertIn('after=2', client.appels[1])

    def test_iter_events_sarrete_si_le_curseur_navance_pas(self):
        client = self._client([
            _FausseReponse({'results': [{'sequence': 1}], 'next_after': 0}),
        ])
        self.assertEqual(len(list(client.iter_events())), 1)
