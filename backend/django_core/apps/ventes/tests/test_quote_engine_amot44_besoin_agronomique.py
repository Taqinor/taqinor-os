"""AMOT44 (C-AMOT-056) — la page 2 agricole qualifie la légende des barres
« besoin agronomique plein (FAO-56) » quand ``base_besoin ==
'agronomique_plein'`` (clé ``agr_base_besoin_agronomique`` fr/en/ar, phrase
``mentions.PHRASES_PROVENANCE['agronomique']``) ; un besoin DÉCLARÉ garde
« votre besoin ».

Synthèse réelle (``renderer._augment`` → ``synthese_agricole``), gabarit
réel. Test-du-test : retirer la lecture de ``base_besoin`` dans
``pages.page2`` ⇒ ``test_agronomique_trois_langues`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import i18n_labels
from apps.ventes.quote_engine.agricole import mentions, pages, renderer
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete


def _agronomique(langue):
    d = data_complete()
    d['langue_sortie'] = langue
    etude = d['etude']
    etude['besoin'] = {'mode': 'fao', 'region': 'souss-massa',
                       'cultures': [{'crop': 'olivier', 'ha': 3}],
                       'nature': 'agronomique_plein'}
    etude['besoin_mensuel'] = {'m3_jour_mois': [135] * 12,
                               'nature': 'agronomique_plein',
                               'source_et0': 'FAO-56 Penman-Monteith'}
    return d


class BesoinAgronomiqueTests(SimpleTestCase):
    def test_agronomique_trois_langues(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                d = renderer._augment(_agronomique(langue))
                bvl = (d.get('synthese') or {}).get('besoin_vs_livre')
                self.assertEqual((bvl or {}).get('base_besoin'),
                                 'agronomique_plein')
                page2 = pages.page2(pages.build_ctx(d))
                phrase = mentions.PHRASES_PROVENANCE['agronomique'][langue]
                self.assertIn(phrase, page2)
                self.assertNotIn(
                    i18n_labels.libelle('agr_legende_barres', langue), page2)

    def test_besoin_declare_inchange(self):
        d = renderer._augment(data_complete())
        page2 = pages.page2(pages.build_ctx(d))
        self.assertIn(i18n_labels.libelle('agr_legende_barres', 'fr'), page2)
        self.assertNotIn('FAO-56', page2)
