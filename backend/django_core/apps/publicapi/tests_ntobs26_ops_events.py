"""NTOBS26 — webhooks sortants ``incident_opened``/``incident_resolved``/
``maintenance_window_announced``.

L'émission passe par ``core.events`` (bus M6, ``apps.statuspage.receivers``
et ``core.maintenance_windows``), la livraison par
``delivery.dispatch_event`` — MÊME transport que tous les autres webhooks
(voir ``tests_nti18n43_langue_changed.py``, patron identique)."""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from . import delivery, ops_event_receivers
from .constants import (
    ALL_EVENTS, EVENT_CHOICES, EVENT_INCIDENT_OPENED, EVENT_INCIDENT_RESOLVED,
    EVENT_MAINTENANCE_WINDOW_ANNOUNCED,
)
from .models import Webhook


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class VocabulaireTests(SimpleTestCase):
    """Les trois évènements font partie du vocabulaire abonnable, une seule
    fois, sous la clé littéralement nommée par le plan NTOBS26."""

    def test_evenements_au_catalogue_une_seule_fois(self):
        codes = [code for code, _ in EVENT_CHOICES]
        for event in (EVENT_INCIDENT_OPENED, EVENT_INCIDENT_RESOLVED,
                      EVENT_MAINTENANCE_WINDOW_ANNOUNCED):
            self.assertIn(event, ALL_EVENTS)
            self.assertEqual(codes.count(event), 1)

    def test_les_codes_sont_ceux_nommes_par_le_plan(self):
        self.assertEqual(EVENT_INCIDENT_OPENED, 'incident_opened')
        self.assertEqual(EVENT_INCIDENT_RESOLVED, 'incident_resolved')
        self.assertEqual(
            EVENT_MAINTENANCE_WINDOW_ANNOUNCED, 'maintenance_window_announced')


class _Incident:
    def __init__(self, pk=1):
        self.id = pk
        self.titre = 'Panne API'
        self.severite = 'majeure'
        self.statut = 'investigating'
        self.region = 'ma-casablanca'
        self.debute_le = None
        self.resolu_le = None


class _Fenetre:
    def __init__(self, pk=1):
        self.id = pk
        self.region = ''
        self.impact = 'degrade'
        self.statut = 'planifie'
        self.debute_le = None
        self.termine_le = None


class LivraisonWebhookTests(TestCase):
    """Le récepteur ``publicapi`` traduit chaque signal en webhook sortant."""

    def setUp(self):
        self.co = make_company('pa-ntobs26', 'PA NTOBS26')

    def test_incident_opened_livre_le_payload_attendu(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            ops_event_receivers.on_incident_opened(
                sender=None, incident=_Incident(7), company=self.co)
        m.assert_called_once()
        args, _kwargs = m.call_args
        self.assertEqual(args[0], self.co.id)
        self.assertEqual(args[1], EVENT_INCIDENT_OPENED)
        self.assertEqual(args[2]['incident_id'], 7)
        self.assertEqual(args[2]['statut'], 'investigating')

    def test_incident_resolved_livre_le_payload_attendu(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            ops_event_receivers.on_incident_resolved(
                sender=None, incident=_Incident(8), company=self.co)
        args, _kwargs = m.call_args
        self.assertEqual(args[1], EVENT_INCIDENT_RESOLVED)
        self.assertEqual(args[2]['incident_id'], 8)

    def test_maintenance_window_announced_livre_le_payload_attendu(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            ops_event_receivers.on_maintenance_window_announced(
                sender=None, fenetre=_Fenetre(3), company=self.co)
        args, _kwargs = m.call_args
        self.assertEqual(args[1], EVENT_MAINTENANCE_WINDOW_ANNOUNCED)
        self.assertEqual(args[2]['fenetre_id'], 3)
        self.assertEqual(args[2]['impact'], 'degrade')

    def test_incident_systeme_sans_societe_ne_livre_rien(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            ops_event_receivers.on_incident_opened(
                sender=None, incident=_Incident(9), company=None)
        m.assert_not_called()

    def test_fenetre_systeme_sans_societe_ne_livre_rien(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            ops_event_receivers.on_maintenance_window_announced(
                sender=None, fenetre=_Fenetre(4), company=None)
        m.assert_not_called()

    def test_une_livraison_en_echec_ne_remonte_pas(self):
        with mock.patch.object(
                delivery, 'dispatch_event',
                side_effect=RuntimeError('cible morte')):
            with self.assertLogs(
                    'apps.publicapi.ops_event_receivers', level='ERROR'):
                ops_event_receivers.on_incident_opened(
                    sender=None, incident=_Incident(10), company=self.co)

    def test_un_webhook_peut_sabonner_aux_trois_evenements(self):
        webhook = Webhook.objects.create(
            company=self.co, target_url='https://exemple.test/hook',
            secret=Webhook.generate_secret(),
            events=[EVENT_INCIDENT_OPENED, EVENT_INCIDENT_RESOLVED,
                    EVENT_MAINTENANCE_WINDOW_ANNOUNCED])
        self.assertTrue(webhook.subscribes_to(EVENT_INCIDENT_OPENED))
        self.assertTrue(webhook.subscribes_to(EVENT_INCIDENT_RESOLVED))
        self.assertTrue(
            webhook.subscribes_to(EVENT_MAINTENANCE_WINDOW_ANNOUNCED))
