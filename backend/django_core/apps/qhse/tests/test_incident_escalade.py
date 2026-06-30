"""Tests QHSE32 — Événement ``incident_declared`` sur le bus (escalade).

Couvre :
* la déclaration d'un Incident via l'API émet ``incident_declared`` (le
  récepteur est exécuté) ;
* un incident CRITIQUE escalade : une note d'escalade est écrite dans le chatter
  QHSE de l'incident ;
* un incident NON critique (mineure/majeure) n'escalade pas (gating par gravité) ;
* la société est portée par l'événement (scope serveur) ;
* une réaction qui échoue ne casse JAMAIS la création de l'incident (best-effort).

Mirroir du patron ``ventes`` (émet ``devis_accepted``) / ``crm`` (s'abonne via
``receivers.py`` câblé dans ``apps.py`` ``ready()``).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import Incident, QhseChatterEntry
from apps.qhse.receivers import incident_declared

User = get_user_model()

INCIDENT_URL = '/api/django/qhse/incidents/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def chatter_notes(company, incident):
    return QhseChatterEntry.objects.filter(
        company=company,
        cible_type=QhseChatterEntry.Cible.INCIDENT,
        cible_id=incident.id,
        kind=QhseChatterEntry.Kind.NOTE)


class IncidentEscaladeTests(TestCase):
    def setUp(self):
        self.company = make_company('co-inc-esc', 'CoIncEsc')
        self.user = make_user(self.company, 'inc-esc-resp')
        self.client_api = auth_client(self.user)

    def test_declaration_emet_incident_declared(self):
        """La création via l'API fait courir le récepteur du bus."""
        received = {}

        def _spy(sender, incident, company, user, gravite, **kwargs):
            received['incident'] = incident
            received['company'] = company
            received['user'] = user
            received['gravite'] = gravite

        incident_declared.connect(_spy, dispatch_uid='qhse32_test_spy')
        try:
            resp = self.client_api.post(
                INCIDENT_URL,
                {'titre': 'Effondrement', 'type_incident': 'accident',
                 'gravite': 'critique'},
                format='json')
        finally:
            incident_declared.disconnect(dispatch_uid='qhse32_test_spy')

        self.assertEqual(resp.status_code, 201, resp.data)
        # Le récepteur a bien reçu l'instance + la société + l'utilisateur.
        self.assertEqual(received['incident'].id, resp.data['id'])
        self.assertEqual(received['company'], self.company)
        self.assertEqual(received['user'], self.user)
        self.assertEqual(received['gravite'], 'critique')

    def test_incident_critique_escalade(self):
        """Un incident critique écrit une note d'escalade dans son chatter."""
        resp = self.client_api.post(
            INCIDENT_URL,
            {'titre': 'Arc électrique', 'type_incident': 'accident',
             'gravite': 'critique'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])
        notes = chatter_notes(self.company, inc)
        self.assertEqual(notes.count(), 1)
        note = notes.first()
        self.assertIn('CRITIQUE', note.body)
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.company, self.company)

    def test_incident_non_critique_pas_escalade(self):
        """Mineure / majeure : aucune note d'escalade (gating par gravité)."""
        for gravite in ('mineure', 'majeure'):
            resp = self.client_api.post(
                INCIDENT_URL,
                {'titre': f'Incident {gravite}', 'gravite': gravite},
                format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
            inc = Incident.objects.get(id=resp.data['id'])
            self.assertEqual(chatter_notes(self.company, inc).count(), 0)

    def test_reaction_qui_echoue_ne_casse_pas_la_creation(self):
        """Si l'escalade lève, la création de l'incident réussit quand même."""
        with mock.patch(
                'apps.qhse.chatter.log_note',
                side_effect=RuntimeError('boom')):
            resp = self.client_api.post(
                INCIDENT_URL,
                {'titre': 'Incendie', 'gravite': 'critique'},
                format='json')
        # La création n'est PAS affectée par l'échec best-effort de la réaction.
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(Incident.objects.filter(id=resp.data['id']).exists())
        # Aucune note n'a pu être écrite (la réaction a échoué silencieusement).
        inc = Incident.objects.get(id=resp.data['id'])
        self.assertEqual(chatter_notes(self.company, inc).count(), 0)
