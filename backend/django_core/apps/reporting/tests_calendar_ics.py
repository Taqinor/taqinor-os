"""FG6 — flux ICS/iCal par utilisateur (abonnement Google/Outlook).

Authentifié par jeton signé (sans session), borné à la société + à
l'utilisateur résolu du jeton. Vérifie : jeton valide → text/calendar avec
VEVENT, jeton absent/invalide → 404 neutre (ASEC45), isolation société,
isolation utilisateur.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.reporting.calendar import make_ics_token
from authentication.models import Company

User = get_user_model()


class TestCalendarIcs(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ics-co', defaults={'nom': 'ICS Co'})[0]
        self.other = Company.objects.create(slug='ics-other', nom='Autre')
        self.user = User.objects.create_user(
            username='ics_user', password='x', role_legacy='responsable',
            company=self.company)
        self.other_user = User.objects.create_user(
            username='ics_other', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client A')
        self.api = APIClient()
        # Le flux .ics est anonyme (jeton) ; la souscription est par session.
        self.token = make_ics_token(self.user)

    def _chantier(self, **kw):
        return Installation.objects.create(
            company=self.company, reference=kw.pop('reference', 'CH-1'),
            client=self.client_obj, **kw)

    def test_valid_token_returns_calendar_with_vevents(self):
        soon = date.today() + timedelta(days=5)
        self._chantier(reference='CH-ICS',
                       date_pose_prevue=soon,
                       technicien_responsable=self.user)
        resp = self.api.get(f'/api/django/reporting/calendar.ics?token={self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp['Content-Type'].startswith('text/calendar'))
        body = resp.content.decode('utf-8')
        self.assertIn('BEGIN:VCALENDAR', body)
        self.assertIn('END:VCALENDAR', body)
        self.assertIn('BEGIN:VEVENT', body)
        self.assertIn('SUMMARY:Pose', body)

    def test_flux_sans_a_faire_de_lead_archive(self):
        """ASUP45 — l'agenda du téléphone et l'écran Calendrier ne servent plus
        l'à-faire d'un lead archivé ou supprimé ; celui d'un lead actif reste."""
        from django.contrib.contenttypes.models import ContentType
        from apps.crm.models import Lead
        from apps.records.models import Activity
        ct = ContentType.objects.get_for_model(Lead)
        soon = date.today() + timedelta(days=2)
        for nom in ('ARCHIVE', 'SUPPRIME', 'ACTIF'):
            lead = Lead.objects.create(company=self.company, nom=nom, is_archived=nom == 'ARCHIVE')
            Activity.objects.create(company=self.company, content_type=ct, object_id=lead.pk,
                                    summary=f'Rappeler {nom}', assigned_to=self.user, due_date=soon)
            if nom == 'SUPPRIME':
                lead.soft_delete()
        body = self.api.get(f'/api/django/reporting/calendar.ics?token={self.token}').content.decode('utf-8')
        self.assertIn('Rappeler ACTIF', body)
        self.assertNotIn('Rappeler ARCHIVE', body)
        self.assertNotIn('Rappeler SUPPRIME', body)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = self.api.get('/api/django/reporting/calendar/', {
            'from': date.today().isoformat(), 'to': (soon + timedelta(days=1)).isoformat(), 'types': 'activite'})
        self.assertEqual(resp.status_code, 200, resp.content)
        titres = [e['title'] for e in (resp.data.get('events') if isinstance(resp.data, dict) else resp.data)]
        self.assertEqual(titres, ['Rappeler ACTIF'])

    def test_missing_token_unauthorized(self):
        resp = self.api.get('/api/django/reporting/calendar.ics')
        # ASEC45 — réponse neutre unique pour tout lien inutilisable.
        self.assertEqual(resp.status_code, 404)

    def test_bad_token_unauthorized(self):
        resp = self.api.get(
            '/api/django/reporting/calendar.ics?token=not-a-real-token')
        self.assertEqual(resp.status_code, 404)

    def test_only_token_users_events_appear(self):
        soon = date.today() + timedelta(days=4)
        # Pose assignée à l'autre utilisateur (même société) : ne doit PAS
        # apparaître dans le flux de self.user.
        self._chantier(reference='CH-MINE', date_pose_prevue=soon,
                       technicien_responsable=self.user)
        self._chantier(reference='CH-THEIRS', date_pose_prevue=soon,
                       technicien_responsable=self.other_user)
        resp = self.api.get(
            f'/api/django/reporting/calendar.ics?token={self.token}')
        body = resp.content.decode('utf-8')
        self.assertIn('CH-MINE', body)
        self.assertNotIn('CH-THEIRS', body)

    def test_company_isolation(self):
        soon = date.today() + timedelta(days=6)
        # Chantier d'une autre société, même nom de technicien-id impossible :
        # on crée un technicien dans l'autre société et lui assigne la pose.
        other_tech = User.objects.create_user(
            username='ics_cross', password='x', role_legacy='responsable',
            company=self.other)
        Installation.objects.create(
            company=self.other, reference='CH-CROSS',
            client=Client.objects.create(company=self.other, nom='B'),
            date_pose_prevue=soon, technicien_responsable=other_tech)
        # Le flux de self.user (société ICS Co) ne doit jamais voir CH-CROSS.
        resp = self.api.get(
            f'/api/django/reporting/calendar.ics?token={self.token}')
        self.assertNotIn('CH-CROSS', resp.content.decode('utf-8'))

    def test_intervention_in_feed(self):
        soon = date.today() + timedelta(days=3)
        inst = self._chantier(reference='CH-IV',
                              technicien_responsable=self.user)
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='depannage', date_prevue=soon,
            technicien=self.user)
        resp = self.api.get(
            f'/api/django/reporting/calendar.ics?token={self.token}')
        body = resp.content.decode('utf-8')
        self.assertIn('BEGIN:VEVENT', body)
        self.assertIn('UID:intervention-', body)

    def test_subscription_endpoint_returns_url(self):
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = self.api.get('/api/django/reporting/calendar/subscription/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertIn('calendar.ics?token=', resp.data['url'])

    def test_subscription_requires_auth(self):
        bare = APIClient()
        resp = bare.get('/api/django/reporting/calendar/subscription/')
        self.assertIn(resp.status_code, (401, 403))

    def test_inactive_user_token_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        resp = self.api.get(
            f'/api/django/reporting/calendar.ics?token={self.token}')
        self.assertEqual(resp.status_code, 404)
