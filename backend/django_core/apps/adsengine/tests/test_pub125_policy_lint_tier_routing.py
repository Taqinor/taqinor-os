"""PUB125 — ``policy_lint`` + ``tier_router`` insérés dans le chemin RÉEL.

Le chemin de production sautait les deux : le pré-linter policy (AGEN5) n'avait
AUCUN appelant et le routeur de paliers (AGEN6) n'était consommé que par le
simulateur. Prouve, sur fixtures :

  * une variante à SUPERLATIF interdit est linted FAIL, son verdict est persisté
    (asset + audit du lot) et elle n'entre JAMAIS au backlog — ni comme membre
    du lot (``visual_ids``), ni comme item de file ;
  * une variante propre non graduée est routée Palier B et flaggée
    « revue humaine » ;
  * un gabarit GRADUÉ (tout vert) route en Palier A → item de backlog DIRECT ;
  * un lot entièrement vert alimente ``record_clean_week`` (la graduation B→A
    devient réelle), au plus une fois par semaine ISO ;
  * le chemin SIMULATEUR reste byte-identique (comparaison réelle du rapport).
"""
import datetime
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import simulator, tasks, tier_router
from apps.adsengine.models import (
    CreativeAsset, CreativeBacklogItem, CreativeGenerationBatch, FactEntry,
    FactTable,
)

# Environnement SANS aucune clé de génération : le NO-OP key-gated ne doit pas
# dépendre de la machine qui lance les tests.
NO_ENV = {'ADSENGINE_GEN_API_KEY': '', 'GROQ_API_KEY': ''}

CLEAN = {
    'hook_text': 'Passez au solaire',
    'primary_text': 'Vos factures baissent chaque mois.',
    'cta': 'LEARN_MORE',
    'hook_tag': 'FACTURE', 'angle_tag': 'ROI', 'format_tag': 'STATIC',
}
SUPERLATIF = {
    'hook_text': 'Le meilleur installateur',
    'primary_text': 'Nous sommes le meilleur choix du Maroc.',
    'cta': 'LEARN_MORE',
    'hook_tag': 'MARQUE', 'angle_tag': 'AUTORITE', 'format_tag': 'STATIC',
}


def make_company(slug, nom=None):
    return Company.objects.create(nom=nom or slug, slug=slug)


def grounded_scorer(text, references):
    """Scoreur d'ancrage INJECTÉ (le vrai est key-gated : sans clé, tout reste
    Palier B par prudence — c'est le contrat d'``groundedness``)."""
    return 0.95


class PolicyRoutingBase(TestCase):
    def setUp(self):
        cache.clear()
        self.company = make_company('pub125', 'PUB125 Co')
        table = FactTable.create_draft(self.company)
        FactEntry.objects.create(
            table=table, company=self.company, cle='economie_annuelle',
            valeur='12 000', unite='MAD', source='étude interne',
            verifie_le=datetime.date(2026, 1, 1))
        table.publish()

    def tearDown(self):
        cache.clear()

    def _generator(self, variants):
        return lambda context: [dict(v) for v in variants]

    def _run(self, variants, *, scorer=None, seed_brief='accroche facture'):
        return tasks._run_grounded_generation(
            self.company, seed_brief,
            generator=self._generator(variants),
            groundedness_scorer=scorer)

    def _template_id(self, variant):
        return '/'.join([variant['format_tag'], variant['hook_tag'],
                         variant['angle_tag']])


class PolicyLintInsertionTests(PolicyRoutingBase):
    def test_a_forbidden_superlative_never_reaches_the_backlog(self):
        report = self._run([CLEAN, SUPERLATIF])

        self.assertTrue(report['enabled'])
        self.assertEqual(report['assets'], 2)
        self.assertEqual(report['policy_blocked'], 1)

        batch = CreativeGenerationBatch.objects.get(pk=report['batch_id'])
        routing = batch.claim_verdicts['policy_routing']
        blocked = [r for r in routing if r.get('blocked')]
        self.assertEqual(len(blocked), 1)
        self.assertFalse(blocked[0]['policy_lint']['ok'])
        self.assertIn(
            'superlatif',
            blocked[0]['policy_lint']['blocking'][0]['rule_id'])

        from apps.adsengine.models import CreativeAsset
        asset = CreativeAsset.objects.get(pk=blocked[0]['asset_id'])
        # Verdict PERSISTÉ sur l'asset + garde ENG15 (jamais référençable).
        self.assertFalse(asset.policy_stamp['policy_lint']['ok'])
        self.assertIs(asset.policy_stamp['passed'], False)
        self.assertTrue(asset.policy_stamp['policy_lint_block'])
        self.assertFalse(asset.is_policy_passed)
        # Ni membre du lot, ni item de file : le backlog lui est fermé.
        self.assertNotIn(asset.pk, batch.visual_ids)
        self.assertFalse(CreativeBacklogItem.objects.filter(
            company=self.company, asset=asset).exists())

    def test_a_clean_variant_is_tier_b_and_flagged_for_review(self):
        report = self._run([CLEAN])

        self.assertEqual(report['tier_b'], 1)
        self.assertEqual(report['tier_a'], 0)
        batch = CreativeGenerationBatch.objects.get(pk=report['batch_id'])
        record = batch.claim_verdicts['policy_routing'][0]
        self.assertEqual(record['tier'], tier_router.TIER_B)

        from apps.adsengine.models import CreativeAsset
        asset = CreativeAsset.objects.get(pk=record['asset_id'])
        self.assertTrue(asset.policy_stamp['revue_humaine'])
        self.assertEqual(asset.policy_stamp['tier'], tier_router.TIER_B)
        self.assertIn(asset.pk, batch.visual_ids)
        # Palier B = revue humaine par LOT : aucun item de file avant elle.
        self.assertFalse(CreativeBacklogItem.objects.filter(
            company=self.company).exists())

    def test_without_a_scorer_everything_stays_tier_b_by_prudence(self):
        # Contrat key-gated d'``groundedness`` : aucun scoreur ⇒ jamais A.
        report = self._run([CLEAN], scorer=None)
        self.assertEqual(report['tier_a'], 0)
        self.assertEqual(report['tier_b'], 1)


