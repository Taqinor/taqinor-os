"""PUB120 — ``run_weekly`` MATÉRIALISE les décisions de rotation.

Prouve, sur fixtures :
  * la boucle hebdo alimente enfin ``plan_rotation`` en ``p_best`` (dernière
    repondération journalisée) et en série de semaines faibles — sans quoi la
    règle des deux coups ne pouvait structurellement jamais sortir un bras ;
  * une décision portant 1 sortie + 1 entrée écrit 2 PROPOSITIONS liées à
    l'expérience (PAUSE + ROTATE_CREATIVE), le ROTATE_CREATIVE au payload
    COMPLET de PUB119 (``adset_id`` + ``name`` + ``creative``) ;
  * l'item de backlog consommé avance ``EN_FILE`` → ``PROGRAMME`` ;
  * un re-run la MÊME semaine ne duplique RIEN (ni proposition, ni alerte de
    revue, ni avancement de série) ;
  * une revue produit une ALERTE, jamais une action à la place de l'humain ;
  * aucun créatif prêt ⇒ alerte explicite et ZÉRO proposition creuse ;
  * l'interrupteur global fait NO-OP de la boucle (aucune proposition écrite) ;
  * les compteurs ``rotations`` du retour restent la décision brute.
"""
import datetime

from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import flightrunner as fr_mod, rotation
from apps.adsengine.flightrunner import FlightRunner
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, ArmDailyStat,
    CreativeAsset, CreativeBacklogItem, DecisionLog, EngineAction, EngineAlert,
    Experiment, ExperimentArm, FlightPlan, GuardrailConfig, MetaConnection,
)

# Lundi (jour d'évaluation de la rotation — ``rotation.is_rotation_day``).
MONDAY = datetime.date(2026, 7, 13)


def make_company(slug, nom=None):
    return Company.objects.create(nom=nom or slug, slug=slug)


