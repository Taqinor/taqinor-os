"""NTSRV8 — File d'attente par équipe avec débordement PROPOSÉ.

Critère d'acceptation : le débordement est une PROPOSITION visible en liste,
JAMAIS une réaffectation silencieuse — appeler la lecture ne change aucune
équipe ; seul ``tickets/{id}/reaffecter-equipe/`` écrit.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv8 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import EquipeMaintenance, Ticket, TicketActivity
from apps.sav.selectors import charge_equipe, file_attente_equipe
from apps.sav.services import debordement_equipe

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV8FileAttenteTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv8', defaults={'nom': 'Sav Co NTSRV8'})
        self.admin = User.objects.create_user(
            username='ntsrv8_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV8')
        self.equipe = EquipeMaintenance.objects.create(
            company=self.company, nom='Équipe A',
            capacite_max_tickets_ouverts=2)
        self.equipe_b = EquipeMaintenance.objects.create(
            company=self.company, nom='Équipe B')
        self.tickets = [
            Ticket.objects.create(
                company=self.company, reference=f'SAV-NTSRV8-{i}',
                client=self.client_obj, equipe=self.equipe,
                statut=Ticket.Statut.NOUVEAU,
                date_ouverture=f'2026-0{i}-01')
            for i in range(1, 5)
        ]

    # ── File d'attente ───────────────────────────────────────────────────
    def test_file_triee_du_plus_ancien_au_plus_recent(self):
        file_attente = list(file_attente_equipe(self.equipe))
        self.assertEqual([t.reference for t in file_attente],
                         [t.reference for t in self.tickets])

    def test_ticket_deja_affecte_sort_de_la_file(self):
        self.tickets[0].technicien_responsable = self.admin
        self.tickets[0].save(update_fields=['technicien_responsable'])
        self.assertEqual(len(file_attente_equipe(self.equipe)), 3)
        # …mais il compte toujours dans la CHARGE de l'équipe.
        self.assertEqual(charge_equipe(self.equipe), 4)

    def test_ticket_clos_ou_annule_hors_file(self):
        self.tickets[0].statut = Ticket.Statut.CLOTURE
        self.tickets[0].save(update_fields=['statut'])
        self.tickets[1].annule = True
        self.tickets[1].save(update_fields=['annule'])
        self.assertEqual(len(file_attente_equipe(self.equipe)), 2)
        self.assertEqual(charge_equipe(self.equipe), 2)

    # ── Débordement : PROPOSITION seulement ──────────────────────────────
    def test_debordement_propose_sans_rien_ecrire(self):
        proposition = debordement_equipe(self.equipe)
        self.assertEqual(proposition['charge'], 4)
        self.assertEqual(proposition['capacite'], 2)
        self.assertEqual(proposition['excedent'], 2)
        self.assertEqual(proposition['equipe_cible_id'], self.equipe_b.pk)
        self.assertEqual(len(proposition['tickets_proposes']), 2)
        # RIEN n'a bougé : aucune réaffectation silencieuse.
        for ticket in self.tickets:
            ticket.refresh_from_db()
            self.assertEqual(ticket.equipe, self.equipe)

    def test_les_plus_recents_sont_proposes(self):
        proposes = [t['reference']
                    for t in debordement_equipe(self.equipe)['tickets_proposes']]
        self.assertEqual(proposes, ['SAV-NTSRV8-4', 'SAV-NTSRV8-3'])

    def test_sans_capacite_declaree_aucun_debordement(self):
        self.equipe.capacite_max_tickets_ouverts = None
        self.equipe.save(update_fields=['capacite_max_tickets_ouverts'])
        proposition = debordement_equipe(self.equipe)
        self.assertEqual(proposition['excedent'], 0)
        self.assertEqual(proposition['tickets_proposes'], [])

    def test_sous_la_capacite_aucun_debordement(self):
        self.equipe.capacite_max_tickets_ouverts = 10
        self.equipe.save(update_fields=['capacite_max_tickets_ouverts'])
        self.assertEqual(debordement_equipe(self.equipe)['excedent'], 0)

    def test_equipe_cible_saturee_ecartee(self):
        # Équipe B saturée : capacité 1 pour 1 ticket ouvert.
        self.equipe_b.capacite_max_tickets_ouverts = 1
        self.equipe_b.save(update_fields=['capacite_max_tickets_ouverts'])
        Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV8-B1',
            client=self.client_obj, equipe=self.equipe_b)
        proposition = debordement_equipe(self.equipe)
        self.assertEqual(proposition['excedent'], 2)
        self.assertIsNone(proposition['equipe_cible_id'],
                          'on ne déplace pas le problème vers une équipe saturée')

    # ── Endpoints ────────────────────────────────────────────────────────
    def test_endpoint_file_attente(self):
        resp = self.api.get('/api/django/sav/file-attente/')
        self.assertEqual(resp.status_code, 200, resp.content)
        lignes = {ligne['equipe_nom']: ligne for ligne in resp.json()['results']}
        self.assertEqual(lignes['Équipe A']['charge'], 4)
        self.assertEqual(lignes['Équipe A']['debordement']['excedent'], 2)
        self.assertEqual(lignes['Équipe B']['debordement']['excedent'], 0)
        self.assertEqual(len(lignes['Équipe A']['file_attente']), 4)

    def test_endpoint_file_attente_ne_reaffecte_rien(self):
        self.api.get('/api/django/sav/file-attente/')
        for ticket in self.tickets:
            ticket.refresh_from_db()
            self.assertEqual(ticket.equipe, self.equipe)

    def test_reaffecter_equipe_est_explicite_et_trace(self):
        ticket = self.tickets[3]
        resp = self.api.post(
            f'/api/django/sav/tickets/{ticket.pk}/reaffecter-equipe/',
            {'equipe': self.equipe_b.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ticket.refresh_from_db()
        self.assertEqual(ticket.equipe, self.equipe_b)
        note = TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE).latest('id')
        self.assertIn('Équipe réaffectée', note.body)
        self.assertEqual(note.user, self.admin)

    def test_reaffecter_vers_une_equipe_inconnue_refuse(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv8-b', defaults={'nom': 'Autre'})
        etrangere = EquipeMaintenance.objects.create(
            company=autre, nom='Étrangère')
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.tickets[0].pk}/reaffecter-equipe/',
            {'equipe': etrangere.pk}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('equipe', resp.json())
        self.tickets[0].refresh_from_db()
        self.assertEqual(self.tickets[0].equipe, self.equipe)

    def test_reaffecter_null_detache_le_ticket(self):
        ticket = self.tickets[0]
        resp = self.api.post(
            f'/api/django/sav/tickets/{ticket.pk}/reaffecter-equipe/',
            {'equipe': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.equipe)
