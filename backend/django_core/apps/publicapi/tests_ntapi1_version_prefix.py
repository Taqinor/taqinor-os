"""NTAPI1 — préfixe de version explicite `/api/public/v1/` + alias legacy.

Le contrat vérifié ici :

* `/api/public/v1/leads/` répond À L'IDENTIQUE (même auth par clé, même corps) ;
* `/api/public/leads/` (racine historique SANS version) redirige DÉFINITIVEMENT
  vers v1 — donc aucune clé existante n'est cassée : le client suit la
  redirection avec le même en-tête `Authorization` et obtient sa réponse ;
* la redirection ne perd JAMAIS ni la query string ni le corps d'une écriture
  (308 sur les méthodes non sûres) ;
* un chemin DÉJÀ versionné mais inconnu est un 404 franc, jamais une boucle de
  redirection `/v1/v1/v1/…`.
"""
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .constants import (
    PUBLIC_API_BASE, PUBLIC_API_DEFAULT_VERSION, PUBLIC_API_LEGACY_BASE,
    PUBLIC_API_LEGACY_SUNSET, PUBLIC_API_VERSIONS, SCOPE_READ_LEADS,
)
from .models import ApiKey
from .versioning import (
    version_demandee, version_depuis_chemin, version_depuis_entete,
)


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi1VersionConstantsTests(SimpleTestCase):
    def test_versions_servies_declarees_une_seule_fois(self):
        self.assertEqual(PUBLIC_API_VERSIONS, ['v1'])
        self.assertIn(PUBLIC_API_DEFAULT_VERSION, PUBLIC_API_VERSIONS)
        self.assertEqual(PUBLIC_API_LEGACY_BASE, '/api/public/')
        self.assertEqual(PUBLIC_API_BASE, '/api/public/v1/')

    def test_version_lue_depuis_le_chemin(self):
        self.assertEqual(version_depuis_chemin('/api/public/v1/leads/'), 'v1')
        self.assertEqual(version_depuis_chemin('/api/public/v1'), 'v1')
        # Racine non versionnée et version inconnue : jamais « résolues ».
        self.assertIsNone(version_depuis_chemin('/api/public/leads/'))
        self.assertIsNone(version_depuis_chemin('/api/public/v9/leads/'))
        self.assertIsNone(version_depuis_chemin(''))

    def test_entete_de_requete_sert_de_repli(self):
        self.assertEqual(
            version_depuis_entete({'HTTP_X_TAQINOR_API_VERSION': 'V1'}), 'v1')
        # Valeur inconnue ignorée : l'en-tête n'ouvre aucun contrat non monté.
        self.assertIsNone(
            version_depuis_entete({'HTTP_X_TAQINOR_API_VERSION': 'v9'}))
        self.assertIsNone(version_depuis_entete({}))

    def test_resolution_chemin_puis_entete_puis_defaut(self):
        class _Req:
            def __init__(self, path, meta):
                self.path, self.META = path, meta

        # Le chemin l'emporte sur l'en-tête.
        self.assertEqual(
            version_demandee(_Req('/api/public/v1/leads/',
                                  {'HTTP_X_TAQINOR_API_VERSION': 'v1'})), 'v1')
        # Sans version dans le chemin, l'en-tête décide…
        self.assertEqual(
            version_demandee(_Req('/api/public/leads/',
                                  {'HTTP_X_TAQINOR_API_VERSION': 'v1'})), 'v1')
        # … et sans en-tête non plus, le défaut.
        self.assertEqual(
            version_demandee(_Req('/api/public/leads/', {})),
            PUBLIC_API_DEFAULT_VERSION)


class Ntapi1VersionedPrefixTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='ntapi1', defaults={'nom': 'NTAPI1'})
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='v1', scopes=[SCOPE_READ_LEADS])

    def test_chemin_versionne_repond_a_l_identique(self):
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self.assertIsNotNone(
            data['results'] if isinstance(data, dict) and 'results' in data
            else data)

    def test_racine_non_versionnee_redirige_en_301(self):
        resp = _key_client(self.raw).get('/api/public/leads/')
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'], '/api/public/v1/leads/')
        # RFC 8594 — l'alias est daté, visible dans les logs du client.
        self.assertEqual(resp['Deprecation'], 'true')
        self.assertEqual(resp['Sunset'], PUBLIC_API_LEGACY_SUNSET)

    def test_cle_existante_non_cassee_en_suivant_la_redirection(self):
        resp = _key_client(self.raw).get('/api/public/leads/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.redirect_chain,
                         [('/api/public/v1/leads/', 301)])

    def test_query_string_preservee(self):
        resp = _key_client(self.raw).get('/api/public/leads/?stage=NEW')
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'], '/api/public/v1/leads/?stage=NEW')

    def test_ecriture_redirigee_en_308_pour_ne_pas_perdre_le_corps(self):
        # 301 autorise un client à retomber en GET : une écriture perdrait son
        # corps. 308 l'interdit explicitement.
        resp = _key_client(self.raw).post(
            '/api/public/leads-write/', {'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 308)
        self.assertEqual(resp['Location'], '/api/public/v1/leads-write/')

    def test_racine_nue_redirige_vers_la_racine_versionnee(self):
        resp = _key_client(self.raw).get('/api/public/')
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'], '/api/public/v1/')

    def test_chemin_versionne_inconnu_est_un_404_pas_une_boucle(self):
        resp = _key_client(self.raw).get('/api/public/v1/nexiste-pas/')
        self.assertEqual(resp.status_code, 404)

    def test_endpoints_deja_versionnes_inchanges(self):
        """NTADM42/NTSCM38 écrivaient `v1/` en dur dans l'urlconf : le segment
        vient désormais du mont, le chemin servi est le MÊME qu'avant."""
        resp = _key_client(self.raw).get('/api/public/v1/licence/statut/')
        # Sans le scope `read:licence` → 403 (et surtout PAS 404 : la route
        # existe toujours au même endroit).
        self.assertEqual(resp.status_code, 403)
