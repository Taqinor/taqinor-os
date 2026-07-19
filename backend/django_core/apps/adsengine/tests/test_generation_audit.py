"""AGEN9 — Tests audit de génération + rollback (§10.2 point 6).

Prouve :
  * la décote posterior est PURE (0 ⇒ prior, 1 ⇒ inchangé, 0.5 ⇒ à mi-chemin) et
    ``decay_node`` la persiste ;
  * le registre de quarantaine (cache) : poser / lire / lever ;
  * ``record_audit`` pose la version + fusionne les verdicts ;
  * ``audit_snapshot`` assemble version / verdicts / décision / statuts Meta /
    bras ;
  * ``rollback_batch`` en quelques appels : pause du bras (client gardé
    PAUSED-only) + désactivation, décote du nœud, quarantaine effective (le
    gabarit ne peut plus régénérer via AGEN7), alerte 🔴 émise.
"""
from unittest.mock import Mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import generation_audit as ga
from apps.adsengine.models import (
    AdMirror, AssumptionNode, CreativeAsset, CreativeBacklogItem,
    CreativeGenerationBatch,
    EngineAction, EngineAlert, Experiment, ExperimentArm,
)


class DecayPosteriorPureTests(SimpleTestCase):
    def test_factor_zero_resets_to_prior(self):
        self.assertEqual(ga.decay_posterior(9, 3, 1, 1, factor=0.0), (1.0, 1.0))

    def test_factor_one_unchanged(self):
        self.assertEqual(ga.decay_posterior(9, 3, 1, 1, factor=1.0), (9.0, 3.0))

    def test_factor_half_midway(self):
        self.assertEqual(ga.decay_posterior(9, 3, 1, 1, factor=0.5), (5.0, 2.0))

    def test_factor_clamped(self):
        # factor > 1 borné à 1 (inchangé), < 0 borné à 0 (prior).
        self.assertEqual(ga.decay_posterior(9, 3, 1, 1, factor=5), (9.0, 3.0))
        self.assertEqual(ga.decay_posterior(9, 3, 1, 1, factor=-2), (1.0, 1.0))


class QuarantineRegistryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Q Co', slug='q-co')

    def test_set_read_lift(self):
        self.assertFalse(ga.is_template_quarantined(self.company, 'eco'))
        ga.quarantine_template(self.company, 'eco')
        self.assertTrue(ga.is_template_quarantined(self.company, 'eco'))
        ga.lift_quarantine(self.company, 'eco')
        self.assertFalse(ga.is_template_quarantined(self.company, 'eco'))

    def test_empty_key_never_quarantines(self):
        self.assertFalse(ga.quarantine_template(self.company, ''))
        self.assertFalse(ga.is_template_quarantined(self.company, ''))


class AuditRecordTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='A Co', slug='a-co')
        self.batch = CreativeGenerationBatch.objects.create(company=self.company)

    def test_record_sets_version_and_merges_verdicts(self):
        ga.record_audit(self.batch, fact_table_version=3,
                        claim_verdicts={'economie_pct': 'grounded'})
        ga.record_audit(self.batch, claim_verdicts={'kwc': 'grounded'})
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.fact_table_version, 3)
        # Fusion, jamais écrasement muet.
        self.assertEqual(self.batch.claim_verdicts,
                         {'economie_pct': 'grounded', 'kwc': 'grounded'})

    def test_snapshot_shape(self):
        asset = CreativeAsset.objects.create(
            company=self.company,
            asset_type=CreativeAsset.AssetType.EXPLAINER, policy_stamp={})
        self.batch.source_hook_asset = asset
        self.batch.save(update_fields=['source_hook_asset'])
        exp = Experiment.objects.create(company=self.company, name='E1')
        ExperimentArm.objects.create(
            company=self.company, experiment=exp, creative_asset=asset,
            label='A', ad_id='ad-1')
        AdMirror.objects.create(
            company=self.company, meta_id='ad-1', status='ACTIVE')
        snap = ga.audit_snapshot(self.batch)
        self.assertEqual(snap['batch_id'], self.batch.pk)
        self.assertEqual(len(snap['arms']), 1)
        self.assertEqual(snap['meta_statuses'], {'ad-1': 'ACTIVE'})


class RollbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='R Co', slug='r-co')
        self.asset = CreativeAsset.objects.create(
            company=self.company,
            asset_type=CreativeAsset.AssetType.EXPLAINER, policy_stamp={})
        self.batch = CreativeGenerationBatch.objects.create(
            company=self.company, source_hook_asset=self.asset)
        self.exp = Experiment.objects.create(company=self.company, name='E')
        self.arm = ExperimentArm.objects.create(
            company=self.company, experiment=self.exp,
            creative_asset=self.asset, label='A', ad_id='ad-9', is_active=True)
        self.node = AssumptionNode.objects.create(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Hypothèse', enjeux_s=0.5, pertinence_r=0.5,
            alpha=9.0, beta=3.0, alpha0=1.0, beta0=1.0)

    def test_rollback_pauses_decays_quarantines(self):
        client = Mock()
        result = ga.rollback_batch(
            self.batch, template_key='eco', nodes=[self.node], client=client)

        # 1. Pause : bras désactivé + client appelé PAUSED-only.
        self.arm.refresh_from_db()
        self.assertFalse(self.arm.is_active)
        client.update_status_paused.assert_called_once_with(
            object_id='ad-9', level='ad')
        self.assertEqual(result['ads_paused'], 1)
        # Trace d'audit : une EngineAction PAUSE auto.
        act = EngineAction.objects.get(kind=EngineAction.Kind.PAUSE)
        self.assertTrue(act.auto)
        self.assertEqual(act.status, EngineAction.Statut.APPROUVEE)

        # 2. Décote posterior appliquée + persistée (9,3 → mi-chemin de 1,1).
        self.node.refresh_from_db()
        self.assertEqual((self.node.alpha, self.node.beta), (5.0, 2.0))

        # 3. Quarantaine effective : le flag lot + le marqueur cache.
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.template_quarantined)
        self.assertTrue(ga.is_template_quarantined(self.company, 'eco'))

        # Alerte 🔴 émise.
        self.assertTrue(
            EngineAlert.objects.filter(
                company=self.company, severity='critical').exists())

    def test_quarantine_blocks_regeneration_via_agen7(self):
        # Le rollback met « eco » en quarantaine ; AGEN7 refuse alors de générer.
        import os
        from unittest.mock import patch

        from apps.adsengine import video_queue
        ga.rollback_batch(self.batch, template_key='eco')
        with patch.dict(os.environ, {'JSON2VIDEO_API_KEY': 'k'}, clear=False):
            video = video_queue.generate_video(
                self.company, template_key='eco', http_client=Mock())
        self.assertIsNone(video)

    def test_rollback_without_client_still_deactivates_arm(self):
        result = ga.rollback_batch(self.batch, template_key='eco')
        self.arm.refresh_from_db()
        self.assertFalse(self.arm.is_active)
        self.assertEqual(result['ads_paused'], 0)  # pas de client → pas d'appel
        self.assertTrue(self.batch.template_quarantined
                        or CreativeGenerationBatch.objects.get(
                            pk=self.batch.pk).template_quarantined)


class AssetProvenanceTests(TestCase):
    """PUB84 — Piste de provenance durable PAR ASSET (fait cité → version
    table de faits → verdicts → décision humaine), consultable même après que
    le rapport de génération d'origine se soit « dispersé »."""

    def setUp(self):
        self.company = Company.objects.create(nom='Prov Co', slug='prov-co')

    def test_manual_asset_has_no_batch_but_keeps_policy_stamp(self):
        asset = CreativeAsset.objects.create(
            company=self.company,
            asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp={'passed': True, 'rules_checked': ['r1']})
        prov = ga.asset_provenance(asset)
        self.assertEqual(prov['asset_id'], asset.pk)
        self.assertIsNone(prov['batch_id'])
        self.assertEqual(prov['claim_verdicts'], {})
        self.assertIsNone(prov['human_decision'])
        self.assertIsNone(prov['meta_status'])
        self.assertEqual(
            prov['policy_stamp'], {'passed': True, 'rules_checked': ['r1']})

    def test_generated_asset_surfaces_fact_table_version_and_verdicts(self):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.EXPLAINER,
            policy_stamp={'passed': True})
        batch = CreativeGenerationBatch.objects.create(
            company=self.company, status=CreativeGenerationBatch.Statut.APPROUVEE)
        ga.record_audit(
            batch, fact_table_version=5,
            claim_verdicts={'economie_pct': 'grounded'})
        CreativeBacklogItem.objects.create(
            company=self.company, asset=asset, batch=batch,
            source=CreativeBacklogItem.Source.RECOMBINAISON)
        exp = Experiment.objects.create(company=self.company, name='E')
        ExperimentArm.objects.create(
            company=self.company, experiment=exp, creative_asset=asset,
            label='A', ad_id='ad-prov-1')
        AdMirror.objects.create(
            company=self.company, meta_id='ad-prov-1', status='ACTIVE')

        prov = ga.asset_provenance(asset)
        self.assertEqual(prov['batch_id'], batch.pk)
        self.assertEqual(prov['fact_table_version'], 5)
        self.assertEqual(
            prov['claim_verdicts'], {'economie_pct': 'grounded'})
        self.assertEqual(prov['meta_status'], 'ACTIVE')
        self.assertEqual(prov['human_decision']['status'],
                         CreativeGenerationBatch.Statut.APPROUVEE)

    def test_quarantined_batch_flag_surfaced(self):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp={})
        batch = CreativeGenerationBatch.objects.create(
            company=self.company, template_quarantined=True)
        CreativeBacklogItem.objects.create(
            company=self.company, asset=asset, batch=batch,
            source=CreativeBacklogItem.Source.RECOMBINAISON)
        prov = ga.asset_provenance(asset)
        self.assertTrue(prov['template_quarantined'])


class DecayNodeTests(TestCase):
    def test_decay_node_persists(self):
        company = Company.objects.create(nom='D Co', slug='d-co')
        node = AssumptionNode.objects.create(
            company=company, classe=AssumptionNode.Classe.ANGLE,
            enonce_fr='X', enjeux_s=0.4, pertinence_r=0.6,
            alpha=5.0, beta=5.0, alpha0=1.0, beta0=1.0)
        ga.decay_node(node, factor=0.5)
        node.refresh_from_db()
        self.assertEqual((node.alpha, node.beta), (3.0, 3.0))
