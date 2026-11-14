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
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav import selectors
from apps.sav.models import SavSlaSettings, Ticket, TicketEmailThread

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

    def _creer(self, description='Onduleur en défaut.'):
        r = self.api.post(f'{BASE}/', {
            'client': self.client_obj.pk, 'priorite': 'haute',
            'type': 'correctif', 'description': description,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return Ticket.objects.get(pk=r.data['id'])

    def test_jours_ouvres_suivent_le_calendrier_societe(self):
        """ASOC80 — jours ouvrés = calendrier de la SOCIÉTÉ (jours + fériés
        de calendar_utils), plus le week-end/fériés marocains codés en dur."""
        from datetime import date

        from apps.notifications.models import Holiday, WorkingHoursConfig
        from apps.sav.services import compute_sla_reponse_due_at

        WorkingHoursConfig.objects.create(
            company=self.company, working_days=0b0111111)  # lun-sam
        Holiday.objects.create(company=self.company, date=date(2026, 11, 11),
                               nom='Armistice', recurrent_annuel=True, pays='FR')
        sla = SavSlaSettings.get(self.company)
        sla.sla_jours_ouvres = True
        sla.sla_par_priorite = {'normale': {'response': 1, 'resolution': 3}}
        sla.save()
        # Vendredi 13/11 + 1 jour ouvré = samedi 14/11 (ouvert).
        self.assertEqual(compute_sla_reponse_due_at(
            self.company, None, 'normale', date(2026, 11, 13)), date(2026, 11, 14))
        # 18/11 (férié marocain) compte ouvré ; le 11/11 (férié société) non.
        self.assertEqual(compute_sla_reponse_due_at(
            self.company, None, 'normale', date(2026, 11, 17)), date(2026, 11, 18))
        self.assertEqual(compute_sla_reponse_due_at(
            self.company, None, 'normale', date(2026, 11, 10)), date(2026, 11, 12))
        r = self.api.post(f'{BASE}/', {
            'client': self.client_obj.pk, 'priorite': 'normale',
            'type': 'correctif', 'description': 'Onduleur muet.',
            'date_ouverture': '2026-11-13'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        t = Ticket.objects.get(pk=r.data['id'])
        self.assertEqual(t.sla_reponse_due_at, date(2026, 11, 14))

    def test_pause_suit_le_calendrier_societe(self):
        """ASOC105 — la pause « en attente client » compte les jours ouvrés du
        calendrier de la SOCIÉTÉ (lun-sam ici), comme l'échéance qu'elle décale."""
        from datetime import date

        from apps.notifications.models import Holiday, WorkingHoursConfig

        WorkingHoursConfig.objects.create(
            company=self.company, working_days=0b0111111)  # lun-sam
        Holiday.objects.create(company=self.company, date=date(2026, 11, 11),
                               nom='Armistice', recurrent_annuel=True, pays='FR')
        sla = SavSlaSettings.get(self.company)
        sla.sla_jours_ouvres = True
        sla.save()
        t = Ticket.objects.create(
            company=self.company, reference='SAV-OC105', client=self.client_obj,
            type=Ticket.Type.CORRECTIF, priorite='normale',
            date_ouverture=date(2026, 11, 10), sla_due_at=date(2026, 11, 17),
            en_attente_client=True, attente_depuis=date(2026, 11, 13),
            created_by=self.admin)
        lundi = date(2026, 11, 16)
        # Vendredi 13 + samedi 14 ouvrés (dimanche 15 non) : 2 jours, pas 1.
        self.assertEqual(t._pause_en_cours_jours(today=lundi), 2)
        self.assertEqual(t.sla_due_at_effectif(today=lundi), date(2026, 11, 19))
        t.reprendre_apres_attente(today=lundi)
        t.save()
        t.refresh_from_db()
        self.assertEqual(t.jours_pause, 2)

    def test_echeance_reponse_posee(self):
        t = self._creer()
        self.assertEqual(t.sla_reponse_due_at, self.today + timedelta(days=1))
        self.assertEqual(t.sla_due_at, self.today + timedelta(days=7))

    @override_settings(ANYMAIL={'SENDINBLUE_API_KEY': 'cle-factice'},  # AMSG57 — l'e-mail part
                       EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
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

    @override_settings(ANYMAIL={},  # AMSG95 — aucun e-mail ne part : 409, rien posé
                       EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_non_operationnel_409_premiere_reponse_non_posee(self):
        t = self._creer()
        r = self.api.post(f'{BASE}/{t.pk}/repondre-email/', {
            'corps': 'Nous passons jeudi.', 'sujet': 'Votre ticket',
            'destinataire': 'asav19-client@example.invalid'}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn("rien n'est parti", r.data['detail'])
        self.assertEqual(mail.outbox, [])
        t.refresh_from_db()
        self.assertIsNone(t.date_premiere_reponse)
        self.assertFalse(TicketEmailThread.objects.filter(
            ticket=t, direction=TicketEmailThread.Direction.SORTANT).exists())

    def test_appel_et_note_visible_posent(self):
        t1 = self._creer()
        self.api.post(f'{BASE}/{t1.pk}/log-appel/', {'issue': 'joint'},
                      format='json')
        t1.refresh_from_db()
        self.assertIsNotNone(t1.date_premiere_reponse)
        # ASAV23 — second ticket : autre demande (sinon doublon 409).
        t2 = self._creer(description='Compteur muet.')
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