class RotationMaterializationBase(TestCase):
    """Fixtures : une expérience à 2 bras dont l'un est FAIBLE depuis 2 semaines."""

    def setUp(self):
        cache.clear()
        self.company = make_company('pub120', 'PUB120 Co')
        GuardrailConfig.objects.create(company=self.company)
        self.plan = FlightPlan.objects.create(
            company=self.company, name='Plan PUB120',
            status=FlightPlan.Statut.ACTIF)
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-1', name='Solaire',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-1', name='Toit Casa',
            status='PAUSED', campaign=self.campaign)
        self.experiment = Experiment.objects.create(
            company=self.company, name='Accroche facture',
            status=Experiment.Statut.EN_COURS, campaign=self.campaign)

        self.weak_ad = self._ad_with_creative('ad-weak', 'cr-weak')
        self.strong_ad = self._ad_with_creative('ad-strong', 'cr-strong')
        self.weak_arm = self._arm('faible', self.weak_ad.meta_id)
        self.strong_arm = self._arm('fort', self.strong_ad.meta_id)

    def tearDown(self):
        cache.clear()

    # ── Fixtures ─────────────────────────────────────────────────────────────
    def _ad_with_creative(self, meta_id, creative_id):
        ad = AdMirror.objects.create(
            company=self.company, meta_id=meta_id, adset=self.adset,
            name=meta_id)
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id=creative_id,
            link_url='https://taqinor.ma/devis')
        return ad

    def _arm(self, label, ad_id, *, days=14, impressions=400):
        """Bras dont l'exploration est COMPLÈTE (≥7 j et ≥1000 impressions —
        ``rotation.exploration_complete``), sinon aucune sortie n'est éligible."""
        arm = ExperimentArm.objects.create(
            company=self.company, experiment=self.experiment, label=label,
            ad_id=ad_id)
        for offset in range(days):
            ArmDailyStat.objects.create(
                company=self.company, arm=arm,
                date=MONDAY - datetime.timedelta(days=offset),
                impressions=impressions, conversations=1, spend='10.00')
        return arm

    def _log_prob_best(self, mapping):
        """Journalise une repondération bandit (la SOURCE du ``p_best`` lu par la
        rotation)."""
        return DecisionLog.objects.create(
            company=self.company, experiment=self.experiment,
            inputs={}, posteriors={},
            allocations={'prob_best': mapping},
            summary_fr='Repondération de test.')

    def _backlog_item(self, *, image_hash='', **kw):
        """Item EN FILE de la campagne.

        Par DÉFAUT son asset ne porte AUCUN média de compte : le pont PUB123 le
        refuse donc (``media_non_uploade``) et la rotation retombe sur le créatif
        LIVE — c'est l'état d'un item tout juste approuvé, et le cas exigé par
        ``test_entry_without_any_ready_creative_alerts_and_proposes_nothing``.
        ``image_hash`` (avec ``_connect_page``) le rend PONTABLE, donc réellement
        embarquable — et donc consommable — par une proposition."""
        asset = CreativeAsset.objects.create(
            company=self.company,
            asset_type=CreativeAsset.AssetType.STATIC,
            hook_text='Accroche', primary_text='Corps', cta='LEARN_MORE',
            meta_image_hash=image_hash, policy_stamp={'passed': True})
        return CreativeBacklogItem.objects.create(
            company=self.company, asset=asset,
            target_campaign=kw.pop('target_campaign', self.campaign),
            status=CreativeBacklogItem.Statut.EN_FILE, **kw)

    def _connect_page(self, page_id='page-42'):
        """PUB123/PUB-P8/C2 — la Page qui PUBLIE : sans elle le pont refuse TOUT
        asset (``page_absente``), donc aucun item n'est jamais pontable."""
        return MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', page_id=page_id)

    def _runner(self, *, today=MONDAY):
        return FlightRunner(self.plan, clock=lambda: today)

    def _make_weak_two_weeks(self):
        """Amène le bras faible à 2 semaines FAIBLES consécutives : la série
        avance d'un cran par semaine ÉVALUÉE (jamais deux fois la même semaine),
        il faut donc bien DEUX semaines.

        On évalue la semaine précédente par ``_rotation_snapshots`` — le seul
        geste dont la série a besoin — et NON par un ``run_weekly`` complet : une
        boucle entière MATÉRIALISE aussi ses propres propositions (2 bras vivants
        sur ``ADS_PER_ADSET``=3 laissent un slot libre, donc une ENTRÉE est
        légitimement proposée dès cette semaine-là, et l'item de backlog est
        consommé une semaine trop tôt). Cette fixture ne doit préparer QUE la
        série ; la semaine testée reste celle du test."""
        self._log_prob_best({'faible': 0.05, 'fort': 0.95})
        previous = MONDAY - datetime.timedelta(days=7)
        self._runner(today=previous)._rotation_snapshots(
            self.experiment, today=previous)


class SnapshotFeedTests(RotationMaterializationBase):
    def test_p_best_comes_from_the_last_logged_reweighting(self):
        self._log_prob_best({'faible': 0.05, 'fort': 0.95})
        snaps = {s.arm_id: s for s in self._runner()._rotation_snapshots(
            self.experiment, today=MONDAY)}
        self.assertAlmostEqual(snaps[self.weak_arm.pk].p_best, 0.05)
        self.assertAlmostEqual(snaps[self.strong_arm.pk].p_best, 0.95)

    def test_no_logged_decision_gives_zero_never_an_invented_belief(self):
        snaps = self._runner()._rotation_snapshots(
            self.experiment, today=MONDAY)
        self.assertTrue(all(s.p_best == 0.0 for s in snaps))
        self.assertTrue(all(s.weak_streak == 1 for s in snaps))

    def test_weak_streak_advances_once_per_week_only(self):
        self._log_prob_best({'faible': 0.05, 'fort': 0.95})
        runner = self._runner()
        first = runner._rotation_snapshots(self.experiment, today=MONDAY)
        again = runner._rotation_snapshots(self.experiment, today=MONDAY)
        by_id = {s.arm_id: s for s in first}
        by_id_again = {s.arm_id: s for s in again}
        self.assertEqual(by_id[self.weak_arm.pk].weak_streak, 1)
        self.assertEqual(by_id_again[self.weak_arm.pk].weak_streak, 1)
        # Semaine suivante → le cran avance.
        next_week = runner._rotation_snapshots(
            self.experiment, today=MONDAY + datetime.timedelta(days=7))
        self.assertEqual(
            {s.arm_id: s for s in next_week}[self.weak_arm.pk].weak_streak, 2)

    def test_a_recovered_arm_resets_its_streak(self):
        self._log_prob_best({'faible': 0.05, 'fort': 0.95})
        runner = self._runner()
        runner._rotation_snapshots(self.experiment, today=MONDAY)
        self._log_prob_best({'faible': 0.60, 'fort': 0.40})
        snaps = runner._rotation_snapshots(
            self.experiment, today=MONDAY + datetime.timedelta(days=7))
        self.assertEqual(
            {s.arm_id: s for s in snaps}[self.weak_arm.pk].weak_streak, 0)


