"""NTSRV5 — Trace structurée d'un appel SAV (click-to-call, sans PBX).

Critère d'acceptation : un appel loggé apparaît dans le chatter avec sa DURÉE
et son ISSUE, et il est filtrable en rapport (``selectors.journal_appels``).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv5 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket, TicketActivity
from apps.sav.selectors import journal_appels

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV5LogAppelTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv5', defaults={'nom': 'Sav Co NTSRV5'})
        self.user = User.objects.create_user(
            username='ntsrv5_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV5')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV5-1',
            client=self.client_obj, created_by=self.user)
        self.api = auth(self.user)

    def _url(self):
        return f'/api/django/sav/tickets/{self.ticket.pk}/log-appel/'

    def test_appel_logge_apparait_au_chatter_avec_duree_et_issue(self):
        resp = self.api.post(self._url(), {
            'duree_minutes': 7, 'issue': 'joint',
            'notes': 'Client rassuré, intervention mardi.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        entree = TicketActivity.objects.get(kind=TicketActivity.Kind.APPEL)
        self.assertEqual(entree.duree_minutes, 7)
        self.assertEqual(entree.outcome, 'joint')
        self.assertEqual(entree.user, self.user)
        self.assertEqual(entree.company, self.company)
        self.assertIn('7 min', entree.body)
        self.assertIn('Joint', entree.body)
        self.assertIn('Client rassuré', entree.body)

    def test_issue_vide_acceptee(self):
        resp = self.api.post(self._url(), {'duree_minutes': 2}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            TicketActivity.objects.get(kind=TicketActivity.Kind.APPEL).outcome,
            '')

    def test_issue_inconnue_refusee_en_nommant_le_champ(self):
        resp = self.api.post(self._url(), {'issue': 'bizarre'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('issue', resp.json())
        self.assertFalse(TicketActivity.objects.filter(
            kind=TicketActivity.Kind.APPEL).exists())

    def test_duree_invalide_refusee_en_nommant_le_champ(self):
        for mauvaise in ('abc', -3):
            resp = self.api.post(self._url(), {'duree_minutes': mauvaise},
                                 format='json')
            self.assertEqual(resp.status_code, 400, mauvaise)
            self.assertIn('duree_minutes', resp.json())

    def test_issues_identiques_a_la_liste_crm(self):
        """La liste d'issues SAV recopie celle de ``crm.LeadActivity`` (FG30)."""
        self.assertEqual(
            [code for code, _ in TicketActivity.OUTCOMES],
            ['', 'joint', 'non_joint', 'rappel', 'refuse', 'interesse'])

    def test_journal_appels_filtrable(self):
        self.api.post(self._url(), {'duree_minutes': 3, 'issue': 'joint'},
                      format='json')
        self.api.post(self._url(), {'duree_minutes': 1, 'issue': 'non_joint'},
                      format='json')
        tous = journal_appels(self.company)
        self.assertEqual(len(tous), 2)
        joints = journal_appels(self.company, issue='joint')
        self.assertEqual(len(joints), 1)
        self.assertEqual(joints[0]['duree_minutes'], 3)
        self.assertEqual(joints[0]['issue_label'], 'Joint')
        self.assertEqual(joints[0]['ticket_reference'], 'SAV-NTSRV5-1')
        self.assertEqual(
            journal_appels(self.company, technicien_id=self.user.pk + 999), [])

    def test_journal_appels_scope_par_societe(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv5-b', defaults={'nom': 'Autre'})
        self.api.post(self._url(), {'duree_minutes': 3, 'issue': 'joint'},
                      format='json')
        self.assertEqual(journal_appels(autre), [])

    def test_canal_ouverture_telephone_disponible(self):
        self.assertIn(
            ('telephone', 'Téléphone'), Ticket.CanalOuverture.choices)
        self.ticket.canal_ouverture = Ticket.CanalOuverture.TELEPHONE
        self.ticket.save(update_fields=['canal_ouverture'])
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.canal_ouverture, 'telephone')
