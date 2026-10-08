"""APAR23 — l'idempotence des balayages repose sur un MARQUEUR d'émission
indépendant des préférences de canal (C-APAR-029) : in-app coupé (push
seul), deux passages à 15 min d'écart ne rediffusent pas le même lead chaud.
Horloge FIXE (`now=`), préférences réelles.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm import horaires
from apps.crm.models import Lead
from apps.crm.stages import NEW
from authentication.models import Company

from . import sweeps
from .models import MarqueurEmissionBalayage, Notification, NotificationPreference
from .types_evenements import EventType

User = get_user_model()
CASA = horaires.CASABLANCA
#: Mardi 1er septembre 2026 — jour ouvré.
ARRIVEE = datetime.datetime(2026, 9, 1, 8, 45, tzinfo=CASA)
PASSAGE_1 = datetime.datetime(2026, 9, 1, 10, 0, tzinfo=CASA)
PASSAGE_2 = PASSAGE_1 + datetime.timedelta(minutes=15)


class MarqueurEmissionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR23', slug='apar23')
        self.manager = User.objects.create_user(
            username='apar23-mgr', password='x', role_legacy='responsable',
            company=self.company)
        self.commerciale = User.objects.create_user(
            username='apar23-com', password='x', role_legacy='commercial',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect chaud',
            owner=self.commerciale, stage=NEW,
            source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
            score=90)
        Lead.objects.filter(pk=self.lead.pk).update(date_creation=ARRIVEE)

    def _prefs(self, in_app):
        for user in (self.manager, self.commerciale):
            NotificationPreference.objects.update_or_create(
                user=user, event_type=EventType.HOT_LEAD_UNREAD,
                defaults={'company': self.company, 'in_app': in_app,
                          'push': True, 'email': False, 'whatsapp': False})

    def _passage(self, now):
        # notify() juge les heures calmes sur l'horloge : figée au passage.
        with mock.patch.object(sweeps, 'notify', wraps=sweeps.notify) as espion, \
                mock.patch('apps.notifications.services.timezone.now',
                           return_value=now):
            with self.captureOnCommitCallbacks(execute=True):
                sweeps._sweep_hot_leads(self.company, now=now)
        return espion.call_count

    def test_in_app_coupe_pas_de_rediffusion(self):
        self._prefs(in_app=False)
        premier = self._passage(PASSAGE_1)
        self.assertGreaterEqual(premier, 1)
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).exists())
        self.assertEqual(self._passage(PASSAGE_2), 0)

    def test_in_app_actif_non_regression(self):
        self._prefs(in_app=True)
        self.assertGreaterEqual(self._passage(PASSAGE_1), 1)
        self.assertEqual(self._passage(PASSAGE_2), 0)

    def test_marqueur_survit_a_la_suppression_de_la_notification(self):
        self._prefs(in_app=True)
        self._passage(PASSAGE_1)
        Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).delete()
        self.assertTrue(MarqueurEmissionBalayage.objects.filter(
            company=self.company, event_type=EventType.HOT_LEAD_UNREAD,
            cle=f'lead:{self.lead.pk}').exists())
        self.assertEqual(self._passage(PASSAGE_2), 0)

    def test_quotidien_sans_notification(self):
        lien = '/ventes/factures?facture=1'
        self.assertFalse(sweeps._already_notified_today(
            self.company, EventType.FACTURE_OVERDUE, lien))
        self.assertTrue(sweeps._already_notified_today(
            self.company, EventType.FACTURE_OVERDUE, lien))
        self.assertFalse(Notification.objects.exists())
