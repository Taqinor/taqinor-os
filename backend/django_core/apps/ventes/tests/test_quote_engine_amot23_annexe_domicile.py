"""AMOT23 (C-AMOT-021) — le gabarit résidentiel 3 pages imprime l'annexe de
rétractation (CAD122) quand le bon de commande est signé au domicile, par
UNE fonction HTML pure partagée avec le legacy ; le pied « Page n / N » la
compte. Sans le drapeau : 3 pages, aucune annexe.

Rendu réel du gabarit (``render.build_html(renderer._augment(data))``).

Test-du-test : retirer l'appel dans ``residential/render.build_html`` ⇒
``test_annexe_presente_et_comptee`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import annexe_domicile
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.residential import render, renderer
from apps.ventes.tests._quote_engine_common import _residential_sample_data

FORMULAIRE = 'Formulaire détachable de rétractation'


def _html(**extra):
    data = _residential_sample_data()
    data.update(extra)
    return render.build_html(renderer._augment(data))


def _nb_pages(html):
    return html.count('<div class="page">')


class AnnexeDomicileTests(SimpleTestCase):

    def test_annexe_presente_et_comptee(self):
        html = _html(signe_au_domicile=True)
        self.assertIn(FORMULAIRE, html)
        n = _nb_pages(html)
        self.assertEqual(n, _nb_pages(_html()) + 1)
        self.assertIn('/ %d' % n, html)

    def test_sans_drapeau_aucune_annexe(self):
        html = _html()
        self.assertNotIn(FORMULAIRE, html)

    def test_legacy_meme_fonction(self):
        corps = annexe_domicile.corps_annexe_domicile(
            ref='DEV-1', vendeur='SOCIETE',
            couleurs={'navy': '#000', 'texte': '#111', 'muet': '#222',
                      'fond': '#fff', 'filet': '#333'})
        self.assertIn(FORMULAIRE, corps)
        self.assertIs(G._corps_annexe_domicile,
                      annexe_domicile.corps_annexe_domicile)
        self.assertEqual(G.DELAI_RETRACTATION_DOMICILE_JOURS,
                         annexe_domicile.DELAI_RETRACTATION_DOMICILE_JOURS)
