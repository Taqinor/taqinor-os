"""AGEN4 — Tests du filet de véracité non-numérique.

Prouve (dd-assumption-engine §10.2 point 3) : sans clé → routage Palier B
systématique (jamais A par optimisme) ; une affirmation peu ancrée → score bas
→ Palier B ; une affirmation ancrée (score ≥ seuil) → Palier A.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import groundedness


class NoKeyRoutesToBTests(SimpleTestCase):
    def test_no_key_no_scorer_routes_to_b(self):
        # SimpleTestCase : pas de DB — company factice, scoreur None.
        result = groundedness.score_groundedness(
            company=None, text='Le meilleur installateur du Maroc.',
            references=[], scorer=None)
        self.assertFalse(result['enabled'])
        self.assertEqual(result['tier'], groundedness.TIER_B)
        self.assertIsNone(result['score'])


class ScorerRoutingTests(SimpleTestCase):
    def test_low_score_routes_to_b(self):
        result = groundedness.score_groundedness(
            company=None, text='Promesse inventée hors composants.',
            references=['panneaux solaires garantis'],
            scorer=lambda t, r: 0.2)
        self.assertTrue(result['enabled'])
        self.assertFalse(result['grounded'])
        self.assertEqual(result['tier'], groundedness.TIER_B)

    def test_high_score_routes_to_a(self):
        result = groundedness.score_groundedness(
            company=None, text='Installation solaire clé en main.',
            references=['installation solaire clé en main'],
            scorer=lambda t, r: 0.95)
        self.assertTrue(result['grounded'])
        self.assertEqual(result['tier'], groundedness.TIER_A)

    def test_scorer_returning_none_routes_to_b(self):
        result = groundedness.score_groundedness(
            company=None, text='x', references=[], scorer=lambda t, r: None)
        self.assertEqual(result['tier'], groundedness.TIER_B)

    def test_threshold_override(self):
        result = groundedness.score_groundedness(
            company=None, text='x', references=[], scorer=lambda t, r: 0.5,
            threshold=0.4)
        self.assertEqual(result['tier'], groundedness.TIER_A)


class DefaultReferencesTests(TestCase):
    def test_references_default_to_published_fact_sources(self):
        from datetime import date
        from apps.adsengine.models import FactEntry, FactTable
        company = Company.objects.create(nom='Gr Co', slug='gr-co')
        table = FactTable.create_draft(company)
        FactEntry.objects.create(
            table=table, cle='garantie', valeur='25', unite='ans',
            source='fabricant', verifie_le=date(2026, 1, 1))
        table.publish()

        captured = {}

        def scorer(text, refs):
            captured['refs'] = refs
            return 0.9

        groundedness.score_groundedness(
            company=company, text='Garantie longue durée.', scorer=scorer)
        self.assertTrue(any('garantie' in r for r in captured['refs']))
