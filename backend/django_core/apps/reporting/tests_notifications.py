"""N75 — moteur de notifications in-app unifié + préférences par utilisateur."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()


class TestUnifiedNotifications(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='notif2-co', defaults={'nom': 'Notif2 Co'})[0]
        self.user = User.objects.create_user(
            username='notif2_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(company=self.company, nom='C')
        # Un ticket SAV ouvert → catégorie tickets_ouverts.
        Ticket.objects.create(
            company=self.company, reference='SAV-NOTIF-1', client=self.client_obj,
            statut=Ticket.Statut.NOUVEAU)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_new_categories_present_and_counted(self):
        resp = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(resp.status_code, 200)
        for key in ('chantiers_a_planifier', 'maintenance_due',
                    'tickets_ouverts', 'stock_bas', 'preferences'):
            self.assertIn(key, resp.data)
        self.assertEqual(len(resp.data['tickets_ouverts']), 1)
        self.assertGreaterEqual(resp.data['total'], 1)

    def test_preference_disables_category(self):
        # Désactiver les tickets ouverts → la catégorie disparaît du décompte.
        before = self.api.get('/api/django/reporting/notifications/').data['total']
        up = self.api.post('/api/django/reporting/notification-preferences/',
                           {'event_type': 'tickets_ouverts', 'in_app': False},
                           format='json')
        self.assertEqual(up.status_code, 200)
        after = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(after.data['tickets_ouverts'], [])
        self.assertEqual(after.data['total'], before - 1)
        self.assertFalse(after.data['preferences']['tickets_ouverts'])

    def test_preferences_endpoint_lists_all_with_defaults(self):
        resp = self.api.get('/api/django/reporting/notification-preferences/')
        self.assertEqual(resp.status_code, 200)
        prefs = {p['event_type']: p for p in resp.data['preferences']}
        self.assertIn('stock_bas', prefs)
        # Défaut = activé tant qu'aucune préférence n'est posée.
        self.assertTrue(prefs['stock_bas']['in_app'])

    def test_unknown_event_type_rejected(self):
        resp = self.api.post('/api/django/reporting/notification-preferences/',
                             {'event_type': 'inexistant', 'in_app': False},
                             format='json')
        self.assertEqual(resp.status_code, 400)
