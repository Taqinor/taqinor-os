"""ENG11 — Tests du brief hebdomadaire déterministe (v1, sans LLM).

Prouve : chiffres réels agrégés sur la fenêtre, niveau de fatigue vs seuil
2.0–2.5, 0-3 propositions liées (chacune avec reason_fr), rendu markdown, upsert
idempotent, et joignabilité + routage du beat hebdo.
"""
import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import brief as brief_mod
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, EngineAction,
    EngineAlert, InsightSnapshot, MetaConnection, WeeklyBrief,
)
from apps.adsengine.tasks import generate_weekly_brief

NOW = datetime.date(2026, 7, 16)


class BriefGeneratorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Brief Co', slug='brief-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _snap(self, *, spend, results, freq, day=NOW):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=day, spend=spend, results=results, frequency=freq)

    def test_brief_aggregates_window_numbers(self):
        self._snap(spend='120.00', results=6, freq='1.80')
        brief = brief_mod.build_brief(self.company, now=NOW)
        data = brief.data
        self.assertEqual(data['spend_semaine'], '120.00')
        self.assertEqual(data['resultats_semaine'], 6)
        self.assertEqual(data['cpl_semaine'], '20.00')
        self.assertEqual(data['fatigue']['niveau'], 'ok')
        self.assertTrue(data['sla_ok'])
        self.assertIn('# Brief hebdomadaire', brief.markdown)

    def test_high_frequency_proposes_an_applicable_rotation(self):
        # PUB130-bis — la rotation du brief passe par
        # ``services.resolve_rotation_payload`` : il lui faut donc un ad set
        # miroité ET un créatif LIVE, sinon rien n'est proposable.
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='Ad set',
            status='PAUSED', campaign=self.camp)
        ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', adset=adset, name='Ad')
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id='cr1')

        self._snap(spend='120.00', results=6, freq='2.80')
        brief = brief_mod.build_brief(self.company, now=NOW)

        self.assertEqual(brief.data['fatigue']['niveau'], 'forte')
        props = brief.data['propositions']
        self.assertTrue(any(
            p['kind'] == EngineAction.Kind.ROTATE_CREATIVE for p in props))
        self.assertTrue(all(p['reason_fr'] for p in props))
        # Payload APPLICABLE (les trois pièces de PUB119), jamais creux.
        action = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.ROTATE_CREATIVE)
        self.assertEqual(action.payload['adset_id'], 'as1')
        self.assertTrue(action.payload['name'])
        self.assertEqual(action.payload['creative'], {'creative_id': 'cr1'})
        # La cible CAMPAGNE (celle qui a déclenché) reste tracée.
        self.assertEqual(action.payload['target_meta_id'], 'c1')
        self.assertEqual(action.payload['target_type'], 'campaign')

    def test_the_brief_consumes_the_backlog_item_it_embarks(self):
        # PUB-P8/C6 — consommation SYMÉTRIQUE : le brief embarquait un item de
        # backlog SANS le sortir de la file libre, donc le brief de la semaine
        # suivante reproposait le MÊME créatif.
        from apps.adsengine.models import CreativeAsset, CreativeBacklogItem

        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='Ad set',
            status='PAUSED', campaign=self.camp)
        ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', adset=adset, name='Ad')
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id='cr1')
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', page_id='page-42')
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp={'passed': True}, meta_image_hash='hash-b',
            primary_text='Vos factures baissent.')
        item = CreativeBacklogItem.objects.create(
            company=self.company, asset=asset,
            status=CreativeBacklogItem.Statut.EN_FILE)

        self._snap(spend='120.00', results=6, freq='2.80')
        brief_mod.build_brief(self.company, now=NOW)

        action = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.ROTATE_CREATIVE)
        self.assertEqual(action.payload['backlog_item_id'], item.pk)
        item.refresh_from_db()
        self.assertEqual(item.status, CreativeBacklogItem.Statut.PROGRAMME)

    def test_high_frequency_without_any_creative_alerts_instead(self):
        # Aucun ad set miroité : le brief ALERTE explicitement et ne propose
        # RIEN (jamais une action creuse que l'approbation ferait échouer).
        self._snap(spend='120.00', results=6, freq='2.80')
        brief = brief_mod.build_brief(self.company, now=NOW)

        kinds = {p['kind'] for p in brief.data['propositions']}
        self.assertNotIn(EngineAction.Kind.ROTATE_CREATIVE, kinds)
        self.assertFalse(EngineAction.objects.filter(
            company=self.company,
            kind=EngineAction.Kind.ROTATE_CREATIVE).exists())
        alert = EngineAlert.objects.filter(
            company=self.company,
            detail__template_key='brief_rotation').first()
        self.assertIsNotNone(alert)
        self.assertIn('aucune rotation proposable', alert.message)

    def test_the_pause_reason_uses_the_real_account_currency(self):
        # PUB134 — Meta rapporte les montants dans la devise DU COMPTE.
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', currency='USD')
        self._snap(spend='80.00', results=0, freq='1.10')

        brief_mod.build_brief(self.company, now=NOW)

        action = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.PAUSE)
        self.assertIn('80.00 USD', action.reason_fr)
        self.assertNotIn('MAD', action.reason_fr)

    def test_the_pause_reason_falls_back_to_mad_without_a_connection(self):
        self._snap(spend='80.00', results=0, freq='1.10')
        brief_mod.build_brief(self.company, now=NOW)
        action = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.PAUSE)
        self.assertIn('80.00 MAD', action.reason_fr)

    def test_spend_without_results_proposes_pause(self):
        self._snap(spend='80.00', results=0, freq='1.10')
        brief = brief_mod.build_brief(self.company, now=NOW)
        kinds = {p['kind'] for p in brief.data['propositions']}
        self.assertIn(EngineAction.Kind.PAUSE, kinds)

    def test_proposals_capped_at_three(self):
        # 4 campagnes en fatigue forte → au plus 3 propositions.
        for i in range(4):
            camp = AdCampaignMirror.objects.create(
                company=self.company, meta_id=f'x{i}', name=f'C{i}',
                status='PAUSED')
            InsightSnapshot.objects.create(
                company=self.company,
                content_type=self.ct, object_id=camp.pk,
                date=NOW, spend='50.00', results=1, frequency='3.00')
        brief = brief_mod.build_brief(self.company, now=NOW)
        self.assertLessEqual(len(brief.data['propositions']), 3)

    def test_idempotent_upsert_same_week(self):
        self._snap(spend='10.00', results=1, freq='1.00')
        b1 = brief_mod.build_brief(self.company, now=NOW)
        b2 = brief_mod.build_brief(self.company, now=NOW)
        self.assertEqual(b1.id, b2.id)
        self.assertEqual(WeeklyBrief.objects.filter(
            company=self.company).count(), 1)

    def test_out_of_window_snapshot_excluded(self):
        self._snap(spend='999.00', results=0, freq='1.0',
                   day=NOW - datetime.timedelta(days=30))
        brief = brief_mod.build_brief(self.company, now=NOW)
        self.assertEqual(brief.data['spend_semaine'], '0')


