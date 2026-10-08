"""AMOT44 (C-AMOT-056) — la légende des barres de la page 2 agricole dit
« besoin agronomique plein (FAO-56) » quand ``base_besoin ==
'agronomique_plein'`` ; « votre besoin » reste réservé à la nature déclarée.

Rejoue VC agr3 (``base_besoin agronomique_plein``, page 2 « Gris : votre
besoin par jour », 0 « agronomique », 0 « FAO »). La synthèse est la vraie
``synthese_agricole`` (via ``renderer._augment``), fr / en / ar.

Test-du-test : retirer la lecture de ``base_besoin`` dans ``pages.page2`` ⇒
``test_agronomique_qualifie`` rougit.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole import mentions, pages, renderer
from apps.ventes.quote_engine import i18n_labels
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete


def _data_agronomique(langue):
    d = data_complete()
    d['langue_sortie'] = langue
    etude = d['etude']
    etude['besoin'] = {'mode': 'fao', 'nature': 'agronomique_plein',
                       'cultures': [{'crop': 'olivier', 'ha': 3}],
                       'region': 'marrakech_safi'}
    etude['besoin_mensuel'] = {'m3_jour_mois': [120] * 12,
                               'nature': 'agronomique_plein',
                               'source_et0': 'FAO-56 / ET0 régionale'}
    return d


class BesoinAgronomiqueTests(SimpleTestCase):

    def test_agronomique_qualifie(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                d = renderer._augment(_data_agronomique(langue))
                self.assertEqual(
                    d['synthese']['besoin_vs_livre']['base_besoin'],
                    'agronomique_plein')
                html = pages.build_html(d)
                self.assertIn(
                    mentions.phrase_provenance('agronomique', langue), html)
                self.assertNotIn(
                    i18n_labels.libelle('agr_legende_barres', langue), html)

    def test_besoin_declare_garde_votre_besoin(self):
        d = renderer._augment(data_complete())
        self.assertEqual(d['synthese']['besoin_vs_livre']['base_besoin'],
                         'declare')
        html = pages.build_html(d)
        self.assertIn(i18n_labels.libelle('agr_legende_barres', 'fr'), html)
        self.assertNotIn('FAO-56', html)
