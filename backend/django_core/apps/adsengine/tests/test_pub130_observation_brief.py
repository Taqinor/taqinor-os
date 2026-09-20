"""PUB130 — Brief hebdomadaire en mode OBSERVATION (avant tout plan de vol).

Prouve, sur fixtures :
  * une société qui OBSERVE (miroirs + instantanés synchronisés, aucune
    expérience ni plan) reçoit des sections d'observation NON VIDES : top/flop
    ads, fatigue, fréquence, junk, candidats en LECTURE SEULE ;
  * le périmètre est dit HONNÊTEMENT : sans instantané sur la fenêtre, le brief
    l'écrit et ne produit AUCUN candidat ;
  * aucune ``EngineAction`` n'est créée depuis les candidats (lecture seule) ;
  * une société AVEC expérience garde un brief INCHANGÉ — golden comparé en
    entier (``data`` sans clé ``observation`` + markdown byte-identique) ;
  * le beat DIT désormais pourquoi il n'a rien produit (compteurs sautés/échecs).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import brief as brief_mod
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, EngineAction, Experiment,
    FlightPlan, InsightSnapshot,
)

NOW = datetime.date(2026, 7, 16)


class ObservationModeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Observe Co', slug='observe-co')
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='Ad set',
            status='PAUSED', campaign=self.campaign)
        self.ad_ct = ContentType.objects.get_for_model(AdMirror)

    def _ad(self, meta_id, *, name='', spend='0.00', results=0,
            impressions=0, frequency=None, day=NOW):
        ad = AdMirror.objects.create(
            company=self.company, meta_id=meta_id, adset=self.adset,
            name=name or meta_id)
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ad_ct, object_id=ad.pk,
            date=day, spend=spend, results=results, impressions=impressions,
            frequency=frequency)
        return ad

    # ── Mode ─────────────────────────────────────────────────────────────────
    def test_observation_mode_is_on_without_experiment_or_plan(self):
        self.assertTrue(brief_mod.observation_mode(self.company))

    def test_an_experiment_turns_observation_mode_off(self):
        Experiment.objects.create(
            company=self.company, name='X',
            status=Experiment.Statut.EN_COURS)
        self.assertFalse(brief_mod.observation_mode(self.company))

    def test_a_flight_plan_turns_observation_mode_off(self):
        FlightPlan.objects.create(
            company=self.company, name='Plan',
            status=FlightPlan.Statut.ACTIF)
        self.assertFalse(brief_mod.observation_mode(self.company))

    # ── Sections d'observation ───────────────────────────────────────────────
    def test_top_and_flop_ads_come_from_synced_snapshots(self):
        self._ad('ad-top', name='Top', spend='60.00', results=5,
                 impressions=4000, frequency='1.10')
        self._ad('ad-flop', name='Flop', spend='40.00', results=0,
                 impressions=3000, frequency='1.20')

        brief = brief_mod.build_brief(self.company, now=NOW)
        obs = brief.data['observation']

        self.assertTrue(obs['donnees_suffisantes'])
        self.assertEqual(obs['ads_observees'], 2)
        self.assertEqual(obs['ads_avec_resultat'], 1)
        self.assertEqual([r['meta_id'] for r in obs['top_ads']], ['ad-top'])
        self.assertEqual([r['meta_id'] for r in obs['flop_ads']], ['ad-flop'])
        self.assertEqual(obs['candidats_duplication'], ['ad-top'])
        self.assertEqual(obs['candidats_pause'], ['ad-flop'])
        self.assertIn('Mode OBSERVATION', obs['perimetre_fr'])
        # Rendu markdown : les sections sont VISIBLES et marquées lecture seule.
        self.assertIn('## Observation (lecture seule)', brief.markdown)
        self.assertIn('Meilleures ads de la semaine', brief.markdown)
        self.assertIn('Ads qui dépensent sans résultat', brief.markdown)
        self.assertIn('LECTURE SEULE', brief.markdown)

    def test_fatigue_section_lists_ads_over_the_threshold(self):
        self._ad('ad-fatigue', name='Fatiguée', spend='30.00', results=2,
                 impressions=9000, frequency='3.10')
        self._ad('ad-saine', name='Saine', spend='30.00', results=3,
                 impressions=2000, frequency='1.10')

        obs = brief_mod.build_brief(
            self.company, now=NOW).data['observation']

        self.assertEqual([r['meta_id'] for r in obs['fatigue_ads']],
                         ['ad-fatigue'])
        self.assertIsNotNone(obs['frequence_moyenne'])
        self.assertEqual(obs['seuil_fatigue'],
                         str(brief_mod.FATIGUE_THRESHOLD_LOW))

    def test_candidates_never_create_an_action(self):
        self._ad('ad-top', spend='60.00', results=5, impressions=4000)
        self._ad('ad-flop', spend='40.00', results=0, impressions=3000)

        brief_mod.build_brief(self.company, now=NOW)

        # Lecture SEULE : aucune rotation, aucune pause proposée depuis les
        # candidats d'observation.
        self.assertFalse(EngineAction.objects.filter(
            company=self.company,
            kind=EngineAction.Kind.ROTATE_CREATIVE).exists())
        self.assertFalse(EngineAction.objects.filter(
            company=self.company,
            payload__target_meta_id='ad-flop').exists())

    def test_without_snapshots_the_brief_says_it_cannot_observe(self):
        AdMirror.objects.create(
            company=self.company, meta_id='ad-muette', adset=self.adset,
            name='Muette')

        obs = brief_mod.build_brief(
            self.company, now=NOW).data['observation']

        self.assertFalse(obs['donnees_suffisantes'])
        self.assertEqual(obs['ads_observees'], 0)
        self.assertEqual(obs['candidats_duplication'], [])
        self.assertEqual(obs['candidats_pause'], [])
        self.assertIn("RIEN à observer", obs['perimetre_fr'])

    def test_no_winner_is_declared_without_a_single_result(self):
        self._ad('ad-1', spend='20.00', results=0, impressions=1000)
        self._ad('ad-2', spend='20.00', results=0, impressions=900)

        obs = brief_mod.build_brief(
            self.company, now=NOW).data['observation']

        self.assertEqual(obs['top_ads'], [])
        self.assertEqual(obs['candidats_duplication'], [])
        self.assertIn('impossible de désigner un gagnant',
                      obs['perimetre_fr'])

    def test_out_of_window_snapshots_are_excluded(self):
        self._ad('ad-vieille', spend='999.00', results=9, impressions=9000,
                 day=NOW - datetime.timedelta(days=30))

        obs = brief_mod.build_brief(
            self.company, now=NOW).data['observation']

        self.assertEqual(obs['ads_observees'], 0)
        self.assertFalse(obs['donnees_suffisantes'])

    def test_sections_are_capped(self):
        for i in range(brief_mod.OBSERVATION_TOP_N + 2):
            self._ad(f'ad-{i}', spend='10.00', results=9 - i,
                     impressions=1000 - i)

        obs = brief_mod.build_brief(
            self.company, now=NOW).data['observation']

        self.assertEqual(len(obs['top_ads']), brief_mod.OBSERVATION_TOP_N)


class ExperimentCompanyGoldenTests(TestCase):
    """Société AVEC expérience : le brief reste BYTE-IDENTIQUE à l'avant-PUB130.

    Le golden est comparé EN ENTIER (markdown complet + absence de la clé
    ``observation``), pas par simple présence de clés."""

    def setUp(self):
        self.company = Company.objects.create(nom='Golden Co', slug='golden-co')
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        # L'expérience éteint le mode observation.
        Experiment.objects.create(
            company=self.company, name='Accroche',
            status=Experiment.Statut.EN_COURS)
        # Un instantané de CAMPAGNE (fréquence volontairement absente : la
        # moyenne d'un DecimalField dépend de la précision du moteur SQL, un
        # golden ne doit pas en dépendre).
        InsightSnapshot.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(AdCampaignMirror),
            object_id=self.campaign.pk, date=NOW, spend='120.00', results=6,
            frequency=None)

    def test_data_carries_no_observation_key(self):
        brief = brief_mod.build_brief(self.company, now=NOW)
        self.assertNotIn('observation', brief.data)
        self.assertEqual(brief.data['propositions'], [])

    def test_markdown_is_unchanged(self):
        brief = brief_mod.build_brief(self.company, now=NOW)
        self.assertEqual(brief.markdown, '\n'.join([
            '# Brief hebdomadaire (2026-07-10 → 2026-07-16)',
            '',
            "## Ce qui s'est passé",
            '- Dépense de la semaine : 120.00 MAD pour 6 résultat(s).',
            '- Coût par lead (semaine) : 20.00 MAD.',
            '- Cadence créative : 0 créatif(s) neuf(s) cette semaine '
            '(repère marché 12-19/semaine) → sous cible.',
            '- Taux de gagnants : aucun ad lancé cette semaine — '
            'indicateur non calculable.',
            '- SLA de synchronisation : à jour (dernière sync 2026-07-16).',
            '',
            '## Suggestions',
            '- Aucune action proposée cette semaine.',
        ]))

    def test_the_observation_renderer_adds_nothing_without_a_section(self):
        self.assertEqual(brief_mod._render_observation(None), [])
        self.assertEqual(brief_mod._render_observation({}), [])
