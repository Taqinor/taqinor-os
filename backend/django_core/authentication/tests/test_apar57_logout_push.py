"""APAR57 — la déconnexion désabonne l'appareil des notifications push.

Constat C-APAR-022 : ``LogoutView`` ne touchait pas ``PushSubscription`` ; un
navigateur déconnecté (poste partagé) continuait de recevoir des push porteurs
de jetons « Approuver/Refuser ». Le corps de ``/auth/logout/`` gagne un champ
optionnel ``push_endpoint`` (additif) : l'abonnement de CET endpoint, pour
l'utilisateur courant seulement, est supprimé.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.notifications.models import PushSubscription
from authentication.models import Company

User = get_user_model()

PWD = 'motDePasseApar57!'
LOGOUT = '/api/django/auth/logout/'
EP = 'https://push.example.test/apar57/poste-partage'
EP_AUTRE = 'https://push.example.test/apar57/telephone'

_LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'apar57',
    }
}


@override_settings(CACHES=_LOCMEM_CACHE)
class LogoutPushTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='APAR57 Co', slug='apar57')
        self.user = User.objects.create_user(
            username='resp57', password=PWD, company=self.company)
        self.autre = User.objects.create_user(
            username='autre57', password=PWD, company=self.company)

    def _sub(self, user, endpoint):
        return PushSubscription.objects.create(
            company=self.company, user=user, endpoint=endpoint,
            p256dh='p', auth='a')

    def _login(self, username='resp57'):
        api = APIClient()
        r = api.post('/api/django/token/',
                     {'username': username, 'password': PWD}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return api

    def test_logout_supprime_abonnement_de_l_endpoint(self):
        self._sub(self.user, EP)
        self._sub(self.user, EP_AUTRE)
        api = self._login()
        r = api.post(LOGOUT, {'push_endpoint': EP}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # CLAUSE PERSISTANCE : recompte en base.
        endpoints = set(PushSubscription.objects.filter(
            user=self.user).values_list('endpoint', flat=True))
        self.assertNotIn(EP, endpoints)
        # Les AUTRES appareils de l'utilisateur restent abonnés.
        self.assertIn(EP_AUTRE, endpoints)

    def test_logout_ne_supprime_jamais_l_abonnement_d_autrui(self):
        self._sub(self.autre, EP)
        api = self._login()
        r = api.post(LOGOUT, {'push_endpoint': EP}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(PushSubscription.objects.filter(
            user=self.autre, endpoint=EP).exists())

    def test_logout_sans_endpoint_reste_inchange(self):
        self._sub(self.user, EP)
        api = self._login()
        r = api.post(LOGOUT, {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(PushSubscription.objects.filter(
            user=self.user, endpoint=EP).exists())

    def test_reconnexion_reabonne_normalement(self):
        self._sub(self.user, EP)
        api = self._login()
        api.post(LOGOUT, {'push_endpoint': EP}, format='json')
        api2 = self._login()
        r = api2.post('/api/django/notifications/push/subscribe/', {
            'endpoint': EP, 'keys': {'p256dh': 'p2', 'auth': 'a2'},
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.data)
        self.assertTrue(PushSubscription.objects.filter(
            user=self.user, endpoint=EP).exists())
