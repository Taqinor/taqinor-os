"""NTOBS26 — ``core.events.incident_opened``/``incident_resolved`` sont émis
à la création/résolution d'un ``IncidentPublic``, pour TOUT incident (système
OU société) — contrairement à la notification email des abonnés publics
(NTOBS15, ``test_ntobs15_status_subscriber.py``), réservée aux incidents
SYSTÈME (``company=None``)."""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core import events

from ..models import IncidentPublic


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class IncidentBusEventsTests(TestCase):
    def setUp(self):
        self.recus_ouverts = []
        self.recus_resolus = []
        events.incident_opened.connect(
            self._capter_ouvert, dispatch_uid='test_ntobs26_ouvert')
        events.incident_resolved.connect(
            self._capter_resolu, dispatch_uid='test_ntobs26_resolu')
        self.addCleanup(
            events.incident_opened.disconnect,
            dispatch_uid='test_ntobs26_ouvert')
        self.addCleanup(
            events.incident_resolved.disconnect,
            dispatch_uid='test_ntobs26_resolu')

    def _capter_ouvert(self, sender, **kwargs):
        self.recus_ouverts.append(kwargs)

    def _capter_resolu(self, sender, **kwargs):
        self.recus_resolus.append(kwargs)

    def test_creation_emet_incident_opened_pour_incident_systeme(self):
        incident = IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
        self.assertEqual(len(self.recus_ouverts), 1)
        self.assertEqual(self.recus_ouverts[0]['incident'].pk, incident.pk)
        self.assertIsNone(self.recus_ouverts[0]['company'])

    def test_creation_emet_incident_opened_pour_incident_societe(self):
        # Contrairement à l'email NTOBS15 (réservé au système), le bus émet
        # aussi pour un incident société-spécifique.
        co = make_company('ntobs26-co', 'NTOBS26 Co')
        incident = IncidentPublic.objects.create(
            titre='Panne locale', company=co, debute_le=timezone.now())
        self.assertEqual(len(self.recus_ouverts), 1)
        self.assertEqual(self.recus_ouverts[0]['incident'].pk, incident.pk)
        self.assertEqual(self.recus_ouverts[0]['company'], co)

    def test_resolution_emet_incident_resolved_une_seule_fois(self):
        incident = IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
        self.recus_ouverts.clear()

        incident.statut = IncidentPublic.Statut.RESOLVED
        incident.save()
        self.assertEqual(len(self.recus_resolus), 1)
        self.assertEqual(self.recus_resolus[0]['incident'].pk, incident.pk)

        # Rejouer un save sans changement de statut ne réémet rien.
        incident.description = 'note'
        incident.save()
        self.assertEqual(len(self.recus_resolus), 1)

    def test_un_abonne_qui_leve_ne_bloque_pas_la_creation(self):
        def casse(sender, **kwargs):
            raise RuntimeError('webhook injoignable')

        events.incident_opened.connect(casse, dispatch_uid='test_ntobs26_casse')
        self.addCleanup(
            events.incident_opened.disconnect, dispatch_uid='test_ntobs26_casse')
        # Ne doit lever aucune exception.
        IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
