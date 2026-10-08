"""ASAV19 — SLA de première réponse appliqué.

``sla_reponse_due_at`` posée à la création (même service que la résolution,
premier terme de ``days_for``) ; ``date_premiere_reponse`` posée une seule
fois par la première réponse réelle (e-mail, appel journalisé, note visible
client), jamais par une note interne ; ``premiere_reponse_respectee``.

Run :
    python manage.py test apps.sav.tests_asav19_sla_reponse -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav import selectors
from apps.sav.models import SavSlaSettings, Ticket

User = get_user_model()
BASE = '/api/django/sav/tickets'


class SlaReponseTests(TestCase):

    def setUp(self):
        self.today = timezone.localdate()
        self.company, _ = Company.objects.get_or_create(
            slug='asav19-co', defaults={'nom': 'ASAV19 Co'})
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_jours_ouvres = False
        sla.sla_par_priorite = {'haute': {'response': 1, 'resolution': 7}}
        sla.save()
        self.admin = User.objects.create_user(
            username='asav19_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV19',
            email='asav19-client@example.invalid')

    def _creer(self):
        r = self.api.post(f'{BASE}/', {
            'client': self.client_obj.pk, 'priorite': 'haute',
            'type': 'correctif', 'description': 'Onduleur en défaut.',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return Ticket.objects.get(pk=r.data['id'])

    def test_echeance_reponse_posee(self):
        t = self._creer()
        self.assertEqual(t.sla_reponse_due_at, self.today + timedelta(days=1))
        self.assertEqual(t.sla_due_at, self.today + timedelta(days=7))

    def test_email_pose_premiere_reponse(self):
        t = self._creer()
        r = self.api.post(f'{BASE}/{t.pk}/repondre-email/', {
            'corps': 'Nous passons jeudi.', 'sujet': 'Votre ticket',
            'destinataire': 'asav19-client@example.invalid'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        t.refresh_from_db()
        self.assertIsNotNone(t.date_premiere_reponse)
        premiere = t.date_premiere_reponse
        # Une seule fois : une seconde réponse ne la déplace pas.
        self.api.post(f'{BASE}/{t.pk}/log-appel/', {
            'issue': 'joint'}, format='json')
        t.refresh_from_db()
        self.assertEqual(t.date_premiere_reponse, premiere)

    def test_appel_et_note_visible_posent(self):
        t1 = self._creer()
        self.api.post(f'{BASE}/{t1.pk}/log-appel/', {'issue': 'joint'},
                      format='json')
        t1.refresh_from_db()
        self.assertIsNotNone(t1.date_premiere_reponse)
        t2 = self._creer()
        self.api.post(f'{BASE}/{t2.pk}/noter/', {
            'body': 'Pièce commandée.', 'visible_client': True},
            format='json')
        t2.refresh_from_db()
        self.assertIsNotNone(t2.date_premiere_reponse)

    def test_note_interne_ne_pose_pas(self):
        t = self._creer()
        r = self.api.post(f'{BASE}/{t.pk}/noter/', {
            'body': 'Note interne.'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        t.refresh_from_db()
        self.assertIsNone(t.date_premiere_reponse)
        res = selectors.file_action(self.company, today=self.today)
        self.assertIn(t.id, res['buckets']['a_repondre']['ids'])

    def test_respect_reponse(self):
        t = self._creer()
        self.assertIsNone(selectors.premiere_reponse_respectee(t))
        Ticket.objects.filter(pk=t.pk).update(
            date_premiere_reponse=timezone.now())
        t.refresh_from_db()
        self.assertTrue(selectors.premiere_reponse_respectee(t))
        Ticket.objects.filter(pk=t.pk).update(
            date_premiere_reponse=timezone.now() + timedelta(days=6))
        t.refresh_from_db()
        self.assertFalse(selectors.premiere_reponse_respectee(t))
        res = selectors.file_action(self.company, today=self.today)
        self.assertNotIn(t.id, res['buckets']['a_repondre']['ids'])
