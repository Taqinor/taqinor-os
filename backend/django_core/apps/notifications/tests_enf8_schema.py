"""ENF8 — schéma OpenAPI exact de l'app notifications (décision D2 : JSON seul).

Aucune vue de cette app ne reçoit de fichier : toutes n'acceptent que du JSON,
et les sérialiseurs annoncent le vrai type de leurs champs calculés.
"""
from django.test import SimpleTestCase
from rest_framework.parsers import JSONParser

from . import views
from .serializers import AnnonceSerializer, NotificationSerializer


class NotificationsSchemaTests(SimpleTestCase):
    def test_viewsets_json_seul(self):
        for vue in (
            views.NotificationViewSet, views.NotificationPreferenceViewSet,
            views.NotificationRoutingRuleViewSet,
            views.WorkingHoursConfigViewSet, views.HolidayViewSet,
            views.WhatsAppTemplateViewSet, views.AnnonceViewSet,
            views.MessageAccueilViewSet,
        ):
            with self.subTest(vue=vue.__name__):
                self.assertEqual(vue.parser_classes, [JSONParser])

    def test_fonctions_push_json_seul(self):
        for fn in (views.push_subscribe, views.push_unsubscribe):
            with self.subTest(vue=fn.__name__):
                self.assertEqual(fn.cls.parser_classes, [JSONParser])

    def test_champs_calcules_types(self):
        annonce = AnnonceSerializer().fields
        self.assertTrue(annonce['is_expiree'].read_only)
        notif = NotificationSerializer().fields
        self.assertEqual(type(notif['reason']).__name__, 'CharField')
