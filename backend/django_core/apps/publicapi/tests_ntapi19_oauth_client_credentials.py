"""NTAPI19 — OAuth2 « client_credentials » par intégration.

Critère d'acceptation, dans les deux sens :
  * un `client_credentials` valide obtient un jeton qui AUTORISE les scopes
    accordés et qui EXPIRE ;
  * un secret erroné → 401.

Vérifie en plus ce qui rend un JWT sans état acceptable ici : désactiver le
client coupe l'accès IMMÉDIATEMENT même avec un jeton encore valide, retirer un
scope prend effet sans attendre l'expiration, et un jeton de session
utilisateur (signé avec la MÊME clé serveur) n'ouvre rien.
"""
import time

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company

from . import oauth
from .constants import SCOPE_READ_DEVIS, SCOPE_READ_LEADS
from .models import ApiKey, OAuthClient


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _bearer(jeton):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {jeton}')
    return api


class Ntapi19TokenEndpointTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi19', 'NTAPI19')
        self.client_oauth, self.client_id, self.secret = OAuthClient.issue(
            company=self.co, label='Intégration ERP',
            scopes=[SCOPE_READ_LEADS, SCOPE_READ_DEVIS])

    def _demander(self, **surcharge):
        corps = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.secret,
        }
        corps.update(surcharge)
        return APIClient().post(
            '/api/public/v1/oauth/token/', corps, format='json')

    # ── Le cœur du critère ────────────────────────────────────────────────
    def test_client_credentials_valide_obtient_un_jeton(self):
        resp = self._demander()
        self.assertEqual(resp.status_code, 200, resp.content)
        corps = resp.json()
        self.assertTrue(corps['access_token'])
        self.assertEqual(corps['token_type'], 'Bearer')
        self.assertGreater(corps['expires_in'], 0)
        self.assertIn(SCOPE_READ_LEADS, corps['scope'].split())

    def test_secret_errone_renvoie_401(self):
        resp = self._demander(client_secret='mauvais-secret')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['error']['code'], 'invalid_client')

    def test_client_inconnu_renvoie_la_meme_reponse_quun_secret_faux(self):
        """Sans cette égalité, un attaquant distinguerait « ce client existe »
        de « ce client n'existe pas » — la moitié du travail faite."""
        inconnu = self._demander(client_id='tqc_inexistant').json()['error']
        faux = self._demander(client_secret='x').json()['error']
        self.assertEqual(inconnu['code'], faux['code'])
        self.assertEqual(inconnu['message'], faux['message'])

    def test_client_desactive_renvoie_la_meme_reponse(self):
        self.client_oauth.actif = False
        self.client_oauth.save(update_fields=['actif'])
        resp = self._demander()
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['error']['code'], 'invalid_client')

    def test_grant_type_non_supporte(self):
        resp = self._demander(grant_type='password')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['code'], 'unsupported_grant_type')

    def test_scope_demande_est_un_sous_ensemble_jamais_une_elevation(self):
        resp = self._demander(scope=f'{SCOPE_READ_LEADS} read:factures')
        accordes = resp.json()['scope'].split()
        self.assertEqual(accordes, [SCOPE_READ_LEADS])
        self.assertNotIn('read:factures', accordes)

    def test_secret_jamais_relisible(self):
        """Le secret n'est stocké que haché — la colonne ne le contient pas."""
        self.client_oauth.refresh_from_db()
        self.assertNotEqual(self.client_oauth.client_secret_hash, self.secret)
        self.assertNotIn(self.secret, str(self.client_oauth.__dict__))


