"""ACRM23 (C-ACRM-016) — annuler, déplacer ou supprimer un rendez-vous se
lit au chatter du lead, et un déplacement réarme le rappel.

Sonde V_VA LVIEW2-3 : chatter 8 → 8 → 8 après annulation, déplacement et
suppression ; ``reminder_sent`` restait vrai après le déplacement (le
nouveau rendez-vous n'était jamais rappelé).

API réelle (``AppointmentViewSet``) ; aucun mock.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Appointment, Lead, LeadActivity

User = get_user_model()
URL = '/api/django/crm/appointments/'


class RdvTraceTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM23 Solaire', slug='acrm23-rdv')
        self.user = User.objects.create_user(
            username='acrm23-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Visite', owner=self.user,
            telephone='+212661232323')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        quand = (timezone.now() + datetime.timedelta(days=3)).isoformat()
        resp = self.api.post(URL, {'lead': self.lead.pk,
                                   'scheduled_at': quand}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.rdv = Appointment.objects.get(pk=resp.data['id'])
        Appointment.objects.filter(pk=self.rdv.pk).update(reminder_sent=True)

    def _notes(self):
        return list(LeadActivity.objects.filter(
            lead=self.lead, body__startswith=f'RDV #{self.rdv.pk}'
        ).values_list('body', flat=True))

    def test_annulation_tracee(self):
        resp = self.api.patch(f'{URL}{self.rdv.pk}/', {'statut': 'annule'},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        notes = self._notes()
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('Planifié → Annulé', notes[0])
        self.assertIn('acrm23-resp', notes[0])

    def test_deplacement_trace_et_rappel_rearme(self):
        nouveau = (timezone.now() + datetime.timedelta(days=6)).isoformat()
        resp = self.api.patch(f'{URL}{self.rdv.pk}/',
                              {'scheduled_at': nouveau, 'statut': 'planifie'},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        notes = self._notes()
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('déplacé du', notes[0])
        self.rdv.refresh_from_db()
        self.assertFalse(self.rdv.reminder_sent)

    def test_suppression_tracee(self):
        resp = self.api.delete(f'{URL}{self.rdv.pk}/')
        self.assertIn(resp.status_code, (200, 204), resp.content)
        notes = self._notes()
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('supprimé', notes[0])

    def test_patch_sans_changement_muet(self):
        resp = self.api.patch(f'{URL}{self.rdv.pk}/',
                              {'statut': self.rdv.statut}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self._notes(), [])
