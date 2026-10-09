"""ASAV43 — `statuts_suivants` servi par TicketSerializer = graphe serveur
(`machine_etats.statuts_suivants`), sans requête supplémentaire par ticket.

Run :
    python manage.py test apps.sav.tests_asav43_statuts_suivants -v2
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav import machine_etats
from apps.sav.models import Ticket

User = get_user_model()
BASE = '/api/django/sav/tickets'


class StatutsSuivantsTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav43-co', defaults={'nom': 'ASAV43 Co'})
        self.user = User.objects.create_user(
            username='asav43_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV43')

    def _ticket(self, ref, statut):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            type=Ticket.Type.CORRECTIF, statut=statut, created_by=self.user)

    def test_servis_egal_graphe(self):
        for i, statut in enumerate((
                Ticket.Statut.NOUVEAU, Ticket.Statut.EN_COURS,
                Ticket.Statut.CLOTURE)):
            t = self._ticket(f'SAV-A43-{i}', statut)
            r = self.api.get(f'{BASE}/{t.pk}/')
            self.assertEqual(
                r.data['statuts_suivants'], machine_etats.statuts_suivants(t))
        en_cours = self._ticket('SAV-A43-X', Ticket.Statut.EN_COURS)
        self.assertEqual(
            self.api.get(f'{BASE}/{en_cours.pk}/').data['statuts_suivants'],
            ['planifie', 'resolu'])

    def test_liste_sans_n_plus_1(self):
        def requetes():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.api.get(f'{BASE}/').status_code, 200)
            return len(ctx)

        # Un premier ticket : les requêtes FIXES de page (caches de contrat,
        # registre, droits, abonnés) ne partent que si la liste est non vide ;
        # on mesure donc la croissance entre 1 et 11 tickets, pas depuis 0.
        self._ticket('SAV-A43-L-base', Ticket.Statut.NOUVEAU)
        requetes()
        avant = requetes()
        for i in range(10):
            self._ticket(f'SAV-A43-L{i}', Ticket.Statut.NOUVEAU)
        self.assertLessEqual(requetes(), avant + 2)
