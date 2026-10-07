"""ASEC45 — jeton de flux iCal révocable et expirant.

Constat C-ASEC-027 : le jeton signé n'expirait jamais et ne pouvait pas être
révoqué (régénérer le lien laissait l'ancien valide), et les deux vues de
flux n'avaient aucun throttle. Attendu : ancien lien après régénération →
404 neutre ; jeton plus vieux que 180 jours → 404 neutre ; nouveau → 200 ;
rafale → 429.
"""
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.reporting.calendar import make_ics_token
from apps.reporting.models import JetonCalendrier
from authentication.models import Company

User = get_user_model()
FLUX = '/api/django/reporting/calendar.ics?token='
ABONNEMENT = '/api/django/reporting/calendar/subscription/'


class JetonIcalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='ASEC45', slug='asec45')
        self.user = User.objects.create_user(
            username='asec45_user', password='x', role_legacy='responsable',
            company=self.company)
        self.session = APIClient()
        self.session.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def tearDown(self):
        cache.clear()

    def test_ancien_jeton_apres_regeneration_404(self):
        ancien = self.session.get(ABONNEMENT).data['token']
        self.assertEqual(APIClient().get(FLUX + ancien).status_code, 200)
        r = self.session.post(ABONNEMENT)
        self.assertEqual(r.status_code, 200, r.content)
        nouveau = r.data['token']
        self.assertNotEqual(nouveau, ancien)
        self.assertEqual(
            JetonCalendrier.objects.get(user=self.user).version, 1)
        reponse_ancien = APIClient().get(FLUX + ancien)
        reponse_faux = APIClient().get(FLUX + 'pas-un-jeton')
        self.assertEqual(reponse_ancien.status_code, 404)
        # Neutre : même réponse qu'un jeton inexistant.
        self.assertEqual(reponse_ancien.content, reponse_faux.content)

    def test_jeton_trop_vieux_404(self):
        il_y_a_400_jours = time.time() - 400 * 86400
        with mock.patch('django.core.signing.time.time',
                        return_value=il_y_a_400_jours):
            vieux = make_ics_token(self.user)
        self.assertEqual(APIClient().get(FLUX + vieux).status_code, 404)
        recent = make_ics_token(self.user)
        self.assertEqual(APIClient().get(FLUX + recent).status_code, 200)

    def test_nouveau_jeton_200(self):
        self.session.post(ABONNEMENT)
        nouveau = self.session.get(ABONNEMENT).data['token']
        r = APIClient().get(FLUX + nouveau)
        self.assertEqual(r.status_code, 200)
        self.assertIn('BEGIN:VCALENDAR', r.content.decode())

    def test_throttle_flux(self):
        jeton = make_ics_token(self.user)
        client = APIClient()
        statuts = [client.get(FLUX + jeton).status_code for _ in range(40)]
        self.assertEqual(statuts[0], 200)
        self.assertIn(429, statuts)
        statuts_abo = [self.session.get(ABONNEMENT).status_code
                       for _ in range(40)]
        self.assertIn(429, statuts_abo)