class TierRoutingTests(PolicyRoutingBase):
    def test_a_graduated_template_routes_to_tier_a_and_files_directly(self):
        template_id = self._template_id(CLEAN)
        tier_router.set_template_graduated(self.company, template_id, True)

        report = self._run([CLEAN], scorer=grounded_scorer)

        self.assertEqual(report['tier_a'], 1)
        self.assertEqual(report['tier_b'], 0)
        batch = CreativeGenerationBatch.objects.get(pk=report['batch_id'])
        record = batch.claim_verdicts['policy_routing'][0]
        self.assertEqual(record['tier'], tier_router.TIER_A)
        self.assertTrue(record['all_green'])
        self.assertTrue(record['graduated'])
        # File DIRECTE : l'item existe sans attendre l'approbation du lot.
        item = CreativeBacklogItem.objects.get(company=self.company)
        self.assertEqual(item.asset_id, record['asset_id'])
        self.assertEqual(item.batch_id, batch.pk)
        self.assertEqual(item.status, CreativeBacklogItem.Statut.EN_FILE)
        self.assertEqual(batch.visual_ids, [])

        from apps.adsengine.models import CreativeAsset
        asset = CreativeAsset.objects.get(pk=record['asset_id'])
        self.assertFalse(asset.policy_stamp['revue_humaine'])
        # FRONTIÈRE : le routage décide la FILE, jamais la check-list policy
        # (jugement humain, avec ses gardes consentement / divulgation IA).
        self.assertNotIn('passed', asset.policy_stamp)

    def test_a_clean_lot_records_one_clean_week_per_template(self):
        template_id = self._template_id(CLEAN)
        self.assertEqual(tier_router.clean_weeks(self.company, template_id), 0)

        self._run([CLEAN], scorer=grounded_scorer)

        self.assertEqual(tier_router.clean_weeks(self.company, template_id), 1)

    def test_several_lots_the_same_week_count_as_one_clean_week(self):
        template_id = self._template_id(CLEAN)
        for _ in range(3):
            self._run([CLEAN], scorer=grounded_scorer)
        self.assertEqual(tier_router.clean_weeks(self.company, template_id), 1)
        self.assertFalse(
            tier_router.template_graduated(self.company, template_id))

    def test_a_blocked_variant_makes_the_lot_unclean(self):
        template_id = self._template_id(CLEAN)
        self._run([CLEAN, SUPERLATIF], scorer=grounded_scorer)
        self.assertEqual(tier_router.clean_weeks(self.company, template_id), 0)

    @mock.patch.dict('os.environ', NO_ENV)
    def test_no_key_and_no_generator_stays_a_clean_noop(self):
        report = tasks._run_grounded_generation(self.company, 'rien')
        self.assertFalse(report['enabled'])
        self.assertIsNone(report['batch_id'])
        self.assertFalse(CreativeGenerationBatch.objects.exists())
        self.assertFalse(CreativeBacklogItem.objects.exists())


class TemplateIdentityTests(TestCase):
    def test_template_id_uses_declared_tags_then_asset_type(self):
        tagged = CreativeAsset(
            format_tag='STATIC', hook_tag='FACTURE', angle_tag='ROI',
            asset_type=CreativeAsset.AssetType.STATIC)
        self.assertEqual(tasks._generation_template_id(tagged),
                         'STATIC/FACTURE/ROI')
        untagged = CreativeAsset(asset_type=CreativeAsset.AssetType.STATIC)
        self.assertEqual(
            tasks._generation_template_id(untagged),
            f'asset_type:{CreativeAsset.AssetType.STATIC}')


class SimulatorUnchangedTests(TestCase):
    """Le chemin SIMULATEUR n'est pas touché : son rapport reste byte-identique
    (comparaison RÉELLE du dict renvoyé, pas une simple présence de clés)."""

    def setUp(self):
        cache.clear()
        self.company = make_company('pub125-sim', 'PUB125 Sim')

    def tearDown(self):
        cache.clear()

    def test_graduation_scenario_report_is_unchanged(self):
        report = simulator.simulate_generation(
            self.company, scenario='gabarit_gradue', seed=42)
        self.assertEqual(report, {
            'scenario': 'gabarit_gradue',
            'seed': 42,
            'expected_verdict': 'graduated',
            'verdict': 'graduated',
            'clean_weeks': [1, 2, 3],
            'threshold': tier_router.CLEAN_WEEKS_FOR_GRADUATION,
            'tier_before': 'B',
            'tier_after': 'A',
            'summary_fr': (
                f"Gabarit propre {tier_router.CLEAN_WEEKS_FOR_GRADUATION} "
                f"semaines : palier B→A (gradué → backlog direct)."),
        })

    def test_the_scenario_never_touches_the_real_generation_pipeline(self):
        # Le scénario est règle-à-règle (toggles cache) : il ne crée NI lot, NI
        # asset, NI item de file — le lint/routage inséré dans la tâche de
        # production ne peut donc pas déteindre sur lui.
        simulator.simulate_generation(
            self.company, scenario='gabarit_gradue', seed=42)
        self.assertFalse(CreativeGenerationBatch.objects.exists())
        self.assertFalse(CreativeBacklogItem.objects.exists())
        self.assertFalse(CreativeAsset.objects.exists())
