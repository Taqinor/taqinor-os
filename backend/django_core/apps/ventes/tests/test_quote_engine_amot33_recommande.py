"""AMOT33 (C-AMOT-043) — le gabarit résidentiel suit l'option recommandée du
serveur (``d["recommended"]``) : badge, phrase « Pourquoi nous la
recommandons », pastille page 3, légende et chiffres vedettes (−N %, gain net)
sur l'option recommandée ; aucun badge sans recommandation.

Rejoue VC s12 (``recommended Sans batterie`` mais « Option 2 Avec batterie
Recommandé », « Chiffres calculés pour l'option recommandée — avec
batterie »).

Test-du-test : remettre ``recommended=True`` littéral sur la chaîne de totaux
de l'option 2 ⇒ ``test_recommande_sans`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.figures import option_recommandee
from apps.ventes.quote_engine.residential import render, renderer
from apps.ventes.tests._quote_engine_common import _residential_sample_data


def _html(reco, **extra):
    data = _residential_sample_data()
    data['recommended'] = reco
    data.update(extra)
    return data, render.build_html(renderer._augment(data))


class RecommandeTests(SimpleTestCase):
    def test_option_recommandee(self):
        self.assertEqual(option_recommandee({'recommended': 'Sans batterie'}),
                         'sans')
        self.assertEqual(option_recommandee({'recommended': 'Avec batterie'}),
                         'avec')
        self.assertIsNone(option_recommandee(
            {'recommended': 'Aucune recommandation'}))
        self.assertEqual(option_recommandee({}), 'avec')
        self.assertEqual(option_recommandee(
            {'recommended': 'Sans batterie', 'regles_calcul_origine': True}),
            'avec')
        self.assertIsNone(option_recommandee(
            {'recommended': 'Sans batterie', 'deux_options': False}))

    def test_recommande_sans(self):
        data, html = _html('Sans batterie')
        self.assertIn("l'option recommandée — sans batterie", html)
        synthese = renderer.synthese_economies(data)
        if synthese is not None:
            self.assertEqual(synthese['eco_option'], 'sans')
        self.assertIn('option sans batterie', html)
        self.assertNotIn("l'option recommandée — avec batterie", html)

    def test_recommande_avec_inchange(self):
        _data, html = _html('Avec batterie')
        self.assertIn('Recommandé', html)
        self.assertIn('Pourquoi nous la recommandons', html)

    def test_aucune_recommandation(self):
        _data, html = _html('Aucune recommandation')
        self.assertNotIn('<span class="c1-reco-pill">', html)
        self.assertNotIn('p3-reco-mini">recommandé', html)
        self.assertNotIn('Pourquoi nous la recommandons', html)
        self.assertNotIn("l'option recommandée", html)
