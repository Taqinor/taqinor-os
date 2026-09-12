"""NTSRV23 — Enquête CSAT enrichie multi-question (sous-notes optionnelles).

Critère d'acceptation : le formulaire public reste INCHANGÉ tant que le
drapeau ``SavSlaSettings.csat_detaille_actif`` est OFF.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv23 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import SavSlaSettings, Ticket, TicketSatisfaction

User = get_user_model()


class NTSRV23CsatDetailleTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv23', defaults={'nom': 'Sav Co NTSRV23'})
        self.admin = User.objects.create_user(
            username='ntsrv23_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV23')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV23-1',
            client=self.client_obj, statut=Ticket.Statut.RESOLU)
        self.ticket.ensure_share_token()
        self.public_api = APIClient()

    def _url(self, token=None):
        token = token or self.ticket.share_token
        return f'/api/django/public/sav/ticket/{token}/satisfaction/'

    def _statut_url(self):
        return f'/api/django/public/sav/ticket/{self.ticket.share_token}/'

    def _activer(self):
        reglages = SavSlaSettings.get(self.company)
        reglages.csat_detaille_actif = True
        reglages.save(update_fields=['csat_detaille_actif'])
        return reglages

    # ── Drapeau OFF : rien ne change ─────────────────────────────────────
    def test_defaut_off(self):
        self.assertFalse(SavSlaSettings.get(self.company).csat_detaille_actif)

    def test_page_publique_annonce_off_par_defaut(self):
        resp = self.public_api.get(self._statut_url())
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.json()['csat_detaille_actif'])

    def test_formulaire_simple_inchange_quand_off(self):
        resp = self.public_api.post(
            self._url(), {'note': 5, 'commentaire': 'Parfait'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        satisfaction = TicketSatisfaction.objects.get(ticket=self.ticket)
        self.assertEqual(satisfaction.note, 5)
        self.assertIsNone(satisfaction.sous_notes)

    def test_sous_notes_ignorees_quand_off(self):
        resp = self.public_api.post(
            self._url(),
            {'note': 4, 'sous_notes': {'rapidite': 5}}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNone(
            TicketSatisfaction.objects.get(ticket=self.ticket).sous_notes)

    # ── Drapeau ON : les sous-notes sont collectées ──────────────────────
    def test_page_publique_annonce_on(self):
        self._activer()
        resp = self.public_api.get(self._statut_url())
        self.assertTrue(resp.json()['csat_detaille_actif'])

    def test_sous_notes_enregistrees_quand_on(self):
        self._activer()
        resp = self.public_api.post(
            self._url(),
            {'note': 4,
             'sous_notes': {'rapidite': 5, 'courtoisie': 4, 'resolution': 3}},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        satisfaction = TicketSatisfaction.objects.get(ticket=self.ticket)
        self.assertEqual(satisfaction.note, 4)
        self.assertEqual(
            satisfaction.sous_notes,
            {'rapidite': 5, 'courtoisie': 4, 'resolution': 3})

    def test_note_globale_reste_la_seule_obligatoire(self):
        self._activer()
        resp = self.public_api.post(self._url(), {'note': 5}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNone(
            TicketSatisfaction.objects.get(ticket=self.ticket).sous_notes)

    def test_sous_notes_partielles_acceptees(self):
        self._activer()
        resp = self.public_api.post(
            self._url(), {'note': 5, 'sous_notes': {'courtoisie': 5}},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            TicketSatisfaction.objects.get(ticket=self.ticket).sous_notes,
            {'courtoisie': 5})

    def test_sans_note_globale_toujours_refuse(self):
        self._activer()
        resp = self.public_api.post(
            self._url(), {'sous_notes': {'rapidite': 5}}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            TicketSatisfaction.objects.filter(ticket=self.ticket).exists())

    # ── Validation : messages FRANÇAIS qui nomment la sous-note ──────────
    def test_sous_note_hors_bornes_nomme_la_sous_note(self):
        self._activer()
        resp = self.public_api.post(
            self._url(), {'note': 5, 'sous_notes': {'rapidite': 9}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Rapidité', resp.json()['detail'])
        self.assertFalse(
            TicketSatisfaction.objects.filter(ticket=self.ticket).exists())

    def test_sous_note_inconnue_refusee(self):
        self._activer()
        resp = self.public_api.post(
            self._url(), {'note': 5, 'sous_notes': {'prix': 3}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('prix', resp.json()['detail'])

    def test_sous_notes_non_objet_refusees(self):
        self._activer()
        resp = self.public_api.post(
            self._url(), {'note': 5, 'sous_notes': 'très bien'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    # ── Back-office : lecture seule ──────────────────────────────────────
    def test_reglage_expose_en_back_office(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        resp = api.get('/api/django/sav/sla-settings/')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Singleton : `list` renvoie l'objet, pas une liste.
        self.assertIs(resp.json()['csat_detaille_actif'], False)
