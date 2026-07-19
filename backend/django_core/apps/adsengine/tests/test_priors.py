"""ASG8 — Tests des priors hiérarchiques intra-tenant (dd-assumption-engine §3.4/§6).

Prouve :
  * la méthode des moments + le plafond ``κ_max = min(50, 1 sem d'événements)`` ;
  * un nœud neuf CONVERGE vers sa donnée locale en ~1 semaine (le prior ne
    retarde jamais) ;
  * l'héritage ne traverse JAMAIS une frontière de société (invariant §6).
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import priors
from apps.adsengine.models import AssumptionNode


class PriorMathTests(SimpleTestCase):
    """Cœur pur : méthode des moments + plafonnement."""

    def test_kappa_max_caps_at_50(self):
        self.assertEqual(priors.kappa_max(200), 50.0)
        self.assertEqual(priors.kappa_max(30), 30.0)
        self.assertEqual(priors.kappa_max(0), 1.0)  # plancher

    def test_method_of_moments_recovers_mean(self):
        a, b = priors.method_of_moments(0.6, 0.01)
        self.assertAlmostEqual(a / (a + b), 0.6, places=6)

    def test_zero_variance_is_max_concentration(self):
        a, b = priors.method_of_moments(0.6, 0.0)
        self.assertAlmostEqual(a + b, priors.KAPPA_HARD_CAP, places=6)
        self.assertAlmostEqual(a / (a + b), 0.6, places=6)

    def test_cap_concentration_preserves_mean(self):
        a, b = priors.cap_concentration(300.0, 200.0, 50.0)
        self.assertAlmostEqual(a + b, 50.0, places=6)
        self.assertAlmostEqual(a / (a + b), 0.6, places=6)

    def test_cap_noop_when_under(self):
        self.assertEqual(priors.cap_concentration(3.0, 2.0, 50.0), (3.0, 2.0))

    def test_fit_prior_from_siblings_capped(self):
        a0, b0 = priors.fit_prior([0.6, 0.6, 0.6], weekly_events=200)
        self.assertAlmostEqual(a0, 30.0, places=6)
        self.assertAlmostEqual(b0, 20.0, places=6)

    def test_fit_prior_empty_is_uniform(self):
        self.assertEqual(priors.fit_prior([], weekly_events=50), (1.0, 1.0))

    def test_local_data_dominates_within_one_week(self):
        # §3.4 : la donnée locale domine en ~1 semaine. Prior hérité centré sur
        # 0.6 (κ=50) ; vraie valeur locale 0.2 ; 1 semaine = 200 événements.
        a0, b0 = priors.fit_prior([0.6, 0.6, 0.6], weekly_events=200)
        prior_mean = a0 / (a0 + b0)
        a, b = priors.posterior_after_events(a0, b0, successes=40, trials=200)
        post_mean = a / (a + b)
        local = 0.2
        # Le posterior a franchi la moitié du chemin vers le local (domination).
        self.assertLess(abs(post_mean - local), abs(prior_mean - local) * 0.5)


class InheritPriorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASG Priors', slug='asg-pri')

    def _node(self, company=None, classe=AssumptionNode.Classe.CREATIF,
              enonce='n', alpha=1.0, beta=1.0, **kw):
        return AssumptionNode.objects.create(
            company=company or self.company, classe=classe, enonce_fr=enonce,
            enjeux_s=0.5, pertinence_r=0.5,
            alpha=alpha, beta=beta, alpha0=1.0, beta0=1.0, **kw)

    def test_inherits_from_same_company_siblings(self):
        # 3 frères créatif à 0.6 (α=6, β=4).
        for i in range(3):
            self._node(enonce=f'sib{i}', alpha=6.0, beta=4.0)
        fresh = self._node(enonce='neuf', alpha=1.0, beta=1.0)

        a0, b0 = priors.inherit_prior(fresh, weekly_events=200)

        self.assertAlmostEqual(a0 / (a0 + b0), 0.6, places=2)
        fresh.refresh_from_db()
        # Nœud à froid : le posterior redémarre sur le prior hérité.
        self.assertEqual((fresh.alpha, fresh.beta), (a0, b0))
        self.assertEqual((fresh.alpha0, fresh.beta0), (a0, b0))

    def test_never_crosses_company_boundary(self):
        # INVARIANT §6 : frères de MA société (0.6) hérités ; ceux d'une AUTRE
        # société (0.05, extrême) IGNORÉS.
        other = Company.objects.create(nom='Autre', slug='autre-pri')
        for i in range(3):
            self._node(enonce=f'mine{i}', alpha=6.0, beta=4.0)      # 0.6
        for i in range(3):
            self._node(company=other, enonce=f'theirs{i}',
                       alpha=1.0, beta=19.0)                        # 0.05

        fresh = self._node(enonce='neuf', alpha=1.0, beta=1.0)
        a0, b0 = priors.inherit_prior(fresh, weekly_events=200)

        # Non tiré vers 0.05 : reste centré sur 0.6 (mes frères seuls).
        self.assertGreater(a0 / (a0 + b0), 0.5)

    def test_explicit_category_nodes_refilters_foreign(self):
        # Même en passant explicitement un nœud d'une autre société, il est
        # RE-FILTRÉ (garde-fou de l'invariant).
        other = Company.objects.create(nom='Autre2', slug='autre2-pri')
        mine = self._node(enonce='mine', alpha=6.0, beta=4.0)          # 0.6
        theirs = self._node(company=other, enonce='theirs',
                            alpha=1.0, beta=19.0)                       # 0.05
        fresh = self._node(enonce='neuf', alpha=1.0, beta=1.0)

        a0, b0 = priors.inherit_prior(
            fresh, weekly_events=200, category_nodes=[mine, theirs])

        # Seul « mine » (0.6) compte ; « theirs » ignoré → moyenne ~0.6.
        self.assertAlmostEqual(a0 / (a0 + b0), 0.6, places=2)

    def test_no_siblings_yields_uniform_prior(self):
        fresh = self._node(enonce='seul', alpha=1.0, beta=1.0)
        a0, b0 = priors.inherit_prior(fresh, weekly_events=50)
        self.assertEqual((a0, b0), (1.0, 1.0))

    def test_does_not_overwrite_learned_posterior(self):
        for i in range(3):
            self._node(enonce=f'sib{i}', alpha=6.0, beta=4.0)
        # Nœud AVEC apprentissage (posterior ≠ prior) : le prior change, mais le
        # posterior appris n'est PAS ré-ancré.
        learned = self._node(enonce='appris', alpha=40.0, beta=8.0)
        priors.inherit_prior(learned, weekly_events=200)
        learned.refresh_from_db()
        self.assertEqual((learned.alpha, learned.beta), (40.0, 8.0))
