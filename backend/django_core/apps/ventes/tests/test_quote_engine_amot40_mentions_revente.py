"""AMOT40 (C-AMOT-049, volet PDF) — CHAQUE mention de revente servie par
``revente.mentions`` (6, dont « potentiel non garanti ») s'imprime dans la
langue du document, sur le PDF commercial ET industriel.

Rejoue VC lci5 (industriel FR 6/6, industriel EN 0 et « non garanti »
absent ; commercial FR et EN : seule la mention 82-21). Compte des mentions
dans le HTML rendu (jamais une regex de source). Les mentions servies sont
celles de ``economie_ci.revente_ci`` (constantes réelles).

Test-du-test : remettre le filtre ``if langue != "fr": mentions =
[TEXTES_82_21…]`` dans ``_ligne_revente`` ⇒ l'industriel EN retombe à
2 mentions et ``test_industriel_six_mentions`` rougit.
"""
import copy

from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco
from apps.ventes.quote_engine.ci import mentions as M
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.constants_82_21 import MENTION_82_21, MENTION_ART13
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

SERVIES = [MENTION_82_21, eco.MENTION_NON_GARANTI, eco.MENTION_SECOND_COMPTEUR,
           eco.MENTION_TSS, eco.MENTION_TARIF_ARRETE, MENTION_ART13]
REVENTE = {'statut': 'calculee', 'kwh_an': 12000, 'plafond_kwh': 20000,
           'valeur_mad_an': 2280.0, 'mentions': list(SERVIES)}


def _attendus(langue):
    return M.mentions_revente(SERVIES, langue)


def _html(sample, renderer, render, cle, langue):
    data = copy.deepcopy(sample.build())
    data['langue_sortie'] = langue
    d = renderer._augment(data)
    syn = dict(d.get(cle) or {})
    argent = dict(syn.get('argent') or {})
    argent['revente'] = dict(REVENTE)
    syn['argent'] = argent
    d[cle] = syn
    return render.build_html(d)


class MentionsReventeTests(SimpleTestCase):

    def test_table_six_mentions_trilingue(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                sortie = _attendus(langue)
                self.assertEqual(len(sortie), 6)
                self.assertEqual(len(set(sortie)), 6)
        self.assertIn('not guaranteed', ' '.join(_attendus('en')))
        # Une mention inconnue reste servie telle quelle (jamais retirée).
        self.assertEqual(M.mentions_revente(['Mention neuve'], 'en'),
                         ['Mention neuve.'])

    def test_industriel_six_mentions(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                html = _html(i_sample, i_renderer, i_render, 'ind_synthese',
                             langue)
                for mention in _attendus(langue):
                    self.assertIn(mention, html)

    def test_commercial_six_mentions(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                html = _html(c_sample, c_renderer, c_render, 'com_synthese',
                             langue)
                for mention in _attendus(langue):
                    self.assertIn(mention, html)
