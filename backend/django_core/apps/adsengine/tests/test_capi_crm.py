"""ADSENG32 — Tests de l'émetteur CAPI CRM-stage (SÉPARÉ de QJ9).

Prouve : l'événement se construit sur une transition d'étape STAGES.py avec
``event_name`` = la CLÉ (jamais en dur), la dedup par ``event_id`` déterministe,
le match via leadgen_id + téléphone haché, le gating par flag propre, l'émission
via un transport injecté, le déclencheur pre_save/post_save sur ``crm.Lead``, le
moniteur EMQ visible, et la NON-RÉGRESSION de QJ9 (émetteur signature intact).
"""
import inspect
import os
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.stages import CONTACTED, NEW, QUOTE_SENT, SIGNED

from apps.adsengine import capi_crm

_ENV_ON = {
    'META_CRM_STAGE_CAPI_ENABLED': '1',
    'META_CAPI_ACCESS_TOKEN': 'tok-abc',
    'META_CAPI_PIXEL_ID': 'px-123',
}


class BuildStageEventTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CAPI Co', slug='capi-co')

    def _meta_lead(self, **kw):
        defaults = dict(
            company=self.company, nom='Prospect',
            source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
            external_system='meta_lead_ads', external_id='789456123',
            telephone='0612345678', stage=NEW)
        defaults.update(kw)
        return Lead.objects.create(**defaults)

    def test_event_name_is_stage_key_never_hardcoded(self):
        lead = self._meta_lead()
        built = capi_crm.build_stage_event(
            self.company, lead.pk, CONTACTED, old_stage=NEW, now=1000)
        self.assertTrue(built['eligible'])
        ev = built['event']
        # event_name = la CLÉ STAGES.py de la nouvelle étape.
        self.assertEqual(ev['event_name'], CONTACTED)
        self.assertEqual(ev['action_source'], 'system_generated')
        self.assertEqual(ev['custom_data']['event_source'], 'crm')
        # SCA29 white-label : source CRM neutre, jamais la marque plateforme.
        self.assertEqual(ev['custom_data']['lead_event_source'], 'ERP CRM')

    def test_match_uses_leadgen_id_and_hashed_phone(self):
        lead = self._meta_lead()
        ev = capi_crm.build_stage_event(
            self.company, lead.pk, QUOTE_SENT, old_stage=CONTACTED)['event']
        ud = ev['user_data']
        # leadgen_id (= external_id) NON haché ; téléphone haché SHA-256.
        self.assertEqual(ud['lead_id'], '789456123')
        self.assertEqual(len(ud['ph'][0]), 64)
        self.assertNotIn('0612345678', ud['ph'][0])

    def test_deterministic_event_id_dedup(self):
        lead = self._meta_lead()
        a = capi_crm.build_stage_event(
            self.company, lead.pk, SIGNED, old_stage=QUOTE_SENT, now=1)['event']
        b = capi_crm.build_stage_event(
            self.company, lead.pk, SIGNED, old_stage=NEW, now=999)['event']
        # même lead + même étape → même event_id (dedup Meta 48 h).
        self.assertEqual(a['event_id'], b['event_id'])
        self.assertEqual(a['event_id'], f'crmstage:789456123:{SIGNED}')

    def test_non_forward_not_eligible(self):
        lead = self._meta_lead()
        # transition ARRIÈRE (QUOTE_SENT → CONTACTED) → pas d'événement.
        built = capi_crm.build_stage_event(
            self.company, lead.pk, CONTACTED, old_stage=QUOTE_SENT)
        self.assertFalse(built['eligible'])
        self.assertEqual(built['reason'], 'not_forward')

    def test_non_meta_lead_not_eligible(self):
        lead = Lead.objects.create(
            company=self.company, nom='Organique',
            source=Lead.Source.OS_NATIVE, canal=Lead.Canal.TELEPHONE,
            stage=NEW)
        built = capi_crm.build_stage_event(
            self.company, lead.pk, CONTACTED, old_stage=NEW)
        self.assertFalse(built['eligible'])
        self.assertEqual(built['reason'], 'not_meta_origin')

    def test_into_cold_not_eligible(self):
        lead = self._meta_lead()
        from apps.crm.stages import COLD
        built = capi_crm.build_stage_event(
            self.company, lead.pk, COLD, old_stage=CONTACTED)
        self.assertFalse(built['eligible'])


class EmitGatingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Emit Co', slug='emit-co')
        self.lead = Lead.objects.create(
            company=self.company, nom='P', source=Lead.Source.META_LEAD_ADS,
            canal=Lead.Canal.META_ADS, external_system='meta_lead_ads',
            external_id='111', telephone='0612345678', stage=NEW)

    def test_disabled_flag_prepares_but_does_not_send(self):
        sent = []
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('META_CRM_STAGE_CAPI_ENABLED', None)
            res = capi_crm.emit_lead_stage_event(
                self.company, self.lead.pk, CONTACTED, old_stage=NEW,
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
            res = capi_crm.emit_lead_stage_event(
                self.company, self.lead.pk, CONTACTED, old_stage=NEW,
                transport=_transport)
        self.assertTrue(res['emitted'])
        self.assertEqual(len(sent), 1)
        url, payload = sent[0]
        self.assertIn('/px-123/events', url)
        self.assertIn(b'crmstage:111:CONTACTED', payload)
        self.assertIn(b'system_generated', payload)

    def test_match_quality_visible(self):
        with mock.patch.dict(os.environ, _ENV_ON):
            res = capi_crm.emit_lead_stage_event(
                self.company, self.lead.pk, CONTACTED, old_stage=NEW,
                transport=lambda u, p: (200, 'ok'))
        mq = res['match_quality']
        self.assertTrue(mq['has_lead_id'])
        self.assertTrue(mq['has_phone'])
        self.assertGreaterEqual(mq['match_keys'], 2)


class SignalTriggerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Sig Co', slug='sig-co')
        capi_crm.connect()  # idempotent (déjà câblé par ready())

    def test_forward_transition_fires_emitter(self):
        calls = []

        def _recorder(company, lead_id, new_stage, **kw):
            calls.append((lead_id, new_stage, kw.get('old_stage')))
            return {'emitted': False, 'reason': 'test'}

        # Le récepteur pre_save/post_save est gardé par META_CRM_STAGE_CAPI_ENABLED
        # (perf : aucune requête sur chaque save de Lead tant que l'intégration
        # n'est pas activée — OFF par défaut). Il faut donc l'activer pour que le
        # déclencheur atteigne l'émetteur (mocké ici).
        with mock.patch.dict(
                os.environ, {'META_CRM_STAGE_CAPI_ENABLED': '1'}), \
                mock.patch.object(capi_crm, 'emit_lead_stage_event', _recorder):
            lead = Lead.objects.create(
                company=self.company, nom='P',
                source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
                external_system='meta_lead_ads', external_id='222',
                telephone='0612000000', stage=NEW)
            lead.stage = CONTACTED
            lead.save()

        transitions = [(new, old) for (_lid, new, old) in calls]
        # la création (→ NEW) puis la transition (NEW → CONTACTED) sont émises.
        self.assertIn((CONTACTED, NEW), transitions)

    def test_no_stage_change_does_not_fire(self):
        lead = Lead.objects.create(
            company=self.company, nom='P',
            source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
            external_system='meta_lead_ads', external_id='333',
            telephone='0612111111', stage=CONTACTED)
        calls = []
        with mock.patch.object(
                capi_crm, 'emit_lead_stage_event',
                lambda *a, **k: calls.append(a)):
            lead.ville = 'Casablanca'  # édition SANS changement d'étape
            lead.save()
        self.assertEqual(calls, [])


class EmqMonitorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EMQ Co', slug='emq-co')

    def test_emq_monitor_reports_coverage_and_availability(self):
        Lead.objects.create(
            company=self.company, nom='A', source=Lead.Source.META_LEAD_ADS,
            canal=Lead.Canal.META_ADS, external_system='meta_lead_ads',
            external_id='900', telephone='0612345678', stage=NEW)
        Lead.objects.create(
            company=self.company, nom='B', source=Lead.Source.META_LEAD_ADS,
            canal=Lead.Canal.META_ADS, stage=NEW)  # pas d'identifiant fort
        with mock.patch.dict(os.environ, {'META_CAPI_ACCESS_TOKEN': 'tok'}):
            mon = capi_crm.emq_monitor(self.company)
        self.assertTrue(mon['dataset_quality_api']['available'])
        cov = mon['match_coverage']
        self.assertEqual(cov['meta_leads'], 2)
        self.assertEqual(cov['with_leadgen_id'], 1)
        self.assertEqual(cov['strong_match'], 1)


class Qj9NonRegressionTests(TestCase):
    """QJ9 (émetteur signature ventes) reste INTACT et SÉPARÉ d'ADSENG32."""

    def test_qj9_signed_quote_emitter_untouched(self):
        from apps.ventes import services as ventes_services
        src = inspect.getsource(ventes_services._fire_capi_signed_quote)
        # QJ9 émet toujours « SignedQuote » (couche document, action website).
        self.assertIn('SignedQuote', src)
        self.assertIn("'signedquote:", src.replace('"', "'"))
        # ADSENG32 (couche pipeline) n'a jamais fuité dans QJ9.
        self.assertNotIn('crmstage', src)
        self.assertNotIn('system_generated', src)

    def test_two_emitters_use_distinct_namespaces(self):
        company = Company.objects.create(nom='NS Co', slug='ns-co')
        lead = Lead.objects.create(
            company=company, nom='P', source=Lead.Source.META_LEAD_ADS,
            canal=Lead.Canal.META_ADS, external_system='meta_lead_ads',
            external_id='555', telephone='0612345678', stage=NEW)
        ev = capi_crm.build_stage_event(
            company, lead.pk, SIGNED, old_stage=QUOTE_SENT)['event']
        # ADSENG32 : event_name = clé de stade, event_id « crmstage: » — jamais
        # « SignedQuote »/« signedquote: » (QJ9). Les deux ne se croisent pas.
        self.assertEqual(ev['event_name'], SIGNED)
        self.assertTrue(ev['event_id'].startswith('crmstage:'))
        self.assertNotEqual(ev['event_name'], 'SignedQuote')
