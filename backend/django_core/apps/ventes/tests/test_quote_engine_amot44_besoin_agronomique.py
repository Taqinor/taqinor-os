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

    def test_mois_sous_tolerance_agronomique_trois_langues(self):
        """AMOT110 - la liste des mois sous tolerance ne dit "votre besoin"
        que pour un besoin DECLARE ; agronomique plein = libelle neutre."""
        ar = i18n_labels.libelle('agr_mois_couverture_agro', 'ar').format(
            mois=i18n_labels.libelle('agr_mois_10', 'ar'), pct='80')
        attendu = {'fr': 'octobre : 80 % du besoin agronomique estimé',
                   'en': 'October: 80 % of the estimated agronomic need',
                   'ar': ar}
        mois = [{'mois': 10, 'couverture_pct': 80}]
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                texte = pages._sous_tolerance(
                    {'base_besoin': 'agronomique_plein',
                     'mois_sous_tolerance': mois}, langue)
                self.assertIn(attendu[langue], texte)
        declare = pages._sous_tolerance(
            {'base_besoin': 'declare', 'mois_sous_tolerance': mois}, 'fr')
        self.assertIn('octobre : 80 % de votre besoin', declare)