class BriefTaskTests(TestCase):
    def test_task_noop_without_campaigns(self):
        Company.objects.create(nom='Empty', slug='empty')
        result = generate_weekly_brief()
        # PUB130 — le retour DIT pourquoi il n'a rien produit (société sautée
        # faute de campagne miroitée), au lieu d'un 0 muet indiagnosticable.
        self.assertEqual(result, {'briefs_generated': 0,
                                  'skipped_no_campaign': 1, 'failed': 0})

    def test_task_generates_for_company_with_campaign(self):
        company = Company.objects.create(nom='Has', slug='has')
        AdCampaignMirror.objects.create(
            company=company, meta_id='c1', name='C', status='PAUSED')
        result = generate_weekly_brief()
        self.assertEqual(result, {'briefs_generated': 1,
                                  'skipped_no_campaign': 0, 'failed': 0})
        self.assertTrue(WeeklyBrief.objects.filter(company=company).exists())


class BriefBeatReachabilityTests(SimpleTestCase):
    def test_task_is_scheduled(self):
        from erp_agentique.celery import app
        names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('adsengine.generate_weekly_brief', names)

    def test_task_routed_to_scheduled(self):
        route = settings.CELERY_TASK_ROUTES['adsengine.generate_weekly_brief']
        self.assertEqual(route['queue'], 'scheduled')
