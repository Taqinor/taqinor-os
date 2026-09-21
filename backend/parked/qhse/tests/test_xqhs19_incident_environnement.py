"""XQHS19 — Incidents environnementaux (déversement/rejet) + notification.

Couvre :
  * un incident environnement porte substance/quantité/milieu ;
  * la notification requise non faite relance avant échéance ;
  * la clôture exige la notification si requise (gate, pattern QHSE13) ;
  * un incident sans notification requise se clôture librement ;
  * le scoping société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import Incident
from apps.qhse.services import (
    cloturer_incident, incidents_notification_en_retard,
    relancer_notifications_environnement,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class IncidentEnvironnementFieldsTests(TestCase):
    def test_porte_substance_quantite_milieu(self):
        company = make_company('xqhs19-fields', 'Xqhs19 Fields')
        incident = Incident.objects.create(
            company=company, titre='Fuite huile transfo',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            substance='Huile diélectrique', quantite_estimee=25,
            quantite_unite='litres',
            milieu_touche=Incident.MilieuTouche.SOL)
        self.assertEqual(incident.substance, 'Huile diélectrique')
        self.assertEqual(incident.milieu_touche, Incident.MilieuTouche.SOL)


class NotificationEnRetardTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs19-notif', 'Xqhs19 Notif')

    def test_notification_requise_non_faite_avant_echeance_pas_en_retard(self):
        incident = Incident.objects.create(
            company=self.company, titre='Rejet non conforme',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            notification_requise=True,
            date_limite_notification=timezone.localdate() + timedelta(days=5))
        self.assertFalse(incident.notification_en_retard)
        retards = incidents_notification_en_retard(self.company)
        self.assertNotIn(incident, retards)

    def test_notification_requise_non_faite_apres_echeance_en_retard(self):
        incident = Incident.objects.create(
            company=self.company, titre='Rejet non conforme',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            notification_requise=True,
            date_limite_notification=timezone.localdate() - timedelta(days=2))
        self.assertTrue(incident.notification_en_retard)
        retards = incidents_notification_en_retard(self.company)
        self.assertIn(incident, retards)

    def test_notification_faite_nest_plus_en_retard(self):
        incident = Incident.objects.create(
            company=self.company, titre='Rejet non conforme',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            notification_requise=True,
            date_notification=timezone.localdate(),
            date_limite_notification=timezone.localdate() - timedelta(days=2))
        self.assertFalse(incident.notification_en_retard)

    def test_relance_scope_societe(self):
        other_co = make_company('xqhs19-notif-other', 'Xqhs19 Notif Other')
        Incident.objects.create(
            company=other_co, titre='Autre société',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            notification_requise=True,
            date_limite_notification=timezone.localdate() - timedelta(days=1))
        relances = relancer_notifications_environnement(self.company)
        self.assertEqual(len(relances), 0)


class CloturerIncidentGateTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs19-cloture', 'Xqhs19 Cloture')

    def test_notification_requise_non_faite_bloque_cloture(self):
        incident = Incident.objects.create(
            company=self.company, titre='Rejet non conforme',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            notification_requise=True)
        with self.assertRaises(ValueError):
            cloturer_incident(incident)
        incident.refresh_from_db()
        self.assertNotEqual(incident.statut, Incident.Statut.CLOS)

    def test_notification_faite_autorise_cloture(self):
        incident = Incident.objects.create(
            company=self.company, titre='Rejet non conforme',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            notification_requise=True,
            date_notification=timezone.localdate())
        incident = cloturer_incident(incident)
        self.assertEqual(incident.statut, Incident.Statut.CLOS)

    def test_incident_sans_notification_requise_se_cloture_librement(self):
        incident = Incident.objects.create(
            company=self.company, titre='Incident classique',
            type_incident=Incident.TypeIncident.INCIDENT)
        incident = cloturer_incident(incident)
        self.assertEqual(incident.statut, Incident.Statut.CLOS)

    def test_deja_clos_idempotent(self):
        incident = Incident.objects.create(
            company=self.company, titre='Déjà clos',
            statut=Incident.Statut.CLOS)
        result = cloturer_incident(incident)
        self.assertEqual(result.statut, Incident.Statut.CLOS)


class CloturerIncidentApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs19-api', 'Xqhs19 Api')
        self.user = make_user(self.company, 'xqhs19-user')

    def test_cloturer_action_bloque_400(self):
        incident = Incident.objects.create(
            company=self.company, titre='Rejet',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            notification_requise=True)
        resp = auth(self.user).post(
            f'/api/django/qhse/incidents/{incident.pk}/cloturer/')
        self.assertEqual(resp.status_code, 400)

    def test_cloturer_action_succes(self):
        incident = Incident.objects.create(
            company=self.company, titre='Incident classique')
        resp = auth(self.user).post(
            f'/api/django/qhse/incidents/{incident.pk}/cloturer/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'clos')

    def test_notifications_en_retard_endpoint(self):
        Incident.objects.create(
            company=self.company, titre='Rejet en retard',
            type_incident=Incident.TypeIncident.ENVIRONNEMENT,
            notification_requise=True,
            date_limite_notification=timezone.localdate() - timedelta(days=1))
        resp = auth(self.user).get(
            '/api/django/qhse/incidents/notifications-en-retard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