class Ntapi19BearerAccessTests(TestCase):
    """Le jeton ouvre VRAIMENT les endpoints, aux seuls scopes accordés."""

    def setUp(self):
        self.co = _company('ntapi19-acc', 'NTAPI19 accès')
        self.client_oauth, self.client_id, self.secret = OAuthClient.issue(
            company=self.co, label='Lecture leads', scopes=[SCOPE_READ_LEADS])
        self.jeton, _ = oauth.emettre_token(self.client_oauth)

    def test_le_jeton_autorise_un_scope_accorde(self):
        resp = _bearer(self.jeton).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)

    def test_le_jeton_refuse_un_scope_non_accorde(self):
        resp = _bearer(self.jeton).get('/api/public/v1/devis/')
        self.assertEqual(resp.status_code, 403)

    def test_le_jeton_est_scope_a_sa_societe(self):
        from apps.crm.models import Lead

        autre = _company('ntapi19-autre', 'NTAPI19 autre')
        Lead.objects.create(company=autre, nom='Lead voisin')
        Lead.objects.create(company=self.co, nom='Mon lead')
        resp = _bearer(self.jeton).get('/api/public/v1/leads/')
        noms = [item['nom'] for item in resp.json()['results']]
        self.assertEqual(noms, ['Mon lead'])

    def test_jeton_expire_est_refuse(self):
        vieux, _ = oauth.emettre_token(
            self.client_oauth, now=time.time() - oauth.ttl_seconds() - 60)
        resp = _bearer(vieux).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 401)

    @override_settings(PUBLIC_API_OAUTH_TOKEN_TTL=60)
    def test_ttl_configurable(self):
        _jeton, duree = oauth.emettre_token(self.client_oauth)
        self.assertEqual(duree, 60)

    def test_jeton_bidon_est_refuse(self):
        resp = _bearer('pas.un.jwt').get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 401)

    def test_un_jeton_de_session_utilisateur_nouvre_rien(self):
        """Les deux jetons sont signés avec la MÊME SECRET_KEY : sans le
        marqueur de type vérifié, un jeton d'accès utilisateur ouvrirait l'API
        publique avec des scopes qu'il ne porte pas."""
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import AccessToken

        user = get_user_model().objects.create_user(
            username='u-ntapi19', password='x', company=self.co)
        resp = _bearer(str(AccessToken.for_user(user))).get(
            '/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 401)

    # ── Révocation immédiate malgré un JWT sans état ──────────────────────
    def test_desactiver_le_client_coupe_un_jeton_encore_valide(self):
        self.assertEqual(
            _bearer(self.jeton).get('/api/public/v1/leads/').status_code, 200)
        self.client_oauth.actif = False
        self.client_oauth.save(update_fields=['actif'])
        self.assertEqual(
            _bearer(self.jeton).get('/api/public/v1/leads/').status_code, 401)

    def test_retirer_un_scope_prend_effet_sans_attendre_lexpiration(self):
        self.assertEqual(
            _bearer(self.jeton).get('/api/public/v1/leads/').status_code, 200)
        cle = self.client_oauth.api_key
        cle.scopes = []
        cle.save(update_fields=['scopes'])
        self.assertEqual(
            _bearer(self.jeton).get('/api/public/v1/leads/').status_code, 403)


class Ntapi19CompanionKeyTests(TestCase):
    """La clé compagnon : ce qui fait que tout l'aval marche sans changement."""

    def setUp(self):
        self.co = _company('ntapi19-cle', 'NTAPI19 clé')
        self.client_oauth, _cid, _sec = OAuthClient.issue(
            company=self.co, label='C', scopes=[SCOPE_READ_LEADS])

    def test_une_cle_compagnon_est_creee_avec_les_memes_scopes(self):
        cle = self.client_oauth.api_key
        self.assertIsInstance(cle, ApiKey)
        self.assertEqual(cle.company_id, self.co.id)
        self.assertEqual(cle.scopes, [SCOPE_READ_LEADS])

    def test_la_cle_compagnon_nest_pas_utilisable_en_api_key_directe(self):
        """Son secret en clair est généré puis JETÉ : il n'existe nulle part,
        donc personne ne peut la présenter en `Authorization: Api-Key`."""
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Api-Key {self.client_oauth.api_key.prefix}')
        self.assertEqual(
            api.get('/api/public/v1/leads/').status_code, 401)

    def test_request_auth_reste_une_vraie_apikey(self):
        """C'est CE choix qui laisse scopes, débit, quota, en-têtes
        X-RateLimit et dépréciation fonctionner sans un seul assouplissement."""
        jeton, _ = oauth.emettre_token(self.client_oauth)
        resp = _bearer(jeton).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        # NTAPI5 : l'en-tête de version épinglée est bien posé, donc le mixin
        # de réponse publique a vu une ApiKey.
        self.assertEqual(resp['X-Taqinor-Api-Version'], 'v1')


class Ntapi19ScopesEffectifsTests(TestCase):
    """L'intersection jeton ∩ clé, isolée du transport HTTP."""

    def setUp(self):
        self.co = _company('ntapi19-int', 'NTAPI19 intersection')
        self.client_oauth, _cid, _sec = OAuthClient.issue(
            company=self.co, label='C',
            scopes=[SCOPE_READ_LEADS, SCOPE_READ_DEVIS])

    def test_intersection(self):
        charge = {'scopes': [SCOPE_READ_LEADS, 'read:factures']}
        cle = self.client_oauth.api_key
        self.assertEqual(
            oauth.scopes_effectifs(charge, cle), [SCOPE_READ_LEADS])

    def test_jeton_sans_scope_ne_donne_rien(self):
        self.assertEqual(
            oauth.scopes_effectifs({'scopes': []},
                                   self.client_oauth.api_key), [])
