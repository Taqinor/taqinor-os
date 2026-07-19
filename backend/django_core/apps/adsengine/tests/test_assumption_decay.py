"""ASG2 — Tests dorés de l'oubli hebdomadaire (dd-assumption-engine §3.2).

Reproduit §3.2 EXACTEMENT sous seed déterministe :
  * ``ρ = 0.5^(1/H)`` par classe ;
  * un pas d'oubli ``(α,β) ← (ρα+(1−ρ)α₀, ρβ+(1−ρ)β₀)`` ;
  * LA demi-vie : ``(α−α₀)`` divisée par 2 EXACTEMENT toutes les ``H`` semaines
    (``ρ^H = 0.5``) ;
  * le REGONFLEMENT de variance (l'incertitude remonte vers le prior) ;
  * la saisonnalité JAMAIS oubliée par l'horloge hebdo ;
  * l'éligibilité « une semaine sans test ».
"""
import datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company
from apps.adsengine import assumption_decay as decay
from apps.adsengine.models import AssumptionNode


class DecayMathTests(SimpleTestCase):
    """Cœur mathématique pur — golden exact (§3.2)."""

    def test_rho_per_class(self):
        # ρ = 0.5^(1/H) par classe (8/13/26).
        self.assertAlmostEqual(decay.rho(8), 0.5 ** (1.0 / 8), places=15)
        self.assertAlmostEqual(decay.rho(13), 0.5 ** (1.0 / 13), places=15)
        self.assertAlmostEqual(decay.rho(26), 0.5 ** (1.0 / 26), places=15)

    def test_rho_requires_positive_half_life(self):
        with self.assertRaises(ValueError):
            decay.rho(0)

    def test_single_step_exact(self):
        # Beta(50,10) oublié vers Beta(1,1), H=8 (créatif).
        r = 0.5 ** (1.0 / 8)
        a, b = decay.decay_step(50.0, 10.0, 1.0, 1.0, 8)
        self.assertAlmostEqual(a, r * 50.0 + (1 - r) * 1.0, places=12)
        self.assertAlmostEqual(b, r * 10.0 + (1 - r) * 1.0, places=12)

    def test_half_life_halves_distance_to_prior(self):
        # LA demi-vie : après H=8 semaines, (α−α₀) est divisé par 2 EXACTEMENT.
        a0, b0 = 1.0, 1.0
        a, b = decay.decay_multi(50.0, 10.0, a0, b0, 8, 8)
        self.assertAlmostEqual(a - a0, 0.5 * (50.0 - a0), places=9)
        self.assertAlmostEqual(b - b0, 0.5 * (10.0 - b0), places=9)

    def test_two_half_lives_quarters_distance(self):
        a0 = 1.0
        a, _ = decay.decay_multi(50.0, 10.0, a0, 1.0, 8, 16)
        self.assertAlmostEqual(a - a0, 0.25 * (50.0 - a0), places=9)

    def test_multi_matches_closed_form(self):
        # decay_multi ≡ forme fermée ρ^weeks·(x−x₀)+x₀ par coordonnée.
        r = decay.rho(13)
        a, b = decay.decay_multi(30.0, 5.0, 2.0, 2.0, 13, 5)
        self.assertAlmostEqual(a, r ** 5 * (30.0 - 2.0) + 2.0, places=9)
        self.assertAlmostEqual(b, r ** 5 * (5.0 - 2.0) + 2.0, places=9)

    def test_variance_reinflates_toward_prior(self):
        # §3.2 : l'oubli REGONFLE l'incertitude. Beta(50,10) est concentré ;
        # un pas d'oubli l'élargit (variance strictement croissante).
        v0 = decay.beta_variance(50.0, 10.0)
        a, b = decay.decay_step(50.0, 10.0, 1.0, 1.0, 8)
        v1 = decay.beta_variance(a, b)
        self.assertGreater(v1, v0)

    def test_prior_is_fixed_point(self):
        # Un posterior DÉJÀ au prior ne bouge pas (rien à oublier).
        a, b = decay.decay_step(1.0, 1.0, 1.0, 1.0, 8)
        self.assertAlmostEqual(a, 1.0, places=12)
        self.assertAlmostEqual(b, 1.0, places=12)


class DecayNodeTests(TestCase):
    """Couche modèle : éligibilité + application société-scopée."""

    def setUp(self):
        self.company = Company.objects.create(nom='ASG Decay', slug='asg-decay')

    def _node(self, **kw):
        defaults = dict(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Hook facture.', enjeux_s=0.5, pertinence_r=0.5,
            alpha=50.0, beta=10.0, alpha0=1.0, beta0=1.0, demi_vie_semaines=8)
        defaults.update(kw)
        return AssumptionNode.objects.create(**defaults)

    def test_never_tested_is_eligible(self):
        node = self._node(last_tested_at=None)
        self.assertTrue(decay.needs_weekly_decay(node))

    def test_tested_this_week_is_skipped(self):
        node = self._node(last_tested_at=timezone.now())
        self.assertFalse(decay.needs_weekly_decay(node))

    def test_tested_over_a_week_ago_is_eligible(self):
        node = self._node(
            last_tested_at=timezone.now() - datetime.timedelta(days=8))
        self.assertTrue(decay.needs_weekly_decay(node))

    def test_seasonal_node_never_decayed(self):
        # §3.2 : la saisonnalité n'est PAS de l'oubli — jamais touchée.
        node = self._node(tags_saison=['ramadan'], last_tested_at=None)
        self.assertFalse(decay.needs_weekly_decay(node))

    def test_retired_node_skipped(self):
        node = self._node(
            statut=AssumptionNode.Statut.RETIRED, last_tested_at=None)
        self.assertFalse(decay.needs_weekly_decay(node))

    def test_decay_node_uses_class_half_life(self):
        node = self._node(demi_vie_semaines=None)  # défaut = classe créatif (8)
        r = 0.5 ** (1.0 / 8)
        decay.decay_node(node, save=True)
        node.refresh_from_db()
        self.assertAlmostEqual(node.alpha, r * 50.0 + (1 - r) * 1.0, places=9)

    def test_run_weekly_decay_only_eligible(self):
        eligible = self._node(last_tested_at=None)
        fresh = self._node(last_tested_at=timezone.now())
        seasonal = self._node(tags_saison=['ete'], last_tested_at=None)
        before_fresh = fresh.alpha
        before_seasonal = seasonal.alpha

        count = decay.run_weekly_decay(self.company)

        self.assertEqual(count, 1)
        eligible.refresh_from_db()
        fresh.refresh_from_db()
        seasonal.refresh_from_db()
        self.assertLess(eligible.alpha, 50.0)          # oublié
        self.assertEqual(fresh.alpha, before_fresh)    # intact
        self.assertEqual(seasonal.alpha, before_seasonal)  # intact

    def test_run_weekly_decay_is_company_scoped(self):
        other = Company.objects.create(nom='Autre', slug='autre-decay')
        mine = self._node(last_tested_at=None)
        theirs = AssumptionNode.objects.create(
            company=other, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='X', enjeux_s=0.5, pertinence_r=0.5,
            alpha=50.0, beta=10.0, alpha0=1.0, beta0=1.0,
            demi_vie_semaines=8, last_tested_at=None)

        decay.run_weekly_decay(self.company)

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertLess(mine.alpha, 50.0)      # ma société : oubliée
        self.assertEqual(theirs.alpha, 50.0)   # autre société : jamais touchée
