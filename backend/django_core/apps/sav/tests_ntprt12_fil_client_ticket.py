"""
NTPRT12 — « Mes tickets SAV » : fil de commentaires client-visible.

Couvre :
  * CRITÈRE D'ACCEPTATION : une note technicien INTERNE n'apparaît jamais côté
    portail, sauf si elle est explicitement marquée visible client ;
  * le défaut est INTERNE (aucun opt-in dans le corps ⇒ ``visible_client``
    False), y compris pour les entrées typées (journal de statut, e-mail,
    WhatsApp, appel) qui ne peuvent PAS devenir visibles par déduction ;
  * ``visible_client`` n'est jamais écrit depuis le corps d'une mise à jour
    d'activité (lecture seule au sérialiseur) — seul ``noter`` le pose ;
  * le fil client exige le triplet (société, client, ticket) : le ticket d'un
    autre client ou d'une autre société renvoie une liste vide, jamais une
    erreur qui révélerait son existence ;
  * le payload du fil ne contient aucun champ interne.

Run :
    python manage.py test apps.sav.tests_ntprt12_fil_client_ticket -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav import activity, selectors
from apps.sav.models import Ticket, TicketActivity

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/sav'


def make_company(slug=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntprt12-co-{n}', defaults={'nom': f'NTPRT12 Co {n}'})
    return company


def make_user(company, role='admin'):
    return User.objects.create_user(
        username=f'ntprt12-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Portail', prenom=f'Client {n}',
        email=f'ntprt12-{company.id}-{n}@example.invalid')


def make_ticket(company, client, user):
    n = next(_seq)
    inst = Installation.objects.create(
        company=company, reference=f'CHT-NTPRT12-{n}', client=client)
    return Ticket.objects.create(
        company=company, reference=f'SAV-NTPRT12-{n}', client=client,
        installation=inst, type=Ticket.Type.CORRECTIF, created_by=user)


class FilClientTicketTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.technicien = make_user(self.company)
        self.client_portail = make_client(self.company)
        self.ticket = make_ticket(
            self.company, self.client_portail, self.technicien)
        self.api = auth(self.technicien)

    def test_note_interne_jamais_visible_note_marquee_visible(self):
        """CRITÈRE D'ACCEPTATION NTPRT12."""
        resp_interne = self.api.post(
            f'{BASE}/tickets/{self.ticket.pk}/noter/',
            {'body': 'Carte mère probablement HS, prévoir un devis interne.'},
            format='json')
        self.assertEqual(resp_interne.status_code, 201, resp_interne.content)
        self.assertFalse(resp_interne.data['visible_client'])

        resp_visible = self.api.post(
            f'{BASE}/tickets/{self.ticket.pk}/noter/',
            {'body': 'Votre pièce est commandée, intervention lundi.',
             'visible_client': True},
            format='json')
        self.assertEqual(resp_visible.status_code, 201, resp_visible.content)
        self.assertTrue(resp_visible.data['visible_client'])

        fil = selectors.fil_client_du_ticket(
            self.company, self.client_portail.id, self.ticket.pk)

        corps = [entree['body'] for entree in fil]
        self.assertEqual(
            corps, ['Votre pièce est commandée, intervention lundi.'])
        self.assertNotIn(
            'Carte mère probablement HS, prévoir un devis interne.', corps)

    def test_journal_de_changement_reste_interne(self):
        ancien = Ticket.objects.get(pk=self.ticket.pk)
        self.ticket.statut = Ticket.Statut.EN_COURS
        self.ticket.save(update_fields=['statut'])
        activity.log_changes(ancien, self.ticket, self.technicien)
        activity.log_email(self.ticket, self.technicien, 'Échange e-mail')
        activity.log_whatsapp(self.ticket, self.technicien, 'Message WhatsApp')
        activity.log_appel(self.ticket, self.technicien, 'Appel client')

        self.assertEqual(
            selectors.fil_client_du_ticket(
                self.company, self.client_portail.id, self.ticket.pk),
            [])
        self.assertFalse(
            TicketActivity.objects
            .filter(ticket=self.ticket, visible_client=True).exists())

    def test_log_note_par_defaut_interne(self):
        entree = activity.log_note(
            self.ticket, self.technicien, 'Note par défaut')

        self.assertFalse(entree.visible_client)

    def test_visible_client_non_ecrit_depuis_le_corps_dune_mise_a_jour(self):
        interne = activity.log_note(
            self.ticket, self.technicien, 'Note interne')

        resp = self.api.get(f'{BASE}/tickets/{self.ticket.pk}/historique/')
        self.assertEqual(resp.status_code, 200, resp.content)
        lignes = resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])
        cible = [ligne for ligne in lignes if ligne['id'] == interne.pk]
        self.assertEqual(len(cible), 1)
        self.assertFalse(cible[0]['visible_client'])

    def test_payload_du_fil_sans_champ_interne(self):
        self.api.post(
            f'{BASE}/tickets/{self.ticket.pk}/noter/',
            {'body': 'Message client', 'visible_client': '1'}, format='json')

        fil = selectors.fil_client_du_ticket(
            self.company, self.client_portail.id, self.ticket.pk)

        self.assertEqual(
            set(fil[0]), {'id', 'body', 'created_at', 'auteur'})


class IsolationFilClientTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.technicien = make_user(self.company)
        self.client_a = make_client(self.company)
        self.client_b = make_client(self.company)
        self.ticket_a = make_ticket(
            self.company, self.client_a, self.technicien)
        activity.log_note(
            self.ticket_a, self.technicien, 'Visible A', visible_client=True)

    def test_ticket_dun_autre_client_renvoie_un_fil_vide(self):
        self.assertEqual(
            selectors.fil_client_du_ticket(
                self.company, self.client_b.id, self.ticket_a.pk),
            [])

    def test_ticket_dune_autre_societe_renvoie_un_fil_vide(self):
        autre_company = make_company()

        self.assertEqual(
            selectors.fil_client_du_ticket(
                autre_company, self.client_a.id, self.ticket_a.pk),
            [])

    def test_arguments_manquants_renvoient_un_fil_vide(self):
        self.assertEqual(
            selectors.fil_client_du_ticket(self.company, None,
                                           self.ticket_a.pk),
            [])
        self.assertEqual(
            selectors.fil_client_du_ticket(self.company, self.client_a.id,
                                           None),
            [])
