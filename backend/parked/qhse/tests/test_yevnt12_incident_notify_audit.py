"""Tests YEVNT12 — l'escalade d'incident critique QHSE notifie + audite.

QHSE32 posait le bus local ``incident_declared`` et son récepteur
``_escalader_incident_critique`` (``apps/qhse/receivers.py``) ajoutait
seulement une note au chatter. YEVNT12 étend CE récepteur existant pour, en
plus de la note chatter :

* notifier les responsables QHSE via ``notifications.services.notify_many``
  (nouvel ``EventType.INCIDENT_CRITICAL``) ;
* écrire une ligne d'audit via ``apps.audit.recorder.record``.

Couvre : gating gravité inchangé (mineurs/majeurs → rien), notification créée
pour un incident critique, entrée d'audit créée, et best-effort (une
exception de notification ne casse ni la création de l'incident ni la note
chatter existante).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.qhse.models import Incident, QhseChatterEntry

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


class Yevnt12IncidentNotifyAuditTests(TestCase):
    def setUp(self):
        self.company = make_company('co-yevnt12', 'CoYevnt12')
        # Utilisateur "responsable" : reçoit les notifications par défaut
        # (fallback resolve_recipients sans règle de routage configurée).
        self.responsable = make_user(self.company, 'yevnt12-resp', role='responsable')
        self.client_api = auth_client(self.responsable)

    def test_incident_critique_notifie_les_responsables(self):
        resp = self.client_api.post(
            INCIDENT_URL,
            {'titre': 'Chute de hauteur', 'type_incident': 'accident',
             'gravite': 'critique'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])

        notifs = Notification.objects.filter(
            company=self.company, event_type='incident_critical')
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.recipient, self.responsable)
        self.assertIn(str(inc.pk), notif.link)

        # La note chatter existante (QHSE32) reste inchangée en plus de la notif.
        self.assertEqual(chatter_notes(self.company, inc).count(), 1)

    def test_incident_critique_ecrit_une_entree_audit(self):
        resp = self.client_api.post(
            INCIDENT_URL,
            {'titre': 'Arc électrique', 'type_incident': 'accident',
             'gravite': 'critique'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])

        logs = AuditLog.objects.filter(
            company=self.company, action='notify', object_id=str(inc.pk))
        self.assertEqual(logs.count(), 1)
        self.assertIn('critique', logs.first().detail.lower())

    def test_incident_non_critique_ne_notifie_ni_audite(self):
        for gravite in ('mineure', 'majeure'):
            resp = self.client_api.post(
                INCIDENT_URL,
                {'titre': f'Incident {gravite}', 'gravite': gravite},
                format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
            inc = Incident.objects.get(id=resp.data['id'])
            self.assertFalse(
                Notification.objects.filter(
                    company=self.company, event_type='incident_critical',
                    link__contains=f'incident={inc.pk}').exists())
            self.assertFalse(
                AuditLog.objects.filter(
                    company=self.company, action='notify',
                    object_id=str(inc.pk)).exists())

    def test_notification_qui_echoue_ne_casse_pas_creation_ni_note(self):
        """Une notification en échec reste best-effort et indépendante."""
        with mock.patch(
                'apps.notifications.services.notify_many',
                side_effect=RuntimeError('boom')):
            resp = self.client_api.post(
                INCIDENT_URL,
                {'titre': 'Incendie', 'gravite': 'critique'},
                format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])
        # La création réussit et la note chatter (indépendante) est bien écrite.
        self.assertEqual(chatter_notes(self.company, inc).count(), 1)
        # L'audit, lui aussi indépendant, reste écrit malgré l'échec notif.
        self.assertTrue(
            AuditLog.objects.filter(
                company=self.company, action='notify',
                object_id=str(inc.pk)).exists())

    def test_audit_qui_echoue_ne_casse_pas_creation_ni_notification(self):
        """Un audit en échec reste best-effort et indépendant."""
        with mock.patch(
                'apps.audit.recorder.record',
                side_effect=RuntimeError('boom')):
            resp = self.client_api.post(
                INCIDENT_URL,
                {'titre': 'Explosion', 'gravite': 'critique'},
                format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])
        self.assertEqual(chatter_notes(self.company, inc).count(), 1)
        self.assertTrue(
            Notification.objects.filter(
                company=self.company, event_type='incident_critical',
                link__contains=f'incident={inc.pk}').exists())
