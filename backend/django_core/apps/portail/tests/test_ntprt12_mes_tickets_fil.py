"""Tests NTPRT12 — fil de commentaires CLIENT-VISIBLE du ticket SAV lié à une
demande portail (« Mes tickets »).

Monte ``sav.selectors.fil_client_du_ticket`` sur l'action ``fil`` de
``MesDemandesSavPortailViewSet`` (``apps.portail.views_client``). Couvre :

* une note technicien INTERNE (``visible_client=False``, le défaut) n'est
  JAMAIS renvoyée, seule une entrée explicitement marquée ``visible_client``
  apparaît ;
* une demande PAS ENCORE prise en charge (aucun ticket SAV créé) renvoie un
  fil VIDE, jamais une erreur ;
* une demande d'un autre client (ou d'une autre société) est introuvable.

Run :
    python manage.py test \\
        apps.portail.tests.test_ntprt12_mes_tickets_fil -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.portail.models import DemandeTicketPortail
from apps.portail.services import provisionner_compte_portail_client
from apps.sav.models import Ticket, TicketActivity
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT12-{n}',
        email=f'ntprt12-{company.id}-{n}@example.invalid')


def make_admin(company):
    client = make_client_crm(company)
    admin, _ = provisionner_compte_portail_client(company, client.id)
    admin.must_change_password = False
    admin.save(update_fields=['must_change_password'])
    return client, admin


def make_technicien(company):
    return CustomUser.objects.create_user(
        username=f'ntprt12-tech-{next(_seq)}', password='x', company=company)


def make_ticket(company, client, technicien):
    n = next(_seq)
    inst = Installation.objects.create(
        company=company, reference=f'CHT-NTPRT12-{n}', client=client)
    return Ticket.objects.create(
        company=company, reference=f'SAV-NTPRT12-{n}', client=client,
        installation=inst, type=Ticket.Type.CORRECTIF, created_by=technicien)


def make_demande(company, client, *, ticket=None, sujet='Onduleur en panne'):
    return DemandeTicketPortail.objects.create(
        company=company, client=client, ticket=ticket, sujet=sujet,
        statut=(DemandeTicketPortail.Statut.PRISE_EN_CHARGE if ticket
                else DemandeTicketPortail.Statut.SOUMISE))


class FilDemandeSavPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt12-co', 'NTPRT12 Société')
        self.client_crm, self.admin = make_admin(self.company)
        self.technicien = make_technicien(self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def _url(self, demande_id):
        return f'/api/django/portail/mes-demandes-sav/{demande_id}/fil/'

    def test_demande_sans_ticket_renvoie_un_fil_vide(self):
        demande = make_demande(self.company, self.client_crm)
        res = self.api.get(self._url(demande.id))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['results'], [])

    def test_note_interne_najamais_visible_note_marquee_visible_oui(self):
        ticket = make_ticket(self.company, self.client_crm, self.technicien)
        demande = make_demande(self.company, self.client_crm, ticket=ticket)
        TicketActivity.objects.create(
            company=self.company, ticket=ticket, kind=TicketActivity.Kind.NOTE,
            body='Diagnostic technicien interne — pas pour le client.',
            user=self.technicien, visible_client=False)
        TicketActivity.objects.create(
            company=self.company, ticket=ticket, kind=TicketActivity.Kind.NOTE,
            body='Votre pièce est commandée, intervention lundi.',
            user=self.technicien, visible_client=True)

        res = self.api.get(self._url(demande.id))
        self.assertEqual(res.status_code, 200, res.data)
        corps = [e['body'] for e in res.data['results']]
        self.assertEqual(
            corps, ['Votre pièce est commandée, intervention lundi.'])
        self.assertNotIn(
            'Diagnostic technicien interne — pas pour le client.', corps)

    def test_demande_dun_autre_client_introuvable(self):
        autre_client = make_client_crm(self.company)
        demande = make_demande(self.company, autre_client)
        res = self.api.get(self._url(demande.id))
        self.assertEqual(res.status_code, 404)

    def test_demande_dune_autre_societe_introuvable(self):
        autre = make_company('ntprt12-co-b', 'NTPRT12 Société B')
        autre_client, _ = make_admin(autre)
        demande = make_demande(autre, autre_client)
        res = self.api.get(self._url(demande.id))
        self.assertEqual(res.status_code, 404)
