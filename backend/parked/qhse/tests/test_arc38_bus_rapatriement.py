"""Tests ARC38 — Rapatriement de ``incident_declared`` sur le bus.

Avant : ``qhse`` définissait ``incident_declared`` hors ``core/events.py``
(``apps/qhse/receivers.py`` — invisible à tout abonné cross-app). ARC38 :

* déclare ``incident_declared`` dans ``core/events.py`` ;
* ``IncidentViewSet.perform_create`` émet DÉSORMAIS les DEUX signaux (local
  ET bus) — double émission assumée pendant la transition, le comportement
  QHSE32/YEVNT12 existant (chatter + notification + audit sur le signal
  LOCAL) reste STRICTEMENT inchangé ;
* un abonné FICTIF externe (simulant une app cross-app hypothétique, câblé
  ICI dans le test sans jamais importer ``apps.qhse``) prouve que le signal
  BUS est bien reçu ;
* l'abonné réel de ce lot (``qhse`` lui-même, audit dédié) est aussi couvert.

Run :
    docker compose exec django_core python manage.py test apps.qhse.tests.test_arc38_bus_rapatriement -v 2
"""
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.audit.models import AuditLog
from apps.qhse.models import Incident
from core import event_coverage
from core.events import incident_declared

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


class Arc38IncidentDeclaredSurLeBusTests(TestCase):
    def setUp(self):
        self.company = make_company('co-arc38', 'CoArc38')
        self.responsable = make_user(self.company, 'arc38-resp', role='responsable')
        self.client_api = auth_client(self.responsable)

    def test_creation_incident_emet_le_signal_bus(self):
        """Un abonné FICTIF externe (câblé ICI, jamais dans apps.qhse) reçoit
        bien le signal bus — preuve de la visibilité cross-app (ARC38)."""
        recus = []

        @receiver(incident_declared,
                  dispatch_uid='test_arc38_abonne_externe_fictif')
        def _abonne_externe_fictif(sender, incident, company, user, gravite,
                                   **kwargs):
            recus.append((incident.pk, gravite))

        try:
            resp = self.client_api.post(
                INCIDENT_URL,
                {'titre': 'Chute de hauteur', 'type_incident': 'accident',
                 'gravite': 'majeure'},
                format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
            inc = Incident.objects.get(id=resp.data['id'])
            self.assertEqual(len(recus), 1)
            self.assertEqual(recus[0], (inc.pk, 'majeure'))
        finally:
            incident_declared.disconnect(
                dispatch_uid='test_arc38_abonne_externe_fictif')

    def test_double_emission_ne_casse_pas_le_comportement_local_existant(self):
        """Le comportement QHSE32/YEVNT12 (chatter + notification + audit sur
        le signal LOCAL) reste inchangé malgré la double émission ARC38."""
        from apps.notifications.models import Notification
        from apps.qhse.models import QhseChatterEntry

        resp = self.client_api.post(
            INCIDENT_URL,
            {'titre': 'Arc électrique', 'type_incident': 'accident',
             'gravite': 'critique'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])

        # Note chatter QHSE32 (signal local) — toujours exactement 1.
        notes = QhseChatterEntry.objects.filter(
            company=self.company,
            cible_type=QhseChatterEntry.Cible.INCIDENT,
            cible_id=inc.id, kind=QhseChatterEntry.Kind.NOTE)
        self.assertEqual(notes.count(), 1)

        # Notification YEVNT12 (signal local) — toujours exactement 1.
        self.assertEqual(
            Notification.objects.filter(
                company=self.company, event_type='incident_critical').count(),
            1)

    def test_abonne_bus_qhse_ecrit_une_entree_audit_dediee(self):
        """L'abonné réel de ce lot (qhse se réabonne à son propre signal bus)
        écrit une entrée d'audit DISTINCTE de celle de YEVNT12 (signal local)
        — un incident même NON critique déclenche cet audit dédié.

        Action ``create`` (et non ``notify``) : l'abonné bus ne notifie
        personne, il TRACE la visibilité de la déclaration sur le bus. Il ne
        doit donc PAS polluer le flux d'audit ``notify`` réservé aux vraies
        notifications YEVNT12 (garde de non-régression : YEVNT12 compte 1
        ``notify`` pour un critique, 0 pour un mineur)."""
        resp = self.client_api.post(
            INCIDENT_URL,
            {'titre': 'Incident mineur', 'gravite': 'mineure'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])

        logs = AuditLog.objects.filter(
            company=self.company, action='create', object_id=str(inc.pk))
        self.assertTrue(
            logs.filter(detail__icontains='ARC38').exists())
        # Non-régression YEVNT12 : l'abonné bus n'écrit AUCUN audit ``notify``
        # (aucune notification envoyée pour un incident mineur).
        self.assertFalse(
            AuditLog.objects.filter(
                company=self.company, action='notify',
                object_id=str(inc.pk)).exists())

    def test_incident_declared_nest_plus_orphelin(self):
        self.assertNotIn(
            'incident_declared', event_coverage.orphan_signals())
