"""ASEC14 — la réponse de connexion ne dépend pas de l'existence ni de l'état
du compte tant que le mot de passe n'est pas prouvé.

Mauvais mot de passe pour un compte verrouillé, un compte SSO obligatoire, un
compte normal et un nom inconnu → même 401, même corps. Avec le BON mot de
passe : verrou → 403 ``compte_verrouille``, SSO → 403 ``sso_required``.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.identity.models import IdentityProvider
from authentication.models import Company

User = get_user_model()

_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}
_BON = 'Bon-mdp-123!'


@override_settings(CACHES=_LOCMEM_CACHE)
class EnumerationLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.co = Company.objects.create(nom='ASEC14', slug='asec14-co')
        self.co_sso = Company.objects.create(nom='ASEC14 SSO', slug='asec14-sso')
        IdentityProvider.objects.create(
            company=self.co_sso, protocol='saml', nom='Okta', actif=True,
            enforce_sso=True)
        self.normal = User.objects.create_user(
            username='asec14_normal', password=_BON, company=self.co)
        self.verrou = User.objects.create_user(
            username='asec14_verrou', password=_BON, company=self.co)
        self.verrou.locked_until = timezone.now() + timedelta(minutes=15)
        self.verrou.save(update_fields=['locked_until'])
        self.sso = User.objects.create_user(
            username='asec14_sso', password=_BON, company=self.co_sso)

    def _login(self, username, password):
        cache.clear()  # throttle IP couvert ailleurs
        return APIClient().post(
            '/api/django/token/', {'username': username, 'password': password},
            format='json')

    def test_mauvais_mdp_reponse_identique_4_cas(self):
        reponses = [
            self._login(u, 'faux-mot-de-passe')
            for u in ('asec14_verrou', 'asec14_sso', 'asec14_normal',
                      'asec14_inconnu')
        ]
        for r in reponses:
            self.assertEqual(r.status_code, 401, r.data)
        corps = [dict(r.data) for r in reponses]
        for c in corps[1:]:
            self.assertEqual(c.get('detail'), corps[0].get('detail'))
            self.assertEqual(set(c), set(corps[0]))
            self.assertNotIn('sso_required', c)

    def test_bon_mdp_verrou_403(self):
        r = self._login('asec14_verrou', _BON)
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data.get('code'), 'compte_verrouille')
        self.assertNotIn('access_token', r.cookies)

    def test_bon_mdp_sso_403(self):
        r = self._login('asec14_sso', _BON)
        self.assertEqual(r.status_code, 403, r.data)
        self.assertTrue(r.data.get('sso_required'))
        self.assertNotIn('access_token', r.cookies)
