"""AMOT40 (C-AMOT-049) — chaque mention de revente servie par
``revente.mentions`` (dont « potentiel non garanti ») s'imprime dans la
langue du document, sur le PDF commercial ET industriel : la table trilingue
``ci/mentions.py`` porte les 6 mentions (textes en/ar à relire par le
fondateur, patron CIQM22).

Moteur C&I réel (``economie_ci.revente_ci`` pour la liste des 6), gabarits
réels (rendu HTML), aucun mock. Test-du-test : remettre le filtre
``if langue != "fr": mentions = [TEXTES_82_21…]`` dans
``industriel.finance._ligne_revente`` ⇒ ``test_rendu_trois_langues`` échoue
(« not guaranteed » absent en anglais).
"""
import copy
import html as _html

from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco
from apps.ventes.quote_engine.ci.mentions import mentions_revente
from apps.ventes.quote_engine.commercial import render as com_render
from apps.ventes.quote_engine.commercial import renderer as com_renderer
from apps.ventes.quote_engine.commercial import sample_data as com_sample
from apps.ventes.quote_engine.constants_82_21 import MENTION_82_21, MENTION_ART13
from apps.ventes.quote_engine.industriel import render as ind_render
from apps.ventes.quote_engine.industriel import renderer as ind_renderer
from apps.ventes.quote_engine.industriel import sample_data as ind_sample

SIX = [MENTION_82_21, eco.MENTION_NON_GARANTI, eco.MENTION_SECOND_COMPTEUR,
       eco.MENTION_TSS, eco.MENTION_TARIF_ARRETE, MENTION_ART13]


class MentionsReventeTests(SimpleTestCase):
    def test_six_mentions_trois_langues(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                sortie = mentions_revente(SIX, langue)
                self.assertEqual(len(sortie), 6)
                self.assertEqual(len(set(sortie)), 6)
        en = ' '.join(mentions_revente(SIX, 'en'))
        self.assertIn('not guaranteed', en)
        self.assertNotIn('non garanti', en)
        self.assertIn('non garanti', ' '.join(mentions_revente(SIX, 'fr')))

    def _data(self, sample, langue):
        base = copy.deepcopy(sample.build())
        ec = ind_sample.economie_ci()
        revente = (ec.get('revente') or {})
        revente['mentions'] = list(SIX)
        ec['revente'] = revente
        base['economie_ci'] = ec
        base['langue_sortie'] = langue
        return base

    def test_rendu_trois_langues(self):
        for nom, sample, renderer, render in (
                ('commercial', com_sample, com_renderer, com_render),
                ('industriel', ind_sample, ind_renderer, ind_render)):
            for langue in ('fr', 'en', 'ar'):
                with self.subTest(gabarit=nom, langue=langue):
                    h = _html.unescape(render.build_html(
                        renderer._augment(self._data(sample, langue))))
                    for mention in mentions_revente(SIX, langue):
                        self.assertIn(_html.unescape(mention), h, mention)
