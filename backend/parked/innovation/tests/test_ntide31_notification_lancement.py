"""Tests de la notification de lancement de campagne (NTIDE31).

Couvre : ``services.notifier_campagne_lancee`` (notifie chaque utilisateur
du segment, tag ``EventType.INNOVATION_CAMPAIGN``), et le branchement
bout-en-bout via PATCH statut (brouillon → active déclenche, toute autre
transition n'en déclenche PAS une seconde).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import services
from apps.innovation.models import CampagneInnovation
from apps.notifications.models import EventType, Notification
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_role(company, nom):
    role, _ = Role.objects.get_or_create(company=company, nom=nom)
    return role


def make_user(company, username, role=None, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NotifierCampagneLanceeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide31-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.tech1 = make_user(self.co_a, 'ntide31-tech1', role=self.role_tech)
        self.tech2 = make_user(self.co_a, 'ntide31-tech2', role=self.role_tech)

    def test_notifies_each_targeted_user(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            message_incitation='Parlez-nous du pompage.')
        services.notifier_campagne_lancee(camp)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.INNOVATION_CAMPAIGN,
                recipient__in=[self.tech1, self.tech2]).count(),
            2)

    def test_noop_when_no_target(self):
        camp = CampagneInnovation.objects.create(company=self.co_a, nom='Vide')
        services.notifier_campagne_lancee(camp)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.INNOVATION_CAMPAIGN).count(), 0)

    def test_notification_body_uses_message_incitation(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            message_incitation='Parlez-nous du pompage.')
        services.notifier_campagne_lancee(camp)
        notif = Notification.objects.filter(
            event_type=EventType.INNOVATION_CAMPAIGN, recipient=self.tech1).first()
        self.assertEqual(notif.body, 'Parlez-nous du pompage.')


class CampagneActivationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide31-api-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.tech = make_user(self.co_a, 'ntide31-api-tech', role=self.role_tech)
        self.admin_a = make_user(self.co_a, 'ntide31-api-admin', role_legacy='admin')
        self.camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'])

    def test_brouillon_to_active_triggers_notification(self):
        resp = auth(self.admin_a).patch(
            f'/api/django/innovation/campagnes/{self.camp.id}/',
            {'statut': CampagneInnovation.Statut.ACTIVE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            Notification.objects.filter(
                event_type=EventType.INNOVATION_CAMPAIGN,
                recipient=self.tech).exists())

    def test_active_to_fermee_does_not_trigger(self):
        self.camp.statut = CampagneInnovation.Statut.ACTIVE
        self.camp.save(update_fields=['statut'])
        Notification.objects.all().delete()
        resp = auth(self.admin_a).patch(
            f'/api/django/innovation/campagnes/{self.camp.id}/',
            {'statut': CampagneInnovation.Statut.FERMEE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.INNOVATION_CAMPAIGN).exists())

    def test_unrelated_field_update_does_not_trigger(self):
        resp = auth(self.admin_a).patch(
            f'/api/django/innovation/campagnes/{self.camp.id}/',
            {'description': 'Mise à jour'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.INNOVATION_CAMPAIGN).exists())