class ExitAndEntryTests(RotationMaterializationBase):
    def test_one_exit_and_one_entry_write_two_linked_proposals(self):
        self._backlog_item()
        self._make_weak_two_weeks()

        report = self._runner().run_weekly()

        # Compteurs de la DÉCISION (retour inchangé).
        self.assertEqual(
            report['rotations'],
            [{'experiment_id': self.experiment.pk, 'exits': 1, 'reviews': 0,
              'entries': 1}])
        # Deux propositions matérialisées.
        self.assertEqual(report['rotation_proposals']['pauses'], 1)
        self.assertEqual(report['rotation_proposals']['rotations'], 1)

        pause = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.PAUSE)
        self.assertEqual(pause.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(pause.payload['target_meta_id'], self.weak_ad.meta_id)
        self.assertEqual(pause.payload['target_type'], 'ad')
        self.assertEqual(pause.payload['target_object_id'], self.weak_ad.pk)
        self.assertEqual(pause.payload['experiment_id'], self.experiment.pk)
        self.assertEqual(pause.payload['rotation_arm_id'], self.weak_arm.pk)
        self.assertIn('sort du test', pause.reason_fr)

        rotate = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.ROTATE_CREATIVE)
        self.assertEqual(rotate.status, EngineAction.Statut.PROPOSEE)
        # PUB119 — les trois pièces sont là (jamais une action creuse).
        self.assertEqual(rotate.payload['adset_id'], self.adset.meta_id)
        self.assertTrue(rotate.payload['name'])
        self.assertTrue(rotate.payload['creative'])
        self.assertEqual(rotate.payload['experiment_id'], self.experiment.pk)
        self.assertTrue(rotate.payload['rotation_launch_name'])

    def test_the_consumed_backlog_item_leaves_the_free_queue(self):
        # Pour qu'un item soit CONSOMMÉ il faut d'abord qu'il soit EMBARQUÉ : le
        # pont PUB123 exige un média déjà uploadé au COMPTE et la Page qui publie.
        # Sans les deux, la rotation retombe sur le créatif LIVE et ne consomme
        # rien — ce qui est correct, mais n'est pas ce que ce test prouve.
        self._connect_page()
        item = self._backlog_item(image_hash='hash-abc')
        self._make_weak_two_weeks()

        self._runner().run_weekly()

        item.refresh_from_db()
        self.assertEqual(item.status, CreativeBacklogItem.Statut.PROGRAMME)
        rotate = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.ROTATE_CREATIVE)
        self.assertEqual(rotate.payload['backlog_item_id'], item.pk)
        self.assertEqual(rotate.payload['rotation_backlog_item_id'], item.pk)

    def test_rerun_the_same_week_duplicates_nothing(self):
        self._backlog_item()
        self._make_weak_two_weeks()

        self._runner().run_weekly()
        first = EngineAction.objects.filter(company=self.company).count()
        second_report = self._runner().run_weekly()
        after = EngineAction.objects.filter(company=self.company).count()

        self.assertEqual(after, first)
        self.assertEqual(second_report['rotation_proposals']['pauses'], 0)
        self.assertEqual(second_report['rotation_proposals']['rotations'], 0)

    def test_exit_without_a_mirrored_ad_alerts_instead_of_proposing(self):
        ExperimentArm.objects.filter(pk=self.weak_arm.pk).update(ad_id='')
        self._make_weak_two_weeks()

        report = self._runner().run_weekly()

        self.assertEqual(report['rotation_proposals']['pauses'], 0)
        self.assertGreaterEqual(report['rotation_proposals']['alerts'], 1)
        self.assertFalse(EngineAction.objects.filter(
            company=self.company, kind=EngineAction.Kind.PAUSE).exists())
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company,
            detail__template_key=fr_mod.ROTATION_TEMPLATE_EXIT).exists())

    def test_entry_without_any_ready_creative_alerts_and_proposes_nothing(self):
        # Aucun créatif LIVE sur l'ad set, aucun item pontable : PUB119 refuse.
        AdCreativeMirror.objects.filter(company=self.company).delete()
        self._backlog_item()
        self._make_weak_two_weeks()

        report = self._runner().run_weekly()

        self.assertEqual(report['rotation_proposals']['rotations'], 0)
        self.assertFalse(EngineAction.objects.filter(
            company=self.company,
            kind=EngineAction.Kind.ROTATE_CREATIVE).exists())
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company,
            detail__template_key=fr_mod.ROTATION_TEMPLATE_ENTRY).exists())

    def test_no_backlog_means_no_entry_at_all(self):
        self._make_weak_two_weeks()
        report = self._runner().run_weekly()
        self.assertEqual(report['rotations'][0]['entries'], 0)
        self.assertEqual(report['rotation_proposals']['rotations'], 0)


