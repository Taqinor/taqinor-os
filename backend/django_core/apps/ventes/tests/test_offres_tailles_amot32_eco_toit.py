"""AMOT32 (C-AMOT-033) — la taille « Éco » est bornée par le toit : Éco ≤
toit_max et ≤ Max, collapse quand elle ne tient pas ; l'ordre Éco ≤ Max ≤ toit
est une propriété testée.

Rejoue VB (mur physique 26 ⇒ ``{'recommande': 22, 'eco': 30, 'max': 26}`` ;
contenance 24 ⇒ ``eco 30, max 24``).

Test-du-test : retirer le ``min(…, toit_max)`` de ``borner_eco`` ⇒ rouge.
"""
import random

from django.test import SimpleTestCase

from apps.ventes.offres_tailles import borner_eco

try:
    from hypothesis import given
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover — hypothesis absent : tirages fixes
    given = None


class EcoToitTests(SimpleTestCase):
    def test_cas_vb(self):
        self.assertEqual(
            borner_eco({'recommande': 22, 'eco': 30, 'max': 26}, 26),
            {'recommande': 22, 'max': 26})
        self.assertEqual(borner_eco({'eco': 30, 'max': 24}, 24), {'max': 24})

    def test_eco_qui_tient_reste(self):
        self.assertEqual(borner_eco({'eco': 18, 'max': 26}, 30),
                         {'eco': 18, 'max': 26})

    def test_toit_seul_borne(self):
        self.assertEqual(borner_eco({'eco': 30}, 26), {})

    def _propriete(self, eco, maxi, toit):
        champs = borner_eco({'eco': eco, 'max': maxi}, toit)
        if 'eco' in champs:
            self.assertLessEqual(champs['eco'], champs['max'])
            self.assertLessEqual(champs['eco'], toit)

    def test_propriete_tirages(self):
        rng = random.Random(33)
        for _ in range(500):
            self._propriete(rng.randint(1, 60), rng.randint(1, 60),
                            rng.randint(1, 60))

    if given is not None:
        @given(st.integers(1, 80), st.integers(1, 80), st.integers(1, 80))
        def test_propriete_hypothesis(self, eco, maxi, toit):
            self._propriete(eco, maxi, toit)
