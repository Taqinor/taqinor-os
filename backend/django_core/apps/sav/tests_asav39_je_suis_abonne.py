"""ASAV39 — `je_suis_abonne` servi par TicketSerializer (détail et liste),
sans requête par ticket.

Run :
    python manage.py test apps.sav.tests_asav39_je_suis_abonne -v2
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket

User = get_user_model()
BASE = '/api/django/sav/tickets'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class JeSuisAbonneTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav39-co', defaults={'nom': 'ASAV39 Co'})
        self.user = User.objects.create_user(
            username='asav39_admin', password='x', role_legacy='admin',
            company=self.company)
        self.autre = User.objects.create_user(
            username='asav39_autre', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV39')
        self.ticket = self._ticket('SAV-A39-1')

    def _ticket(self, ref):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            type=Ticket.Type.CORRECTIF, created_by=self.user)

    def test_suivi_servi(self):
        api = _api(self.user)
        self.assertFalse(api.get(f'{BASE}/{self.ticket.pk}/').data[
            'je_suis_abonne'])
        api.post(f'{BASE}/{self.ticket.pk}/suivre/')
        self.assertTrue(api.get(f'{BASE}/{self.ticket.pk}/').data[
            'je_suis_abonne'])
        liste = api.get(f'{BASE}/').data
        liste = liste['results'] if isinstance(liste, dict) else liste
        self.assertTrue(liste[0]['je_suis_abonne'])
        api.delete(f'{BASE}/{self.ticket.pk}/suivre/')
        self.assertFalse(api.get(f'{BASE}/{self.ticket.pk}/').data[
            'je_suis_abonne'])

    def test_autre_utilisateur_false(self):
        _api(self.user).post(f'{BASE}/{self.ticket.pk}/suivre/')
        r = _api(self.autre).get(f'{BASE}/{self.ticket.pk}/')
        self.assertFalse(r.data['je_suis_abonne'])

    def test_liste_sans_n_plus_1(self):
        api = _api(self.user)

        def requetes():
            with CaptureQueriesContext(connection) as ctx:
                r = api.get(f'{BASE}/')
                self.assertEqual(r.status_code, 200)
            return len(ctx)

        requetes()  # échauffement (caches de contenu / permissions)
        avant = requetes()
        for i in range(10):
            t = self._ticket(f'SAV-A39-X{i}')
            api.post(f'{BASE}/{t.pk}/suivre/')
        apres = requetes()
        self.assertLessEqual(apres, avant + 2)
