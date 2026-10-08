"""ASEC14 — la réponse de connexion ne dépend pas de l'existence ni de l'état
du compte tant que le mot de passe n'est pas prouvé.

Mauvais mot de passe pour un compte verrouillé, un compte SSO obligatoire, un
compte normal et un nom inconnu → même 401, même corps. Avec le BON mot de
passe : SSO → 403 ``sso_required``.

ASEC14-revue (décision fondateur « même réponse que faux ») : un compte
VERROUILLÉ ne fait plus vérifier son mot de passe — même le BON mot de passe
reçoit EXACTEMENT le 401 d'un mauvais mot de passe, et la tentative est
comptée.
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


def _corps(resp):
    """Corps de la réponse sans ``error.request_id`` — identifiant de
    corrélation unique PAR requête (ACAL315 : jamais null, uuid4 sinon) ;
    tout le reste doit être identique."""
    corps = dict(resp.data)
    if isinstance(corps.get('error'), dict):
        corps['error'] = {
            k: v for k, v in corps['error'].items() if k != 'request_id'}
    return corps


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

    def test_bon_mdp_verrou_meme_401_que_faux(self):
        faux = self._login('asec14_normal', 'faux-mot-de-passe')
        r = self._login('asec14_verrou', _BON)
        self.assertEqual(r.status_code, 401, r.data)
        self.assertEqual(_corps(r), _corps(faux))
        self.assertNotIn('compte_verrouille', str(r.data))
        self.assertNotIn('access_token', r.cookies)

    def test_verrouille_tentative_comptee(self):
        avant = User.objects.get(pk=self.verrou.pk).failed_login_count or 0
        self._login('asec14_verrou', _BON)
        self.assertEqual(
            User.objects.get(pk=self.verrou.pk).failed_login_count, avant + 1)

    def test_bon_mdp_sso_403(self):
        r = self._login('asec14_sso', _BON)
        self.assertEqual(r.status_code, 403, r.data)
        self.assertTrue(r.data.get('sso_required'))
        self.assertNotIn('access_token', r.cookies)