class ReviewTests(RotationMaterializationBase):
    def _age_out(self, arm):
        """Vieillit un bras au-delà de la durée de vie max → REVIEW (jamais une
        sortie automatique : ``rotation.classify_arm``)."""
        old = MONDAY - datetime.timedelta(
            days=rotation.MAX_LIFESPAN_WEEKS * 7 + 3)
        ArmDailyStat.objects.create(
            company=self.company, arm=arm, date=old,
            impressions=2000, conversations=1, spend='10.00')

    def test_a_review_emits_an_alert_and_no_action(self):
        self._age_out(self.strong_arm)
        self._log_prob_best({'faible': 0.40, 'fort': 0.60})

        report = self._runner().run_weekly()

        self.assertGreaterEqual(report['rotations'][0]['reviews'], 1)
        self.assertGreaterEqual(report['rotation_proposals']['reviews'], 1)
        self.assertFalse(EngineAction.objects.filter(
            company=self.company, kind=EngineAction.Kind.PAUSE).exists())
        alert = EngineAlert.objects.filter(
            company=self.company,
            detail__template_key=fr_mod.ROTATION_TEMPLATE_REVIEW).first()
        self.assertIsNotNone(alert)
        self.assertIn('REVUE humaine', alert.message)

    def test_review_alert_is_not_re_emitted_the_same_week(self):
        self._age_out(self.strong_arm)
        self._log_prob_best({'faible': 0.40, 'fort': 0.60})

        self._runner().run_weekly()
        first = EngineAlert.objects.filter(
            company=self.company,
            detail__template_key=fr_mod.ROTATION_TEMPLATE_REVIEW).count()
        self._runner().run_weekly()
        after = EngineAlert.objects.filter(
            company=self.company,
            detail__template_key=fr_mod.ROTATION_TEMPLATE_REVIEW).count()

        self.assertEqual(after, first)


class KillSwitchNoopTests(RotationMaterializationBase):
    def test_kill_switch_makes_the_whole_loop_a_noop(self):
        self._backlog_item()
        self._make_weak_two_weeks()
        runner = self._runner()
        runner.engage_kill_switch()
        before = EngineAction.objects.filter(
            company=self.company,
            status=EngineAction.Statut.PROPOSEE).count()

        report = runner.run_weekly()

        self.assertEqual(report, {'skipped': 'kill_switch'})
        after = EngineAction.objects.filter(
            company=self.company,
            status=EngineAction.Statut.PROPOSEE).count()
        self.assertEqual(after, before)
