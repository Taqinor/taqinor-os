"""NTSRV16 — Gestion Problème (Problem Management).

Critère d'acceptation : lier 5 tickets récurrents « onduleur X en panne » au
MÊME problème permet de voir en UN clic tous les tickets concernés — et
résoudre le problème ne touche JAMAIS le statut des tickets liés (deux
machines d'états indépendantes).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv16 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import (
    Probleme, ProblemeIncident, Ticket, TicketActivity,
)

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV16ProblemeTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv16', defaults={'nom': 'Sav Co NTSRV16'})
        self.admin = User.objects.create_user(
            username='ntsrv16_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV16')
        self.tickets = [
            Ticket.objects.create(
                company=self.company, reference=f'SAV-NTSRV16-{i}',
                client=self.client_obj, statut=Ticket.Statut.EN_COURS,
                date_ouverture='2026-03-01')
            for i in range(1, 6)
        ]

    def _creer_probleme(self, titre='Onduleur X en panne'):
        resp = self.api.post('/api/django/sav/problemes/',
                             {'titre': titre}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        return resp.json()

    # ── Création + numérotation ──────────────────────────────────────────
    def test_reference_prb_posee_cote_serveur(self):
        data = self._creer_probleme()
        self.assertTrue(data['reference'].startswith('PRB-'),
                        data['reference'])
        self.assertEqual(data['statut'], 'identifie')
        probleme = Probleme.objects.get(pk=data['id'])
        self.assertEqual(probleme.company, self.company)

    def test_references_successives_sans_collision(self):
        premiere = self._creer_probleme('Problème 1')['reference']
        seconde = self._creer_probleme('Problème 2')['reference']
        self.assertNotEqual(premiere, seconde)

    def test_reference_du_corps_ignoree(self):
        resp = self.api.post(
            '/api/django/sav/problemes/',
            {'titre': 'Tentative', 'reference': 'PRB-PIRATE'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertNotEqual(resp.json()['reference'], 'PRB-PIRATE')

    def test_titre_vide_refuse_en_nommant_le_champ(self):
        resp = self.api.post('/api/django/sav/problemes/',
                             {'titre': '   '}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('titre', resp.json())

    # ── Critère d'acceptation : 5 tickets, un clic ───────────────────────
    def test_cinq_tickets_lies_visibles_en_un_appel(self):
        probleme = self._creer_probleme()
        for ticket in self.tickets:
            resp = self.api.post(
                f"/api/django/sav/problemes/{probleme['id']}/lier-ticket/",
                {'ticket': ticket.pk}, format='json')
            self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.api.get(
            f"/api/django/sav/problemes/{probleme['id']}/tickets/")
        self.assertEqual(resp.status_code, 200, resp.content)
        references = {ligne['reference'] for ligne in resp.json()['results']}
        self.assertEqual(references,
                         {t.reference for t in self.tickets})

    def test_lier_deux_fois_est_idempotent(self):
        probleme = self._creer_probleme()
        url = f"/api/django/sav/problemes/{probleme['id']}/lier-ticket/"
        premier = self.api.post(url, {'ticket': self.tickets[0].pk},
                                format='json')
        second = self.api.post(url, {'ticket': self.tickets[0].pk},
                               format='json')
        self.assertTrue(premier.json()['cree'])
        self.assertFalse(second.json()['cree'])
        self.assertEqual(second.json()['nb_tickets'], 1)
        self.assertEqual(ProblemeIncident.objects.filter(
            probleme_id=probleme['id']).count(), 1)

    def test_liaison_tracee_dans_le_chatter_du_ticket(self):
        probleme = self._creer_probleme()
        self.api.post(
            f"/api/django/sav/problemes/{probleme['id']}/lier-ticket/",
            {'ticket': self.tickets[0].pk}, format='json')
        note = TicketActivity.objects.filter(
            ticket=self.tickets[0], kind=TicketActivity.Kind.NOTE).latest('id')
        self.assertIn(probleme['reference'], note.body)
        self.assertEqual(note.user, self.admin)

    def test_delier_retire_le_lien_jamais_le_ticket(self):
        probleme = self._creer_probleme()
        self.api.post(
            f"/api/django/sav/problemes/{probleme['id']}/lier-ticket/",
            {'ticket': self.tickets[0].pk}, format='json')
        resp = self.api.post(
            f"/api/django/sav/problemes/{probleme['id']}/delier-ticket/",
            {'ticket': self.tickets[0].pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['delie'])
        self.assertEqual(resp.json()['nb_tickets'], 0)
        self.assertTrue(Ticket.objects.filter(pk=self.tickets[0].pk).exists())

    def test_delier_deux_fois_ne_casse_rien(self):
        probleme = self._creer_probleme()
        url = f"/api/django/sav/problemes/{probleme['id']}/delier-ticket/"
        self.api.post(url, {'ticket': self.tickets[0].pk}, format='json')
        resp = self.api.post(url, {'ticket': self.tickets[0].pk},
                             format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['delie'])

    # ── Multi-tenant ─────────────────────────────────────────────────────
    def test_ticket_d_une_autre_societe_refuse(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv16-b', defaults={'nom': 'Autre NTSRV16'})
        client_etranger = Client.objects.create(
            company=autre, nom='Étranger', prenom='X')
        etranger = Ticket.objects.create(
            company=autre, reference='SAV-ETR-1', client=client_etranger)
        probleme = self._creer_probleme()
        resp = self.api.post(
            f"/api/django/sav/problemes/{probleme['id']}/lier-ticket/",
            {'ticket': etranger.pk}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ticket', resp.json())

    def test_liste_ne_montre_que_sa_societe(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv16-c', defaults={'nom': 'Autre C NTSRV16'})
        Probleme.objects.create(
            company=autre, reference='PRB-ETR-0001', titre='Étranger')
        self._creer_probleme('Le mien')
        resp = self.api.get('/api/django/sav/problemes/')
        self.assertEqual(resp.status_code, 200, resp.content)
        payload = resp.json()
        lignes = payload['results'] if isinstance(payload, dict) else payload
        self.assertEqual([ligne['titre'] for ligne in lignes], ['Le mien'])

    def test_ticket_manquant_nomme_le_champ(self):
        probleme = self._creer_probleme()
        resp = self.api.post(
            f"/api/django/sav/problemes/{probleme['id']}/lier-ticket/",
            {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ticket', resp.json())

    # ── Deux machines d'états INDÉPENDANTES ──────────────────────────────
    def test_resoudre_le_probleme_ne_touche_aucun_ticket(self):
        probleme = self._creer_probleme()
        for ticket in self.tickets:
            self.api.post(
                f"/api/django/sav/problemes/{probleme['id']}/lier-ticket/",
                {'ticket': ticket.pk}, format='json')
        resp = self.api.patch(
            f"/api/django/sav/problemes/{probleme['id']}/",
            {'statut': 'resolu', 'cause_racine': 'Lot de condensateurs'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        for ticket in self.tickets:
            ticket.refresh_from_db()
            self.assertEqual(ticket.statut, Ticket.Statut.EN_COURS)

    # ── Impact (nb tickets × ancienneté) ─────────────────────────────────
    def test_nb_tickets_expose_dans_la_liste(self):
        probleme = self._creer_probleme()
        self.api.post(
            f"/api/django/sav/problemes/{probleme['id']}/lier-ticket/",
            {'ticket': self.tickets[0].pk}, format='json')
        resp = self.api.get('/api/django/sav/problemes/')
        payload = resp.json()
        lignes = payload['results'] if isinstance(payload, dict) else payload
        ligne = next(item for item in lignes if item['id'] == probleme['id'])
        self.assertEqual(ligne['nb_tickets'], 1)
        self.assertGreaterEqual(ligne['impact'], 1)

    def test_tri_par_impact_place_le_plus_lourd_en_tete(self):
        leger = self._creer_probleme('Léger')
        lourd = self._creer_probleme('Lourd')
        for ticket in self.tickets:
            self.api.post(
                f"/api/django/sav/problemes/{lourd['id']}/lier-ticket/",
                {'ticket': ticket.pk}, format='json')
        self.api.post(
            f"/api/django/sav/problemes/{leger['id']}/lier-ticket/",
            {'ticket': self.tickets[0].pk}, format='json')
        resp = self.api.get('/api/django/sav/problemes/?ordering=-impact')
        self.assertEqual(resp.status_code, 200, resp.content)
        payload = resp.json()
        lignes = payload['results'] if isinstance(payload, dict) else payload
        self.assertEqual(lignes[0]['id'], lourd['id'])
