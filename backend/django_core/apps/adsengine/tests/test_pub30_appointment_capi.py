"""PUB30 — Événement CAPI dédié « visite technique effectuée » (Appointment
EFFECTUE), SÉPARÉ de l'événement CRM-stage ADSENG32 mais même famille/gating.

Couvre :
  - ``capi_crm.build_appointment_event`` : event_name mappé en DONNÉES
    (``APPOINTMENT_EVENT_NAMES``, jamais en dur), event_id déterministe PAR
    RENDEZ-VOUS, éligibilité (origine Meta requise, statut mappé requis) ;
  - ``capi_crm.emit_appointment_effectue_event`` : même chaîne de portes que
    ``emit_lead_stage_event`` (disabled/no_token/no_pixel/sent) ;
  - le déclencheur : ``crm.Appointment`` PLANIFIE → EFFECTUE émet
    ``core.events.appointment_effectue`` UNE SEULE FOIS (jamais sur un save
    sans changement de statut) ; ``adsengine.receivers.on_appointment_effectue``
    relaie vers ``capi_crm`` sans jamais importer ``apps.crm.models``.
"""
import os
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Appointment, Lead
from apps.crm.stages import NEW

from apps.adsengine import capi_crm

_ENV_ON = {
    'META_CRM_STAGE_CAPI_ENABLED': '1',
    'META_CAPI_ACCESS_TOKEN': 'tok-abc',
    'META_CAPI_PIXEL_ID': 'px-123',
}


def _meta_lead(company, **kw):
    defaults = dict(
        company=company, nom='Prospect',
        source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
        external_system='meta_lead_ads', external_id='321654987',
        telephone='0612345678', stage=NEW)
    defaults.update(kw)
    return Lead.objects.create(**defaults)


class BuildAppointmentEventTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Appt Co', slug='appt-co')

    def test_event_name_from_data_mapping_not_hardcoded(self):
        lead = _meta_lead(self.company)
        built = capi_crm.build_appointment_event(
            self.company, lead.pk, 999, 'effectue', now=1000)
        self.assertTrue(built['eligible'])
        self.assertEqual(
            built['event']['event_name'],
            capi_crm.APPOINTMENT_EVENT_NAMES['effectue'])
        self.assertEqual(built['event']['custom_data']['event_source'], 'crm')

    def test_unmapped_statut_not_eligible(self):
        lead = _meta_lead(self.company)
        built = capi_crm.build_appointment_event(
            self.company, lead.pk, 1, 'planifie')
        self.assertFalse(built['eligible'])
        self.assertEqual(built['reason'], 'unmapped_statut')

    def test_non_meta_lead_not_eligible(self):
        lead = Lead.objects.create(
            company=self.company, nom='Organique',
            source=Lead.Source.OS_NATIVE, canal=Lead.Canal.TELEPHONE,
            stage=NEW)
        built = capi_crm.build_appointment_event(
            self.company, lead.pk, 2, 'effectue')
        self.assertFalse(built['eligible'])
        self.assertEqual(built['reason'], 'not_meta_origin')

    def test_deterministic_event_id_per_appointment(self):
        lead = _meta_lead(self.company)
        a = capi_crm.build_appointment_event(
            self.company, lead.pk, 555, 'effectue', now=1)['event']
        b = capi_crm.build_appointment_event(
            self.company, lead.pk, 555, 'effectue', now=999)['event']
        self.assertEqual(a['event_id'], b['event_id'])
        self.assertEqual(a['event_id'], 'apptdone:321654987:555')
        # Un AUTRE rendez-vous du même lead a un event_id DIFFÉRENT.
        c = capi_crm.build_appointment_event(
            self.company, lead.pk, 556, 'effectue')['event']
        self.assertNotEqual(a['event_id'], c['event_id'])

    def test_distinct_from_stage_and_signed_quote_namespaces(self):
        lead = _meta_lead(self.company)
        ev = capi_crm.build_appointment_event(
            self.company, lead.pk, 1, 'effectue')['event']
        self.assertTrue(ev['event_id'].startswith('apptdone:'))
        self.assertNotEqual(ev['event_name'], 'SignedQuote')
        self.assertFalse(ev['event_id'].startswith('crmstage:'))


class EmitAppointmentEventGatingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Emit Appt', slug='emit-appt')
        self.lead = _meta_lead(self.company)

    def test_disabled_flag_prepares_but_does_not_send(self):
        sent = []
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('META_CRM_STAGE_CAPI_ENABLED', None)
            res = capi_crm.emit_appointment_effectue_event(
                self.company, self.lead.pk, 42,
                transport=lambda u, p: sent.append((u, p)) or (200, 'ok'))
        self.assertFalse(res['emitted'])
        self.assertEqual(res['reason'], 'disabled')
        self.assertEqual(sent, [])

    def test_enabled_sends_via_transport(self):
        sent = []

        def _transport(url, payload):
            sent.append((url, payload))
            return 200, '{"events_received":1}'

        with mock.patch.dict(os.environ, _ENV_ON):
            res = capi_crm.emit_appointment_effectue_event(
                self.company, self.lead.pk, 42, transport=_transport)
        self.assertTrue(res['emitted'])
        self.assertEqual(len(sent), 1)
        url, payload = sent[0]
        self.assertIn('/px-123/events', url)
        self.assertIn(b'apptdone:321654987:42', payload)

    def test_no_op_without_keys_is_logged_silent(self):
        """Sans clés : no-op silencieux (jamais d'exception)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('META_CRM_STAGE_CAPI_ENABLED', None)
            res = capi_crm.emit_appointment_effectue_event(
                self.company, self.lead.pk, 42,
                transport=lambda u, p: (200, 'ok'))
        self.assertFalse(res['emitted'])
        self.assertIn(res['reason'], ('disabled', 'no_token', 'no_pixel'))


class AppointmentSignalTriggerTests(TestCase):
    """Le déclencheur crm (pre_save/post_save Appointment) + le relais
    adsengine (core.events.appointment_effectue → capi_crm)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Sig Appt', slug='sig-appt')
        self.lead = Lead.objects.create(
            company=self.company, nom='P', stage=NEW)

    def test_transition_to_effectue_fires_emitter_once(self):
        calls = []

        def _recorder(company, lead_id, appointment_id, **kw):
            calls.append((lead_id, appointment_id))
            return {'emitted': False, 'reason': 'test'}

        with mock.patch.object(
                capi_crm, 'emit_appointment_effectue_event', _recorder):
            appt = Appointment.objects.create(
                company=self.company, lead=self.lead,
                scheduled_at=timezone.now(),
                statut=Appointment.Statut.PLANIFIE)
            self.assertEqual(calls, [])  # PLANIFIE → pas d'émission.
            appt.statut = Appointment.Statut.EFFECTUE
            appt.save()
            self.assertEqual(calls, [(self.lead.pk, appt.pk)])
            # Re-save SANS changement de statut → aucune ré-émission.
            appt.notes = 'Compte-rendu'
            appt.save()
            self.assertEqual(calls, [(self.lead.pk, appt.pk)])

    def test_transition_to_other_statut_never_fires(self):
        calls = []
        with mock.patch.object(
                capi_crm, 'emit_appointment_effectue_event',
                lambda *a, **k: calls.append(a) or {'emitted': False}):
            appt = Appointment.objects.create(
                company=self.company, lead=self.lead,
                scheduled_at=timezone.now(),
                statut=Appointment.Statut.PLANIFIE)
            appt.statut = Appointment.Statut.NO_SHOW
            appt.save()
        self.assertEqual(calls, [])
