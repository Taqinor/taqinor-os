"""PUB121 — Le ``FlightRunner`` remplit les SLOTS créatifs au lancement.

Prouve, sur fixtures :
  * un ad set à froid consulte l'arbitre ``dco`` : aucun signal ⇒ bootstrap DCO
    (UN seul ad à spec dynamique — exclusion mutuelle DCO ↔ rotation) ;
  * un pool gagnant vide (compte neuf) ne laisse JAMAIS l'ad set muet : les
    slots sont remplis depuis la file de backlog (pontée par PUB123) ;
  * sans item pontable, le créatif du GAGNANT est réutilisé (chemin duplicate) ;
  * aucun candidat ⇒ ALERTE explicite et ZÉRO proposition ;
  * chaque ad est une PROPOSITION (jamais une création directe) et aucun
    ``status`` ne voyage dans son payload (naissance PAUSED intacte) ;
  * l'item de backlog consommé quitte la file libre (le slot suivant prend le
    suivant).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import dco, flightrunner as fr_mod, rotation, services
from apps.adsengine.flightrunner import FlightRunner
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, CreativeAsset,
    CreativeBacklogItem, EngineAction, EngineAlert, FlightPlan, InsightSnapshot,
    MetaConnection,
)

TODAY = datetime.date(2026, 7, 13)


def make_company(slug, nom=None):
    return Company.objects.create(nom=nom or slug, slug=slug)


class LaunchCreativesBase(TestCase):
    def setUp(self):
        cache.clear()
        self.company = make_company('pub121', 'PUB121 Co')
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-1', name='Solaire',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-new', name='Toit Casa',
            status='PAUSED', campaign=self.campaign, created_via_engine=True)
        self.connection = MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', page_id='page-42')

    def tearDown(self):
        cache.clear()

    # ── Fixtures ─────────────────────────────────────────────────────────────
    def _winner_ad(self, *, results=9, creative_id='cr-win',
                   link='https://taqinor.ma/devis'):
        """Une ad GAGNANTE mirorée (résultats RÉELS sur la fenêtre) : la source
        du pool DCO ET du créatif de repli."""
        other_adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-old', name='Ancien',
            status='PAUSED', campaign=self.campaign)
        ad = AdMirror.objects.create(
            company=self.company, meta_id='ad-win', adset=other_adset,
            name='20260101_STATIC_FACTURE_ROI')
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id=creative_id,
            link_url=link, title='Titre gagnant', body='Texte gagnant',
            image_hash='hash-win', cta_type='LEARN_MORE')
        InsightSnapshot.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(AdMirror),
            object_id=ad.pk, date=TODAY, spend='100.00', results=results,
            impressions=5000)
        return ad

    def _backlog_item(self, *, hook='Accroche', target_campaign=None,
                      image_hash='hash-abc'):
        asset = CreativeAsset.objects.create(
            company=self.company,
            asset_type=CreativeAsset.AssetType.STATIC,
            hook_text=hook, primary_text='Vos factures baissent.',
            cta='LEARN_MORE', hook_tag='FACTURE', angle_tag='ROI',
            format_tag='STATIC', meta_image_hash=image_hash,
            policy_stamp={'passed': True})
        return CreativeBacklogItem.objects.create(
            company=self.company, asset=asset,
            target_campaign=target_campaign,
            status=CreativeBacklogItem.Statut.EN_FILE)

    def _signal_on_adset(self):
        """Donne un SIGNAL à l'ad set (dépense réelle) → plus de bootstrap DCO,
        la rotation multi-ads prend la main (``dco.adset_has_signal``)."""
        InsightSnapshot.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(AdSetMirror),
            object_id=self.adset.pk, date=TODAY, spend='50.00', results=2,
            impressions=1000)


class ColdStartArbitrationTests(LaunchCreativesBase):
    def test_cold_start_with_a_winning_pool_bootstraps_dco_only(self):
        self._winner_ad()

        # ``now=TODAY`` : les chiffres GAGNANTS de la fixture sont datés de TODAY
        # et la moisson du pool (``dco.HARVEST_WINDOW_DAYS`` = 30 j) se lit depuis
        # ce jour-là. Sans horloge injectée, la fenêtre part de l'heure murale et
        # ne voit AUCUN gagnant — l'ad set n'aurait donc rien à recombiner.
        result = services.propose_adset_launch_ads(
            self.company, adset=self.adset, now=TODAY)

        self.assertEqual(result['mode'], dco.MODE_DCO_BOOTSTRAP)
        # Exclusion mutuelle : UN seul ad pour un ad set DCO.
        self.assertEqual(len(result['actions']), 1)
        action = result['actions'][0]
        self.assertEqual(action.kind, EngineAction.Kind.CREATE_AD)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertTrue(action.payload['asset_feed_spec'])
        self.assertEqual(action.payload['adset_id'], self.adset.meta_id)
        self.assertNotIn('status', action.payload)

    def test_cold_start_without_a_pool_falls_back_to_the_backlog(self):
        # Compte neuf : aucun gagnant à recombiner. L'ad set ne reste PAS muet.
        item = self._backlog_item()

        result = services.propose_adset_launch_ads(
            self.company, adset=self.adset)

        self.assertEqual(result['mode'], dco.MODE_MULTI_AD_ROTATION)
        self.assertTrue(result['fallback_fr'])
        self.assertEqual(len(result['actions']), 1)
        payload = result['actions'][0].payload
        self.assertEqual(payload['creative_source'],
                         services.LAUNCH_SOURCE_BACKLOG)
        self.assertEqual(payload['backlog_item_id'], item.pk)
        self.assertEqual(
            payload['creative']['object_story_spec']['page_id'], 'page-42')

    def test_a_signal_switches_to_multi_ad_rotation(self):
        self._signal_on_adset()
        self._backlog_item()

        result = services.propose_adset_launch_ads(
            self.company, adset=self.adset)

        self.assertEqual(result['mode'], dco.MODE_MULTI_AD_ROTATION)
        self.assertEqual(result['fallback_fr'], '')


class SlotFillingTests(LaunchCreativesBase):
    def test_slots_are_filled_up_to_the_adset_capacity(self):
        self._signal_on_adset()
        for i in range(rotation.ADS_PER_ADSET + 2):
            self._backlog_item(hook=f'Accroche {i}',
                               image_hash=f'hash-{i}')

        result = services.propose_adset_launch_ads(
            self.company, adset=self.adset)

        self.assertEqual(len(result['actions']), rotation.ADS_PER_ADSET)
        self.assertEqual(
            EngineAction.objects.filter(
                company=self.company,
                kind=EngineAction.Kind.CREATE_AD).count(),
            rotation.ADS_PER_ADSET)

    def test_consumed_backlog_items_leave_the_free_queue(self):
        self._signal_on_adset()
        items = [self._backlog_item(hook=f'A{i}', image_hash=f'h-{i}')
                 for i in range(2)]

        services.propose_adset_launch_ads(self.company, adset=self.adset)

        for item in items:
            item.refresh_from_db()
            self.assertEqual(item.status,
                             CreativeBacklogItem.Statut.PROGRAMME)

    def test_a_campaign_targeted_item_is_never_diverted(self):
        self._signal_on_adset()
        other_campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-2', name='Autre',
            status='PAUSED')
        foreign = self._backlog_item(target_campaign=other_campaign)
        self._winner_ad()

        # ``now=TODAY`` : le gagnant de repli n'est dans la fenêtre de moisson que
        # depuis le jour où la fixture le date.
        result = services.propose_adset_launch_ads(
            self.company, adset=self.adset, now=TODAY)

        foreign.refresh_from_db()
        self.assertEqual(foreign.status, CreativeBacklogItem.Statut.EN_FILE)
        self.assertEqual(result['sources'], [services.LAUNCH_SOURCE_WINNER])

    def test_a_future_dated_item_is_never_proposed(self):
        # PUB-P8/C7 — la file COMPLÈTE (``queue_for_campaign``) sert l'écran de
        # planification ; un PROPOSEUR, lui, ne prend que les items publiables
        # aujourd'hui. Un item daté dans 30 jours partait en proposition.
        self._signal_on_adset()
        later = self._backlog_item(hook='Plus tard', image_hash='h-late')
        CreativeBacklogItem.objects.filter(pk=later.pk).update(
            earliest_date=TODAY + datetime.timedelta(days=30))
        self._winner_ad()

        # Une seule horloge pour la date-au-plus-tôt ET pour la moisson du pool.
        result = services.propose_adset_launch_ads(
            self.company, adset=self.adset, now=TODAY)

        later.refresh_from_db()
        self.assertEqual(later.status, CreativeBacklogItem.Statut.EN_FILE)
        self.assertEqual(result['sources'], [services.LAUNCH_SOURCE_WINNER])

    def test_an_unbridgeable_item_is_skipped_never_proposed(self):
        self._signal_on_adset()
        # Asset SANS média uploadé au compte : le pont PUB123 le refuse.
        asset = CreativeAsset.objects.create(
            company=self.company,
            asset_type=CreativeAsset.AssetType.STATIC,
            hook_text='Sans média', primary_text='Corps',
            policy_stamp={'passed': True})
        item = CreativeBacklogItem.objects.create(
            company=self.company, asset=asset,
            status=CreativeBacklogItem.Statut.EN_FILE)

        with self.assertRaises(services.AdsetWithoutCreative):
            services.propose_adset_launch_ads(self.company, adset=self.adset)

        item.refresh_from_db()
        self.assertEqual(item.status, CreativeBacklogItem.Statut.EN_FILE)
        self.assertFalse(EngineAction.objects.filter(
            company=self.company).exists())


class WinnerFallbackTests(LaunchCreativesBase):
    def test_the_winner_creative_is_reused_when_the_backlog_is_empty(self):
        self._signal_on_adset()
        self._winner_ad(creative_id='cr-win')

        # ``now=TODAY`` : sans elle, la fenêtre de moisson (30 j depuis l'heure
        # murale) ne voit pas le gagnant daté par la fixture.
        result = services.propose_adset_launch_ads(
            self.company, adset=self.adset, now=TODAY)

        self.assertEqual(len(result['actions']), 1)
        payload = result['actions'][0].payload
        self.assertEqual(payload['creative'], {'creative_id': 'cr-win'})
        self.assertEqual(payload['creative_source'],
                         services.LAUNCH_SOURCE_WINNER)
        self.assertEqual(payload['source_ad_id'], 'ad-win')
        self.assertTrue(payload['name'])
        self.assertNotIn('status', payload)

    def test_no_candidate_at_all_refuses_instead_of_a_silent_shell(self):
        self._signal_on_adset()

        with self.assertRaises(services.AdsetWithoutCreative) as ctx:
            services.propose_adset_launch_ads(self.company, adset=self.adset)

        self.assertIn('Aucun créatif prêt', str(ctx.exception))
        self.assertFalse(EngineAction.objects.filter(
            company=self.company).exists())

    def test_an_adset_without_meta_id_is_refused(self):
        self.adset.meta_id = ''
        with self.assertRaises(services.AdsetWithoutCreative):
            services.propose_adset_launch_ads(self.company, adset=self.adset)


class RunnerWiringTests(LaunchCreativesBase):
    def _runner(self):
        plan = FlightPlan.objects.create(
            company=self.company, name='Plan PUB121',
            status=FlightPlan.Statut.ACTIF)
        return FlightRunner(plan, clock=lambda: TODAY)

    def test_launch_proposes_ads_per_adset(self):
        self._signal_on_adset()
        self._winner_ad()

        summary = self._runner()._propose_phase_creatives(
            None, [self.adset.meta_id])

        self.assertEqual(summary['proposed'], 1)
        self.assertEqual(summary['alerts'], 0)
        self.assertEqual(len(summary['by_adset'][self.adset.meta_id]), 1)

    def test_an_adset_without_candidate_raises_an_explicit_alert(self):
        self._signal_on_adset()

        summary = self._runner()._propose_phase_creatives(
            None, [self.adset.meta_id])

        self.assertEqual(summary['proposed'], 0)
        self.assertEqual(summary['alerts'], 1)
        alert = EngineAlert.objects.filter(
            company=self.company,
            detail__template_key=fr_mod.LAUNCH_TEMPLATE_CREATIVE).first()
        self.assertIsNotNone(alert)
        self.assertIn('Aucun créatif prêt', alert.message)
        self.assertFalse(EngineAction.objects.filter(
            company=self.company).exists())

    def test_unknown_adset_ids_are_ignored_without_crashing(self):
        summary = self._runner()._propose_phase_creatives(
            None, ['', 'as-inconnu'])
        self.assertEqual(summary, {'proposed': 0, 'alerts': 0, 'by_adset': {}})
