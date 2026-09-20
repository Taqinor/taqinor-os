"""PUB126 — Étiquette « généré par IA » par asset (divulgation exigée par Meta).

Aucun champ ne portait la divulgation. Ces tests prouvent :

  * l'étiquette est posée PAR LA LANE de fabrique (génération / fal) et HÉRITÉE
    du parent (une variante d'un asset IA reste de l'IA) ;
  * un asset chantier RÉEL n'est jamais sur-étiqueté (une fausse divulgation est
    un mensonge de plus, pas une précaution) ;
  * la check-list policy BLOQUE un asset qui devrait être étiqueté et ne l'est
    pas — même si l'humain a coché TOUTES les règles interdites ;
  * le fragment de divulgation propagé dans un payload de créatif porte
    l'étiquette, et n'invente AUCUN nom de champ Graph tant que le champ officiel
    n'est pas confirmé.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import creative_factory as cf
from apps.adsengine import generation, policy
from apps.adsengine.models import CreativeAsset


class LaneMappingTests(SimpleTestCase):
    def test_generative_lanes_are_labelled(self):
        for lane in ('gen', 'fal', 'recombine'):
            self.assertTrue(cf.lane_is_ai_generated(lane), lane)

    def test_real_content_lanes_are_never_labelled(self):
        for lane in ('chantier', 'temoignage', 'upload', '', None):
            self.assertFalse(cf.lane_is_ai_generated(lane), lane)

    def test_label_is_inherited_from_an_ai_parent(self):
        class _Parent:
            ai_generated = True

        # Lane de SUBSTITUTION (templated) : elle ne génère rien…
        self.assertFalse(cf.asset_is_ai_generated('templated'))
        # …mais une variante DÉRIVÉE d'un asset IA reste de l'IA.
        self.assertTrue(cf.asset_is_ai_generated('templated', _Parent()))


class GenerationLaneStampsTheLabelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AI Co', slug='ai-co')

    def test_grounded_generation_labels_its_assets(self):
        # Générateur injecté (aucune clé, aucun réseau) : une variante SANS
        # chiffre passe le contrôle d'ancrage et devient un asset.
        def fake_generator(context):
            return [{'hook_text': 'Passez au solaire',
                     'primary_text': 'Devis gratuit', 'cta': 'En savoir plus',
                     'claims': []}]

        report = generation.generate_grounded_variants(
            self.company, 'solaire', generator=fake_generator)
        self.assertEqual(len(report['assets']), 1, report)
        asset = report['assets'][0]
        self.assertEqual(asset.source_lane, 'gen')
        self.assertTrue(asset.ai_generated)

    def test_factory_adapter_labels_by_lane(self):
        adapter = cf.FalAdapter()
        with patch.object(cf.CreativeFactoryAdapter, 'is_enabled',
                          return_value=True), \
             patch.object(cf.FalAdapter, 'submit', return_value='job-1'), \
             patch.object(cf.FalAdapter, 'poll', return_value=b'img'), \
             patch.object(cf, '_store_bytes', return_value='k/1.png'):
            asset = adapter.run(self.company, {})
        self.assertIsNotNone(asset)
        self.assertEqual(asset.source_lane, 'fal')
        self.assertTrue(asset.ai_generated)

    def test_real_chantier_photo_is_not_over_labelled(self):
        # La lane ``chantier`` ne génère rien : aucune divulgation IA.
        self.assertFalse(cf.lane_is_ai_generated('chantier'))
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            source_lane='chantier', depicts_real_client=True,
            ai_generated=cf.lane_is_ai_generated('chantier'))
        self.assertFalse(asset.ai_generated)


class ChecklistBlocksUnlabelledAiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CB Co', slug='cb-co')
        self.all_keys = [r['key'] for r in policy.DEFAULT_FORBIDDEN]

    def _asset(self, **kwargs):
        defaults = {'asset_type': CreativeAsset.AssetType.STATIC,
                    'policy_stamp': {}}
        defaults.update(kwargs)
        return CreativeAsset.objects.create(company=self.company, **defaults)

    def test_ai_asset_without_the_label_never_passes(self):
        asset = self._asset(source_lane='gen', ai_generated=False)
        policy.record_policy_check(asset, confirmed_keys=self.all_keys)
        asset.refresh_from_db()
        self.assertFalse(asset.is_policy_passed)
        self.assertEqual(asset.policy_stamp['ai_disclosure_block'],
                         policy.AI_DISCLOSURE_BLOCK)
        self.assertIn('IA', asset.policy_stamp['ai_disclosure_block_label'])

    def test_same_asset_passes_once_labelled(self):
        asset = self._asset(source_lane='gen', ai_generated=True)
        policy.record_policy_check(asset, confirmed_keys=self.all_keys)
        asset.refresh_from_db()
        self.assertTrue(asset.is_policy_passed)
        self.assertNotIn('ai_disclosure_block', asset.policy_stamp)

    def test_non_ai_asset_is_unaffected(self):
        asset = self._asset(source_lane='upload', ai_generated=False)
        policy.record_policy_check(asset, confirmed_keys=self.all_keys)
        asset.refresh_from_db()
        self.assertTrue(asset.is_policy_passed)
        self.assertIsNone(policy.ai_disclosure_block_reason(asset))

    def test_variant_of_an_ai_parent_must_be_labelled_too(self):
        parent = self._asset(source_lane='gen', ai_generated=True)
        child = self._asset(source_lane='templated', ai_generated=False,
                            parent=parent)
        self.assertEqual(
            policy.ai_disclosure_block_reason(child),
            policy.AI_DISCLOSURE_BLOCK)
        policy.record_policy_check(child, confirmed_keys=self.all_keys)
        child.refresh_from_db()
        self.assertFalse(child.is_policy_passed)


class DisclosurePayloadTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='DP Co', slug='dp-co')

    def test_payload_carries_the_label_both_ways(self):
        ai_asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            source_lane='gen', ai_generated=True)
        real_asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            source_lane='chantier', ai_generated=False)
        self.assertEqual(
            policy.ai_disclosure_payload(ai_asset), {'ai_generated': True})
        self.assertEqual(
            policy.ai_disclosure_payload(real_asset), {'ai_generated': False})

    def test_no_graph_field_name_is_invented(self):
        # La référence publique AdCreative n'expose aucun champ de divulgation IA
        # documenté : on n'en fabrique pas un. Le jour où il est confirmé, poser
        # GRAPH_AI_DISCLOSURE_FIELD suffit — le fragment l'ajoute tout seul.
        self.assertEqual(policy.GRAPH_AI_DISCLOSURE_FIELD, '')
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            source_lane='gen', ai_generated=True)
        with patch.object(policy, 'GRAPH_AI_DISCLOSURE_FIELD', 'champ_confirme'):
            payload = policy.ai_disclosure_payload(asset)
        self.assertTrue(payload['champ_confirme'])
        self.assertTrue(payload['ai_generated'])
