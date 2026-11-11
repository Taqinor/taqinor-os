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
        # AMSG11 — le gabarit validé `visite_confirmation` salue sans nom.
        self.assertIn('on confirme la visite technique', resp.data['message'])
        self.assertIn(f'/crm/appointments/{self.appt.id}/ics/', resp.data['ics_url'])
        # N'envoie RIEN : aucune notification/message n'est créée par cet appel.

    def test_le_message_client_ne_porte_aucun_lien_authentifie(self):
        # ACVI45 — le client n'ouvre pas une route JWT ; le bouton ERP garde `ics_url`.
        from urllib.parse import unquote

        resp = _api(self.user).post(
            f'/api/django/crm/appointments/{self.appt.id}/confirmer-whatsapp/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for texte in (resp.data['message'], unquote(resp.data['wa_url'])):
            self.assertNotIn('/ics/', texte)
            self.assertNotIn('/api/', texte)
        self.assertTrue(resp.data['ics_url'])

    def test_confirmation_suit_le_gabarit_et_la_langue_du_lead(self):
        # AMSG11 — gabarit société `visite_confirmation`, langue du lead, date
        # parlée du rendez-vous, `{conseiller}` = responsable du lead.
        import zoneinfo
        from urllib.parse import unquote

        from apps.crm.cadence_messages import _date_visite_francais
        from apps.parametres.models_messages import MessageTemplate

        conseiller = User.objects.create_user(
            username='vx245_owner', password='pw', company=self.company,
            role_legacy='commercial', first_name='Salma')
        self.lead.owner = conseiller
        self.lead.langue_preferee = 'darija'
        self.lead.save(update_fields=['owner', 'langue_preferee'])
        jour = _date_visite_francais(self.appt.scheduled_at.astimezone(
            zoneinfo.ZoneInfo('Africa/Casablanca')).date())
        resp = _api(self.user).post(
            f'/api/django/crm/appointments/{self.appt.id}/confirmer-whatsapp/')
        self.assertEqual(resp.status_code, 200, resp.data)
        message = resp.data['message']
        self.assertIn('كنأكدو ليكم الزيارة التقنية', message)
        self.assertIn(jour, message)
        self.assertIn('Salma', message)
        self.assertNotIn('je confirme notre rendez-vous', message)
        self.assertEqual(unquote(resp.data['wa_url']).split('text=', 1)[1], message)
        self.assertIn(f'/crm/appointments/{self.appt.id}/ics/', resp.data['ics_url'])

        # Un lead français dont la société a personnalisé le texte : il part.
        autre = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Karim',
            telephone='+212611111111', langue_preferee='fr')
        rdv = Appointment.objects.create(
            company=self.company, lead=autre,
            scheduled_at=timezone.now() + timedelta(days=2))
        MessageTemplate.objects.create(
            company=self.company, cle='visite_confirmation',
            corps_fr='Texte maison : visite {date_visite}.')
        resp = _api(self.user).post(
            f'/api/django/crm/appointments/{rdv.id}/confirmer-whatsapp/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['message'].startswith('Texte maison : visite '))

    def test_no_phone_returns_409(self):
        # ERR-ENF11-FUZZ-CRM — le numéro vient de la fiche : refus d'état.
        self.lead.telephone = ''
        self.lead.whatsapp = ''
        self.lead.save(update_fields=['telephone', 'whatsapp'])
        resp = _api(self.user).post(
            f'/api/django/crm/appointments/{self.appt.id}/confirmer-whatsapp/')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['detail'], 'Numéro de téléphone invalide.')


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
