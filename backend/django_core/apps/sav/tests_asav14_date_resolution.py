"""ASAV14 — ``date_resolution`` posée par le serveur à la résolution.

Tout chemin de résolution (action, lot, intervention terminée) pose la date
locale ; la réouverture la vide ; un PATCH ne l'écrit plus (lecture seule).

Run :
    python manage.py test apps.sav.tests_asav14_date_resolution -v2
"""
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket

User = get_user_model()
BASE = '/api/django/sav/tickets'


class DateResolutionTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav14-co', defaults={'nom': 'ASAV14 Co'})
        self.admin = User.objects.create_user(
            username='asav14_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV14')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV14',
            client=self.client_obj)
        self._n = 0

    def _ticket(self, statut):
        self._n += 1
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-ASAV14-{self._n}',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=statut, created_by=self.admin)

    def test_resoudre_pose_date(self):
        t = self._ticket(Ticket.Statut.EN_COURS)
        r = self.api.post(f'{BASE}/{t.pk}/resoudre/')
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual(t.date_resolution, timezone.localdate())

    def test_lot_pose_date(self):
        t1 = self._ticket(Ticket.Statut.EN_COURS)
        t2 = self._ticket(Ticket.Statut.EN_COURS)
        r = self.api.post(f'{BASE}/actions-groupees/', {
            'ids': [t1.pk, t2.pk], 'operation': 'statut', 'statut': 'resolu',
        }, format='json')
        self.assertIn(r.status_code, (200, 207), r.content)
        for t in (t1, t2):
            t.refresh_from_db()
            self.assertEqual(t.statut, Ticket.Statut.RESOLU)
            self.assertEqual(t.date_resolution, timezone.localdate())

    def test_patch_ignore(self):
        t = self._ticket(Ticket.Statut.NOUVEAU)
        r = self.api.patch(f'{BASE}/{t.pk}/', {
            'date_resolution': '2026-10-01'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertIsNone(t.date_resolution)

    def test_reouverture_vide(self):
        t = self._ticket(Ticket.Statut.RESOLU)
        Ticket.objects.filter(pk=t.pk).update(
            date_resolution=date(2026, 10, 1))
        r = self.api.post(f'{BASE}/{t.pk}/reouvrir/')
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.NOUVEAU)
        self.assertIsNone(t.date_resolution)

    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_fiche_resolu_le(self, _dl):
        t = self._ticket(Ticket.Statut.EN_COURS)
        self.api.post(f'{BASE}/{t.pk}/resoudre/')
        t.refresh_from_db()
        with patch('apps.sav.pdf._html_to_pdf') as mock_pdf:
            mock_pdf.return_value = b'%PDF-fake'
            from apps.sav.pdf import fiche_synthese_ticket_pdf
            fiche_synthese_ticket_pdf(t)
            html = mock_pdf.call_args[0][0]
        self.assertIn(timezone.localdate().strftime('%d/%m/%Y'), html)
