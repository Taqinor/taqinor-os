"""AUD408 — la révocation d'une session coupe AUSSI le jeton d'ACCÈS.

Défaut audité : logout, révocation d'une session distante, éviction concurrente
et changement de mot de passe ne blacklistaient QUE le jeton de
rafraîchissement. ``CookieJWTAuthentication`` ne consultait ni
``BlacklistedToken`` ni ``UserSession.revoked`` pour le jeton d'ACCÈS — un
appareil révoqué continuait donc d'authentifier jusqu'à 30 min
(``ACCESS_TOKEN_LIFETIME``) après une révocation affichée comme effective, et
un appareil DISTANT ne reçoit littéralement aucune réponse pour l'apprendre.

Décision retenue (écrite dans ``session_policy.py``) : un claim de session
(``sid`` = ``jti`` du refresh = clé de ``UserSession``) est posé sur chaque
jeton émis par la voie de connexion, et comparé à ``UserSession.revoked`` à
chaque requête. Ces tests sont ROUGES avant le correctif (200) et VERTS après
(401). ``test_access_token_lifetime_is_short`` (ERR87) reste inchangé et vert.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, UserSession

User = get_user_model()

PWD = 'ancienMotDePasse1'
ME = '/api/django/auth/me/'

_LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'aud408',
    }
}


@override_settings(CACHES=_LOCMEM_CACHE)
class Aud408AccessRevocationTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='AUD408 Co', slug='aud408')
        self.user = User.objects.create_user(
            username='dave408', password=PWD, company=self.company)

    def _login(self):
        """Connexion réelle → renvoie (client, access_token brut)."""
        api = APIClient()
        r = api.post('/api/django/token/',
                     {'username': 'dave408', 'password': PWD}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return api, r.cookies['access_token'].value

    @staticmethod
    def _bearer(token):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return api

    # ── Le claim de session est bien posé par la voie de connexion ─────────
    def test_le_jeton_dacces_porte_le_claim_de_session(self):
        _, access = self._login()
        from authentication.session_policy import SESSION_CLAIM
        sid = AccessToken(access).get(SESSION_CLAIM)
        self.assertTrue(sid)
        self.assertTrue(
            UserSession.objects.filter(user=self.user, jti=sid).exists())

    # ── 1) Révocation d'un appareil DISTANT ───────────────────────────────
    def test_revoquer_une_session_distante_tue_son_jeton_dacces(self):
        api_a, _ = self._login()
        api_b, access_b = self._login()
        session_b = UserSession.objects.get(
            jti=AccessToken(access_b).get('sid'))

        # L'appareil B fonctionne AVANT la révocation.
        self.assertEqual(api_b.get(ME).status_code, 200)

        r = api_a.post(f'/api/django/auth/sessions/{session_b.id}/revoke/')
        self.assertEqual(r.status_code, 200, r.data)

        # AUD408 : l'appareil B est coupé IMMÉDIATEMENT (avant : 200 jusqu'à
        # 30 min, sans qu'aucune réponse ne l'en informe).
        self.assertEqual(self._bearer(access_b).get(ME).status_code, 401)
        # L'appareil A (non révoqué) reste opérationnel.
        self.assertEqual(api_a.get(ME).status_code, 200)

    # ── 2) Déconnexion ────────────────────────────────────────────────────
    def test_logout_tue_le_jeton_dacces_deja_emis(self):
        api, access = self._login()
        self.assertEqual(self._bearer(access).get(ME).status_code, 200)
        r = api.post('/api/django/auth/logout/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._bearer(access).get(ME).status_code, 401)

    # ── 3) Changement de mot de passe (VX242 → AUD408) ────────────────────
    def test_changement_de_mot_de_passe_tue_les_autres_jetons_dacces(self):
        api_a, access_a = self._login()
        api_b, access_b = self._login()

        r = api_a.post('/api/django/auth/change-password/', {
            'current_password': PWD,
            'new_password': 'nouveauMotDePasse2',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data.get('sessions_revoked'), 1)

        # L'autre appareil est coupé tout de suite ; celui qui a changé le mot
        # de passe reste connecté (contrat VX242 inchangé).
        self.assertEqual(self._bearer(access_b).get(ME).status_code, 401)
        self.assertEqual(self._bearer(access_a).get(ME).status_code, 200)

    # ── 4) Éviction concurrente (NTSEC10) ─────────────────────────────────
    def test_eviction_concurrente_tue_le_jeton_dacces_evince(self):
        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.update_or_create(
            company=self.company,
            defaults={'nom': 'AUD408 Co', 'max_concurrent_sessions': 1},
        )
        _, access_a = self._login()
        self.assertEqual(self._bearer(access_a).get(ME).status_code, 200)
        # La 2e connexion évince la plus ancienne (limite = 1).
        _, access_b = self._login()
        self.assertEqual(self._bearer(access_a).get(ME).status_code, 401)
        self.assertEqual(self._bearer(access_b).get(ME).status_code, 200)

    # ── Compatibilité : jetons sans claim de session ──────────────────────
    def test_jeton_sans_claim_de_session_reste_accepte(self):
        """``AccessToken.for_user`` (scripts, outils, tests) est inchangé."""
        token = str(AccessToken.for_user(self.user))
        self.assertEqual(self._bearer(token).get(ME).status_code, 200)

    def test_claim_sans_ligne_de_session_reste_accepte(self):
        """Un ``sid`` inconnu ne bloque pas (aucune session tracée à opposer)."""
        token = AccessToken.for_user(self.user)
        token['sid'] = 'jti-jamais-trace'
        self.assertEqual(self._bearer(str(token)).get(ME).status_code, 200)

    def test_session_active_ne_bloque_jamais(self):
        api, _ = self._login()
        self.assertEqual(api.get(ME).status_code, 200)
        self.assertEqual(api.get(ME).status_code, 200)
