"""ENF17 — notifications : FK des sérialiseurs bornées société.

``NotificationRoutingRuleSerializer.target_user`` acceptait l'utilisateur
d'une AUTRE société (une règle de routage pouvait notifier un compte voisin) ;
``AnnonceLectureSerializer.annonce`` l'annonce d'une autre société. Désormais
l'id d'ailleurs reçoit la réponse d'un id absent (400 « objet inexistant »)
et l'id de sa propre société reste accepté.

Run:
    python manage.py test apps.notifications.tests_enf17_fk_societe -v 2
"""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.notifications.models import Annonce, NotificationRoutingRule
from apps.notifications.serializers import (
    AnnonceLectureSerializer, NotificationRoutingRuleSerializer,
)
from apps.notifications.types_evenements import EventType
from authentication.models import Company

User = get_user_model()

ID_ABSENT = 99999999
URL = '/api/django/notifications/routing-rules/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FkNotificationsBorneesSocieteTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='enf17-not-a', slug='enf17-not-a')
        self.co_b = Company.objects.create(nom='enf17-not-b', slug='enf17-not-b')
        self.admin_a = User.objects.create_user(
            username='enf17-not-admin-a', password='x', role_legacy='admin',
            company=self.co_a)
        self.user_a = User.objects.create_user(
            username='enf17-not-user-a', password='x', role_legacy='normal',
            company=self.co_a)
        self.user_b = User.objects.create_user(
            username='enf17-not-user-b', password='x', role_legacy='normal',
            company=self.co_b)
        self.annonce_a = Annonce.objects.create(
            company=self.co_a, titre='Note A', corps='Lire',
            cible_type=Annonce.Cible.TOUS, lecture_obligatoire=True)
        self.annonce_b = Annonce.objects.create(
            company=self.co_b, titre='Note B', corps='Lire',
            cible_type=Annonce.Cible.TOUS, lecture_obligatoire=True)
        self.ctx = {'request': SimpleNamespace(user=self.admin_a)}

    def _assert_borne(self, cls, champ, propre, etranger):
        with self.subTest(serializer=cls.__name__, champ=champ):
            ser = cls(data={champ: etranger.pk}, partial=True,
                      context=self.ctx)
            self.assertFalse(ser.is_valid())
            self.assertEqual(ser.errors[champ][0].code, 'does_not_exist')
            absent = cls(data={champ: ID_ABSENT}, partial=True,
                         context=self.ctx)
            self.assertFalse(absent.is_valid())
            self.assertEqual(
                str(ser.errors[champ][0]).replace(str(etranger.pk), '<ID>'),
                str(absent.errors[champ][0]).replace(str(ID_ABSENT), '<ID>'))
            champ_lie = cls(context=self.ctx).fields[champ]
            self.assertEqual(champ_lie.to_internal_value(propre.pk), propre)

    def test_regle_routage_target_user(self):
        self._assert_borne(NotificationRoutingRuleSerializer, 'target_user',
                           self.user_a, self.user_b)

    def test_accuse_lecture_annonce(self):
        self._assert_borne(AnnonceLectureSerializer, 'annonce',
                           self.annonce_a, self.annonce_b)

    def test_post_regle_target_user_etranger_400(self):
        api = _api(self.admin_a)
        r = api.post(URL, {'event_type': EventType.FACTURE_OVERDUE,
                           'target_user': self.user_b.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('target_user', r.data)
        self.assertFalse(NotificationRoutingRule.objects.filter(
            target_user=self.user_b).exists())
        r_ok = api.post(URL, {'event_type': EventType.FACTURE_OVERDUE,
                              'target_user': self.user_a.pk}, format='json')
        self.assertEqual(r_ok.status_code, 201, r_ok.data)
