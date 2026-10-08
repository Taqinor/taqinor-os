"""ASEC49 — le refresh TOURNE à chaque usage et les deux routes de
rafraîchissement appliquent la MÊME politique de session.

* route cookie ``/api/django/auth/token/refresh/`` : nouveau refresh à chaque
  appel, l'ancien est en liste noire (rejeu → 401) ;
* route corps ``/api/django/token/refresh/`` : même rotation, et la durée
  absolue de session société (``session_absolute_hours``) s'y applique ;
* la session (``UserSession``) reste retrouvée par son claim stable ``sid``
  après rotation : durée absolue et révocation tiennent toujours ;
* la borne de 7 jours (``exp`` du refresh d'origine) ne glisse pas.

Run :
    python manage.py test authentication.tests_asec49_refresh_rotation -v2
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.parametres.models import CompanyProfile
from authentication.models import Company, UserSession
from authentication.throttles import LoginRateThrottle
from core.throttling import CookieRefreshThrottle

User = get_user_model()

_BON = 'Bon-mdp-123!'
_COOKIE_URL = '/api/django/auth/token/refresh/'
_CORPS_URL = '/api/django/token/refresh/'
_LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=_LOCMEM)
class RefreshRotationTests(TestCase):
    def setUp(self):
        cache.clear()
        for cls in (LoginRateThrottle, CookieRefreshThrottle):
            patcher = mock.patch.object(cls, 'allow_request', return_value=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.company = Company.objects.create(nom='ASEC49', slug='asec49')
        self.user = User.objects.create_user(
            username='asec49_u', password=_BON, company=self.company)

    def _login(self):
        api = APIClient()
        r = api.post('/api/django/token/', {
            'username': 'asec49_u', 'password': _BON}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return api, api.cookies['refresh_token'].value

    def test_cookie_refresh_tourne(self):
        api, ancien = self._login()
        r = api.post(_COOKIE_URL)
        self.assertEqual(r.status_code, 200, r.data)
        nouveau = r.cookies['refresh_token'].value
        self.assertNotEqual(nouveau, ancien)
        a = RefreshToken(nouveau)
        o = RefreshToken(ancien, verify=False)
        self.assertNotEqual(a['jti'], o['jti'])
        # La borne de 7 jours ne glisse pas : même ``exp`` que le jeton d'origine.
        self.assertEqual(a['exp'], o['exp'])
        # Le claim de session stable est conservé.
        self.assertEqual(a['sid'], o['sid'])
        # Persistance : l'ancien est relu en liste noire en base.
        self.assertTrue(BlacklistedToken.objects.filter(
            token__jti=o['jti']).exists())
        # Le nouveau refresh continue de fonctionner (usage normal).
        r2 = api.post(_COOKIE_URL)
        self.assertEqual(r2.status_code, 200, r2.data)

    def test_ancien_refresh_rejoue_401(self):
        api, ancien = self._login()
        self.assertEqual(api.post(_COOKIE_URL).status_code, 200)
        voleur = APIClient()
        voleur.cookies['refresh_token'] = ancien
        self.assertEqual(voleur.post(_COOKIE_URL).status_code, 401)
        # Même rejeu par la route corps : refusé aussi.
        r = APIClient().post(_CORPS_URL, {'refresh': ancien}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_route_corps_tourne(self):
        _, ancien = self._login()
        r = APIClient().post(_CORPS_URL, {'refresh': ancien}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('access', r.data)
        self.assertNotEqual(r.data['refresh'], ancien)
        rejeu = APIClient().post(_CORPS_URL, {'refresh': ancien}, format='json')
        self.assertEqual(rejeu.status_code, 401)

    def test_route_corps_respecte_duree_absolue(self):
        CompanyProfile.objects.create(
            company=self.company, session_absolute_hours=1)
        _, ancien = self._login()
        session = UserSession.objects.filter(user=self.user).latest('pk')
        UserSession.objects.filter(pk=session.pk).update(
            created_at=timezone.now() - timedelta(hours=2))
        r = APIClient().post(_CORPS_URL, {'refresh': ancien}, format='json')
        self.assertEqual(r.status_code, 401)
        session.refresh_from_db()
        self.assertTrue(session.revoked)

    def test_duree_absolue_tient_apres_rotation(self):
        CompanyProfile.objects.create(
            company=self.company, session_absolute_hours=1)
        api, _ = self._login()
        self.assertEqual(api.post(_COOKIE_URL).status_code, 200)
        session = UserSession.objects.filter(user=self.user).latest('pk')
        UserSession.objects.filter(pk=session.pk).update(
            created_at=timezone.now() - timedelta(hours=2))
        # Le refresh TOURNÉ (nouveau jti) retrouve la session par ``sid``.
        self.assertEqual(api.post(_COOKIE_URL).status_code, 401)

    def test_session_revoquee_refuse_le_refresh_tourne(self):
        api, _ = self._login()
        self.assertEqual(api.post(_COOKIE_URL).status_code, 200)
        UserSession.objects.filter(user=self.user).update(revoked=True)
        self.assertEqual(api.post(_COOKIE_URL).status_code, 401)

    def test_corps_non_objet_sans_500(self):
        r = APIClient().post(_CORPS_URL, ['x'], format='json')
        self.assertEqual(r.status_code, 401)
