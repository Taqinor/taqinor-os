"""VX245 — le cycle client sortant se boucle : `.ics` d'événement unique pour
un rendez-vous (VX245(a)) + confirmation WhatsApp post-RDV avec lien `.ics`
(VX245(b)). Le générateur ICS `.ics` réutilise `reporting.calendar.build_ics`
(jamais une 2ᵉ implémentation) ; le message WhatsApp n'envoie RIEN — un
aperçu seulement, jamais un lien wa.me auto-ouvert côté serveur.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Appointment, Lead
from authentication.models import Company

User = get_user_model()


def _company(name='VX245 Co'):
    return Company.objects.create(nom=name)


def _responsable(company, username='vx245_resp'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Vx245AppointmentIcsTests(TestCase):

    def setUp(self):
        self.company = _company('VX245 ICS Co')
        self.user = _responsable(self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Youssef',
            telephone='+212612345678')
        self.appt = Appointment.objects.create(
            company=self.company, lead=self.lead,
            scheduled_at=timezone.now() + timedelta(days=2))

    def test_ics_download_is_valid_single_vevent(self):
        resp = _api(self.user).get(
            f'/api/django/crm/appointments/{self.appt.id}/ics/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp['Content-Type'], 'text/calendar; charset=utf-8')
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('BEGIN:VCALENDAR', body)
        self.assertIn('BEGIN:VEVENT', body)
        self.assertEqual(body.count('BEGIN:VEVENT'), 1)
        self.assertIn(f'UID:appointment-{self.appt.id}@taqinor', body)
        self.assertIn('DTSTART:', body)
        self.assertIn('DTEND:', body)
        self.assertIn('Bennani', body)
        self.assertIn('END:VCALENDAR', body)

    def test_ics_of_another_company_is_404(self):
        other_company = _company('VX245 ICS Co 2')
        other_user = _responsable(other_company, 'vx245_resp_outsider')
        resp = _api(other_user).get(
            f'/api/django/crm/appointments/{self.appt.id}/ics/')
        self.assertEqual(resp.status_code, 404)


class Vx245ConfirmationWhatsAppTests(TestCase):

    def setUp(self):
        self.company = _company('VX245 WA Co')
        self.user = _responsable(self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Youssef',
            telephone='+212612345678')
        self.appt = Appointment.objects.create(
            company=self.company, lead=self.lead,
            scheduled_at=timezone.now() + timedelta(days=2))

    def test_confirmer_whatsapp_previews_message_with_ics_link(self):
        resp = _api(self.user).post(
            f'/api/django/crm/appointments/{self.appt.id}/confirmer-whatsapp/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['wa_url'].startswith('https://wa.me/'))
        self.assertIn('Bennani', resp.data['message'])
        self.assertIn(resp.data['ics_url'], resp.data['message'])
        self.assertIn(f'/crm/appointments/{self.appt.id}/ics/', resp.data['ics_url'])
        # N'envoie RIEN : aucune notification/message n'est créée par cet appel.

    def test_no_phone_returns_400(self):
        self.lead.telephone = ''
        self.lead.whatsapp = ''
        self.lead.save(update_fields=['telephone', 'whatsapp'])
        resp = _api(self.user).post(
            f'/api/django/crm/appointments/{self.appt.id}/confirmer-whatsapp/')
        self.assertEqual(resp.status_code, 400)


class Vx245ClientDocumentsStatutKeyTests(TestCase):
    """VX245(c) — `statut_key` RAW (additif) exposé pour les factures, pour
    que « Relancer par WhatsApp » se gate sur le statut réel (jamais le
    libellé FR affiché)."""

    def test_facture_en_retard_exposes_statut_key(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture

        company = _company('VX245 Docs Co')
        user = _responsable(company)
        client = Client.objects.create(company=company, nom='Client VX245')
        Facture.objects.create(
            company=company, reference='FAC-VX245-1', client=client,
            statut='en_retard')

        resp = _api(user).get(f'/api/django/crm/clients/{client.id}/documents/')
        self.assertEqual(resp.status_code, 200, resp.data)
        facture = resp.data['factures'][0]
        self.assertEqual(facture['statut_key'], 'en_retard')
