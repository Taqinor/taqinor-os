"""NTSRV31 — Création d'un Problème depuis un regroupement suggéré.

Critère d'acceptation : décocher un ticket dans l'assistant l'exclut BIEN du
problème créé — la moitié serveur ne rattache QUE les ids reçus, jamais « tout
le groupe » implicitement, et le tout part en un seul appel transactionnel.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv31 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Probleme, ProblemeIncident, Ticket, TicketActivity

User = get_user_model()

URL = '/api/django/sav/problemes/creer-depuis-regroupement/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV31CreerDepuisRegroupementTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv31', defaults={'nom': 'Sav Co NTSRV31'})
        self.admin = User.objects.create_user(
            username='ntsrv31_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV31')
        self.tickets = [
            Ticket.objects.create(
                company=self.company, reference=f'SAV-NTSRV31-{i}',
                client=self.client_obj, statut=Ticket.Statut.EN_COURS)
            for i in range(1, 4)
        ]

    def test_cree_le_probleme_et_rattache_les_tickets_coches(self):
        resp = self.api.post(URL, {
            'titre': 'Onduleur X — Surchauffe',
            'cause_racine': 'Lot de condensateurs',
            'ticket_ids': [self.tickets[0].pk, self.tickets[1].pk],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertTrue(data['reference'].startswith('PRB-'))
        self.assertEqual(data['nb_tickets'], 2)
        probleme = Probleme.objects.get(pk=data['id'])
        self.assertEqual(probleme.cause_racine, 'Lot de condensateurs')
        self.assertEqual(
            set(probleme.tickets.values_list('pk', flat=True)),
            {self.tickets[0].pk, self.tickets[1].pk})

    def test_ticket_decoche_reellement_exclu(self):
        resp = self.api.post(URL, {
            'titre': 'Onduleur X — Surchauffe',
            'ticket_ids': [self.tickets[0].pk],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        probleme = Probleme.objects.get(pk=resp.json()['id'])
        self.assertEqual(probleme.incidents.count(), 1)
        self.assertFalse(ProblemeIncident.objects.filter(
            probleme=probleme, ticket=self.tickets[2]).exists())

    def test_chaque_ticket_rattache_est_trace_dans_son_chatter(self):
        resp = self.api.post(URL, {
            'titre': 'Onduleur X — Surchauffe',
            'ticket_ids': [self.tickets[0].pk, self.tickets[1].pk],
        }, format='json')
        reference = resp.json()['reference']
        for ticket in self.tickets[:2]:
            note = TicketActivity.objects.filter(
                ticket=ticket, kind=TicketActivity.Kind.NOTE).latest('id')
            self.assertIn(reference, note.body)
        self.assertFalse(TicketActivity.objects.filter(
            ticket=self.tickets[2],
            kind=TicketActivity.Kind.NOTE).exists())

    def test_statut_des_tickets_jamais_touche(self):
        self.api.post(URL, {
            'titre': 'Onduleur X — Surchauffe',
            'ticket_ids': [t.pk for t in self.tickets],
        }, format='json')
        for ticket in self.tickets:
            ticket.refresh_from_db()
            self.assertEqual(ticket.statut, Ticket.Statut.EN_COURS)

    # ── Refus : tout ou rien ─────────────────────────────────────────────
    def test_titre_vide_refuse_en_nommant_le_champ(self):
        resp = self.api.post(URL, {
            'titre': '  ', 'ticket_ids': [self.tickets[0].pk],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('titre', resp.json())
        self.assertEqual(Probleme.objects.count(), 0)

    def test_aucun_ticket_refuse(self):
        resp = self.api.post(URL, {
            'titre': 'Sans ticket', 'ticket_ids': [],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ticket_ids', resp.json())
        self.assertEqual(Probleme.objects.count(), 0)

    def test_ticket_d_une_autre_societe_annule_toute_la_creation(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv31-b', defaults={'nom': 'Autre NTSRV31'})
        client_etranger = Client.objects.create(
            company=autre, nom='Étranger', prenom='X')
        etranger = Ticket.objects.create(
            company=autre, reference='SAV-NTSRV31-ETR',
            client=client_etranger)
        resp = self.api.post(URL, {
            'titre': 'Tentative',
            'ticket_ids': [self.tickets[0].pk, etranger.pk],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ticket_ids', resp.json())
        # TOUT OU RIEN : aucun problème, aucun rattachement.
        self.assertEqual(Probleme.objects.count(), 0)
        self.assertEqual(ProblemeIncident.objects.count(), 0)

    def test_ticket_ids_non_numeriques_refuses(self):
        resp = self.api.post(URL, {
            'titre': 'Tentative', 'ticket_ids': ['abc'],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ticket_ids', resp.json())

    def test_role_normal_refuse(self):
        normal = User.objects.create_user(
            username='ntsrv31_normal', password='x', role_legacy='normal',
            company=self.company)
        resp = auth(normal).post(URL, {
            'titre': 'Tentative', 'ticket_ids': [self.tickets[0].pk],
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Probleme.objects.count(), 0)
