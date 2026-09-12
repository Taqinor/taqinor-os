"""NTSRV24 — Rapport de résolution au premier contact (FCR).

Critère d'acceptation : le taux FCR se recalcule correctement en EXCLUANT
les tickets encore ouverts de la période.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv24 -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket, TicketActivity
from apps.sav.selectors import taux_resolution_premier_contact

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV24FcrTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv24', defaults={'nom': 'Sav Co NTSRV24'})
        self.admin = User.objects.create_user(
            username='ntsrv24_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV24')
        self.compteur = 0

    def _ticket(self, statut=Ticket.Statut.CLOTURE, reopen=0, echanges=0,
                company=None):
        self.compteur += 1
        company = company or self.company
        ticket = Ticket.objects.create(
            company=company, reference=f'SAV-NTSRV24-{self.compteur}',
            client=self.client_obj, statut=statut, reopen_count=reopen)
        for index in range(echanges):
            TicketActivity.objects.create(
                company=company, ticket=ticket,
                kind=TicketActivity.Kind.EMAIL,
                body=f'Échange {index}')
        return ticket

    # ── Cas nominal ──────────────────────────────────────────────────────
    def test_ticket_cloture_sans_reouverture_ni_va_et_vient_est_fcr(self):
        self._ticket(echanges=2)
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['nb_clotures'], 1)
        self.assertEqual(data['nb_fcr'], 1)
        self.assertEqual(data['taux_fcr'], 100.0)

    def test_ticket_rouvert_n_est_pas_fcr(self):
        self._ticket(reopen=1)
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['nb_fcr'], 0)
        self.assertEqual(data['taux_fcr'], 0.0)
        self.assertEqual(data['exclusions']['reouverture'], 1)

    def test_plus_d_un_aller_retour_n_est_pas_fcr(self):
        self._ticket(echanges=3)
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['nb_fcr'], 0)
        self.assertEqual(data['exclusions']['echanges_multiples'], 1)

    def test_note_interne_ne_compte_pas_comme_echange_client(self):
        ticket = self._ticket(echanges=2)
        for index in range(5):
            TicketActivity.objects.create(
                company=self.company, ticket=ticket,
                kind=TicketActivity.Kind.NOTE, body=f'Note interne {index}')
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['nb_fcr'], 1)

    def test_cumul_des_deux_defauts_compte_une_seule_exclusion(self):
        self._ticket(reopen=1, echanges=5)
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['exclusions']['reouverture'], 1)
        self.assertEqual(data['exclusions']['echanges_multiples'], 0)
        self.assertEqual(
            data['exclusions']['reouverture']
            + data['exclusions']['echanges_multiples'],
            data['nb_clotures'] - data['nb_fcr'])

    def test_taux_sur_plusieurs_tickets(self):
        self._ticket()
        self._ticket()
        self._ticket(reopen=2)
        self._ticket(echanges=4)
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['nb_clotures'], 4)
        self.assertEqual(data['nb_fcr'], 2)
        self.assertEqual(data['taux_fcr'], 50.0)

    # ── Critère d'acceptation : tickets ouverts EXCLUS ───────────────────
    def test_tickets_encore_ouverts_exclus_du_taux(self):
        self._ticket()
        self._ticket(statut=Ticket.Statut.EN_COURS)
        self._ticket(statut=Ticket.Statut.NOUVEAU)
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['nb_tickets_periode'], 3)
        self.assertEqual(data['nb_clotures'], 1)
        self.assertEqual(data['nb_non_clotures_exclus'], 2)
        # Un ticket ouvert ne doit ni gonfler ni écraser le taux.
        self.assertEqual(data['taux_fcr'], 100.0)

    def test_ticket_resolu_pas_encore_cloture_exclu(self):
        self._ticket(statut=Ticket.Statut.RESOLU)
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['nb_clotures'], 0)
        self.assertIsNone(data['taux_fcr'])

    def test_ticket_annule_exclu(self):
        ticket = self._ticket()
        ticket.annule = True
        ticket.save(update_fields=['annule'])
        data = taux_resolution_premier_contact(self.company)
        self.assertEqual(data['nb_tickets_periode'], 0)
        self.assertIsNone(data['taux_fcr'])

    def test_aucun_ticket_pas_de_division_par_zero(self):
        data = taux_resolution_premier_contact(self.company)
        self.assertIsNone(data['taux_fcr'])
        self.assertEqual(data['nb_fcr'], 0)

    # ── Période + multi-tenant ───────────────────────────────────────────
    def test_hors_periode_exclu(self):
        ancien = self._ticket()
        Ticket.objects.filter(pk=ancien.pk).update(
            date_creation=timezone.now() - timedelta(days=120))
        self._ticket(reopen=1)
        data = taux_resolution_premier_contact(
            self.company, date_debut=timezone.localdate() - timedelta(days=7))
        self.assertEqual(data['nb_clotures'], 1)
        self.assertEqual(data['taux_fcr'], 0.0)

    def test_autre_societe_jamais_melangee(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv24-b', defaults={'nom': 'Autre NTSRV24'})
        self._ticket()
        data = taux_resolution_premier_contact(autre)
        self.assertEqual(data['nb_clotures'], 0)

    # ── Endpoint ─────────────────────────────────────────────────────────
    def test_endpoint_json(self):
        self._ticket()
        self._ticket(reopen=1)
        resp = self.api.get('/api/django/sav/insights/sav-fcr/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['nb_clotures'], 2)
        self.assertEqual(data['taux_fcr'], 50.0)
        self.assertEqual(len(data['tickets']), 2)

    def test_endpoint_export_xlsx(self):
        self._ticket()
        resp = self.api.get(
            '/api/django/sav/insights/sav-fcr/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
        self.assertIn('sav-fcr.xlsx', resp['Content-Disposition'])

    def test_endpoint_date_invalide_nomme_le_champ(self):
        resp = self.api.get(
            '/api/django/sav/insights/sav-fcr/?date_debut=hier')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('date_debut', resp.json())

    def test_endpoint_refuse_au_role_normal(self):
        normal = User.objects.create_user(
            username='ntsrv24_normal', password='x', role_legacy='normal',
            company=self.company)
        resp = auth(normal).get('/api/django/sav/insights/sav-fcr/')
        self.assertEqual(resp.status_code, 403)
