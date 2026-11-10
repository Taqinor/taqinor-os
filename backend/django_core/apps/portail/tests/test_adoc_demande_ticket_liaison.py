"""ADOC118 — la liaison d'une demande SAV portail à un ticket est bornée.

Constat (C-ADOC-053, sondes #96/#97) : ``prendre_en_charge`` écrivait le
``ticket_id`` reçu SANS le vérifier (FK ``db_constraint=False``) — un ticket
d'une AUTRE société ou d'un AUTRE client était accepté (200), « abc » faisait
un 500, et un mauvais numéro n'était plus corrigeable (second POST sans effet,
``ticket_id`` en lecture seule au PATCH).

Correctif : une résolution commune (``apps.sav.selectors.ticket_scoped`` +
même client) refuse tout ticket inconnu POUR CE CLIENT avec le MÊME 404 (ENF11, ex-400) que
l'id 999999, et l'action ``lier-ticket`` corrige la liaison tant que la
demande n'est ni résolue ni refusée (409 sinon).

Run :
    python manage.py test apps.portail.tests.test_adoc_demande_ticket_liaison -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.portail.models import DemandeTicketPortail
from apps.sav.models import Ticket
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

RACINE = '/api/django/portail/demandes-ticket-portail/'
MESSAGE = 'Ticket inconnu pour ce client.'


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=f'ADOC118-{n}', prenom='Test',
        email=f'adoc118-{company.id}-{n}@example.invalid')


def make_ticket(company, client, auteur):
    n = next(_seq)
    inst = Installation.objects.create(
        company=company, reference=f'CHT-ADOC118-{n}', client=client)
    return Ticket.objects.create(
        company=company, reference=f'SAV-ADOC118-{n}', client=client,
        installation=inst, type=Ticket.Type.CORRECTIF, created_by=auteur)


class DemandeTicketLiaisonTests(TestCase):
    def setUp(self):
        self.co_a = make_company('adoc118-a')
        self.co_b = make_company('adoc118-b')
        self.resp = CustomUser.objects.create_user(
            username='adoc118-resp', password='motdepasse-test-1234',
            company=self.co_a, role_legacy='responsable')
        auteur_b = CustomUser.objects.create_user(
            username='adoc118-resp-b', password='motdepasse-test-1234',
            company=self.co_b, role_legacy='responsable')
        self.c1 = make_client(self.co_a)
        self.c2 = make_client(self.co_a)
        client_b = make_client(self.co_b)
        self.ticket_b = make_ticket(self.co_b, client_b, auteur_b)
        self.ticket_c2 = make_ticket(self.co_a, self.c2, self.resp)
        self.faux_ticket_c1 = make_ticket(self.co_a, self.c1, self.resp)
        self.bon_ticket_c1 = make_ticket(self.co_a, self.c1, self.resp)
        self.demande = DemandeTicketPortail.objects.create(
            company=self.co_a, client=self.c1, sujet='Onduleur en panne')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp)}')

    def _prendre(self, ticket_id):
        return self.api.post(
            f'{RACINE}{self.demande.id}/prendre_en_charge/',
            {'ticket_id': ticket_id}, format='json')

    def _lier(self, ticket_id, demande=None):
        demande = demande or self.demande
        return self.api.post(
            f'{RACINE}{demande.id}/lier-ticket/',
            {'ticket_id': ticket_id}, format='json')

    def _assert_refus_inchange(self, res):
        self.assertEqual(res.status_code, 404, res.content)
        self.assertEqual(res.json(), {'detail': MESSAGE})
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut,
                         DemandeTicketPortail.Statut.SOUMISE)
        self.assertIsNone(self.demande.ticket_id)

    def test_ticket_autre_societe_refuse(self):
        res = self._prendre(self.ticket_b.id)
        self._assert_refus_inchange(res)
        # Octet-identique au refus d'un id qui n'existe nulle part.
        inexistant = self._prendre(999999)
        self._assert_refus_inchange(inexistant)
        self.assertEqual(res.content, inexistant.content)

    def test_ticket_non_numerique_404(self):
        res = self._prendre('abc')
        self._assert_refus_inchange(res)
        self.assertEqual(res.content, self._prendre(999999).content)

    def test_ticket_autre_client_refuse(self):
        res = self._prendre(self.ticket_c2.id)
        self._assert_refus_inchange(res)
        self.assertEqual(res.content, self._prendre(999999).content)

    def test_relier_ticket_corrige(self):
        res = self._prendre(self.faux_ticket_c1.id)
        self.assertEqual(res.status_code, 200, res.content)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut,
                         DemandeTicketPortail.Statut.PRISE_EN_CHARGE)
        self.assertEqual(self.demande.ticket_id, self.faux_ticket_c1.id)

        res = self._lier(self.bon_ticket_c1.id)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['ticket_id'], self.bon_ticket_c1.id)
        # Persistance : relu par l'API.
        relu = self.api.get(f'{RACINE}{self.demande.id}/')
        self.assertEqual(relu.json()['ticket_id'], self.bon_ticket_c1.id)

        # La correction elle-même reste bornée au client.
        refus = self._lier(self.ticket_c2.id)
        self.assertEqual(refus.status_code, 404, refus.content)
        self.assertEqual(refus.json(), {'detail': MESSAGE})
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.ticket_id, self.bon_ticket_c1.id)

    def test_lier_ticket_demande_close_409(self):
        for statut in (DemandeTicketPortail.Statut.RESOLUE,
                       DemandeTicketPortail.Statut.REFUSEE):
            demande = DemandeTicketPortail.objects.create(
                company=self.co_a, client=self.c1, sujet='Close',
                statut=statut, ticket=self.faux_ticket_c1)
            res = self._lier(self.bon_ticket_c1.id, demande=demande)
            self.assertEqual(res.status_code, 409, res.content)
            demande.refresh_from_db()
            self.assertEqual(demande.ticket_id, self.faux_ticket_c1.id)

    def test_lier_ticket_autre_societe_404(self):
        """La demande d'une autre société n'est même pas adressable."""
        autre = DemandeTicketPortail.objects.create(
            company=self.co_b, client=None, sujet='Autre société')
        res = self._lier(self.bon_ticket_c1.id, demande=autre)
        self.assertEqual(res.status_code, 404, res.content)

    def test_ticket_resolu_resout_la_demande(self):
        """ASOC44 — la demande prise en charge suit la résolution de SON
        ticket ; une demande soumise ou liée à un autre ticket ne bouge pas."""
        self.assertEqual(self._prendre(self.bon_ticket_c1.id).status_code, 200)
        soumise = DemandeTicketPortail.objects.create(
            company=self.co_a, client=self.c1, sujet='Soumise')
        autre = DemandeTicketPortail.objects.create(
            company=self.co_a, client=self.c1, sujet='Autre ticket',
            statut=DemandeTicketPortail.Statut.PRISE_EN_CHARGE,
            ticket=self.faux_ticket_c1)
        tickets = f'/api/django/sav/tickets/{self.bon_ticket_c1.id}/'
        for geste in ('demarrer', 'resoudre'):
            res = self.api.post(f'{tickets}{geste}/', {}, format='json')
            self.assertEqual(res.status_code, 200, res.content)
        relu = self.api.get(f'{RACINE}{self.demande.id}/')
        self.assertEqual(relu.json()['statut'],
                         DemandeTicketPortail.Statut.RESOLUE)
        soumise.refresh_from_db()
        autre.refresh_from_db()
        self.assertEqual(soumise.statut, DemandeTicketPortail.Statut.SOUMISE)
        self.assertEqual(autre.statut,
                         DemandeTicketPortail.Statut.PRISE_EN_CHARGE)

    def test_refuser_avec_motif(self):
        """ASOC98 — refus motivé : 200 + motif lu par le client ; motif vide
        400 ; demande close 409 ; utilisateur sans rôle responsable 403."""
        from apps.portail.tests.test_aud525_demandes_sav_client import (
            make_portal_user)

        motif = "Hors garantie : dégât d'orage"
        url = f'{RACINE}{self.demande.id}/refuser/'
        vide = self.api.post(url, {'motif': '  '}, format='json')
        self.assertEqual(vide.status_code, 400, vide.content)
        self.assertIn('motif', vide.json())
        normal = CustomUser.objects.create_user(
            username='asoc98-normal', password='motdepasse-test-1234',
            company=self.co_a, role_legacy='normal')
        autre = APIClient()
        autre.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(normal)}')
        self.assertEqual(
            autre.post(url, {'motif': motif}, format='json').status_code, 403)
        res = self.api.post(url, {'motif': motif}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['statut'],
                         DemandeTicketPortail.Statut.REFUSEE)
        encore = self.api.post(url, {'motif': motif}, format='json')
        self.assertEqual(encore.status_code, 409, encore.content)
        portail = make_portal_user(
            self.co_a, 'asoc98-portail', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.c1.id)
        client = APIClient()
        client.force_authenticate(portail)
        ligne = client.get(
            f'/api/django/portail/mes-demandes-sav/{self.demande.id}/').json()
        self.assertEqual(
            (ligne['statut'], ligne['statut_display'], ligne['motif_refus']),
            ('refusee', 'Refusée', motif))
