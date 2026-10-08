"""ASEC5 — un code TOTP ne sert qu'une fois ; gestes de sécurité bornés par
utilisateur.

Même code présenté deux fois dans sa fenêtre → 200 puis 401
``otp_deja_utilise`` (le pas consommé est relu en base) ; le pas suivant reste
accepté. Désactivation 2FA et changement de mot de passe : au-delà de 5 appels
par heure pour le même utilisateur → 429.
"""
import time

import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company

User = get_user_model()

_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}
_MDP = 'Bon-mdp-123!'


@override_settings(CACHES=_LOCMEM_CACHE)
class TotpRejeuTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='ASEC5 Co', slug='asec5-co')
        self.secret = pyotp.random_base32()
        self.user = User.objects.create_user(
            username='asec5_u', password=_MDP, company=self.company)
        self.user.totp_secret = self.secret
        self.user.totp_enabled = True
        self.user.save()

    def _login(self, otp):
        cache.clear()  # throttle IP couvert ailleurs
        return APIClient().post(
            '/api/django/token/',
            {'username': 'asec5_u', 'password': _MDP, 'otp': otp},
            format='json')

    def test_meme_code_refuse_deuxieme_fois(self):
        code = pyotp.TOTP(self.secret).now()
        premier = self._login(code)
        self.assertEqual(premier.status_code, 200, premier.data)
        pas = User.objects.get(pk=self.user.pk).totp_dernier_pas
        self.assertIsNotNone(pas)
        second = self._login(code)
        self.assertEqual(second.status_code, 401, second.data)
        self.assertEqual(second.data.get('code'), 'otp_deja_utilise')
        # Connexion puis désactivation 2FA avec le même code : refusée aussi.
        api = APIClient()
        api.force_authenticate(User.objects.get(pk=self.user.pk))
        resp = api.post('/api/django/auth/2fa/disable/', {'code': code},
                        format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(User.objects.get(pk=self.user.pk).totp_enabled)

    def test_pas_suivant_accepte(self):
        totp = pyotp.TOTP(self.secret)
        self.assertEqual(self._login(totp.now()).status_code, 200)
        suivant = totp.at(int(time.time()) + 30)
        resp = self._login(suivant)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_throttle_desactivation_2fa_par_utilisateur(self):
        api = APIClient()
        api.force_authenticate(self.user)
        statuts = [
            api.post('/api/django/auth/2fa/disable/', {'code': '000000'},
                     format='json').status_code
            for _ in range(6)
        ]
        self.assertNotIn(429, statuts[:5])
        self.assertEqual(statuts[5], 429)

    def test_throttle_changement_mdp_par_utilisateur(self):
        api = APIClient()
        api.force_authenticate(self.user)
        statuts = [
            api.post('/api/django/auth/change-password/',
                     {'current_password': 'faux', 'new_password': 'x'},
                     format='json').status_code
            for _ in range(6)
        ]
        self.assertNotIn(429, statuts[:5])
        self.assertEqual(statuts[5], 429)
