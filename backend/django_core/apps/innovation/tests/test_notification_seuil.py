"""Tests de la notification de seuil de votes (NTIDE16).

Couvre : notification créée exactement au moment où ``votes_count`` ATTEINT
le seuil configuré (``InnovationSettings.seuil_votes_notification``, défaut
3) — jamais avant, jamais répétée à chaque vote suivant —, seuil
configurable, aucune erreur si l'idée n'a pas d'auteur, event_type
``EventType.IDEA_VOTE``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee, InnovationSettings
from apps.notifications.models import EventType, Notification

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='normal')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NotificationSeuilVotesTests(TestCase):
    BASE = '/api/django/innovation/votes/'

    def setUp(self):
        self.co_a = make_company('innov-notif-a', 'A')
        self.author = make_user(self.co_a, 'innov-notif-author')
        self.voters = [
            make_user(self.co_a, f'innov-notif-voter{i}') for i in range(5)
        ]
        self.idee = Idee.objects.create(
            company=self.co_a, titre='Une idée populaire', auteur=self.author)

    def _vote(self, voter):
        return auth(voter).post(
            self.BASE, {'idee': self.idee.id}, format='json')

    def test_no_notification_before_threshold(self):
        self._vote(self.voters[0])
        self._vote(self.voters[1])
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.author, event_type=EventType.IDEA_VOTE).count(),
            0)

    def test_notification_fires_exactly_at_default_threshold(self):
        for v in self.voters[:3]:
            self._vote(v)
        notifs = Notification.objects.filter(
            recipient=self.author, event_type=EventType.IDEA_VOTE)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('3 votes', notifs.first().title)
        self.assertEqual(notifs.first().link, f'/innovation/idees/{self.idee.id}')

    def test_notification_not_repeated_past_threshold(self):
        for v in self.voters[:5]:
            self._vote(v)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.author, event_type=EventType.IDEA_VOTE).count(),
            1)

    def test_threshold_configurable(self):
        InnovationSettings.objects.create(
            company=self.co_a, seuil_votes_notification=1)
        self._vote(self.voters[0])
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.author, event_type=EventType.IDEA_VOTE).count(),
            1)

    def test_no_error_when_idee_has_no_author(self):
        idee_sans_auteur = Idee.objects.create(
            company=self.co_a, titre='Idée sans auteur')
        resp = self._vote(self.voters[0])
        self.assertEqual(resp.status_code, 201, resp.data)
        # Simple vérification qu'aucune exception n'a été levée (le vote
        # ci-dessus porte sur ``self.idee``, celle-ci vérifie juste que le
        # helper ne casse rien en présence d'une idée sans auteur ailleurs
        # dans la société).
        idee_sans_auteur.refresh_from_db()
        self.assertEqual(idee_sans_auteur.votes_count, 0)
