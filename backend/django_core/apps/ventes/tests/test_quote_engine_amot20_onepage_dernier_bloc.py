"""AMOT20 (C-AMOT-018) — le une-page prouve sa postcondition sur le DERNIER
bloc de la zone (ligne Validité/Acompte/TVA) et sur le HTML RENDU : une note
×60 et trois clauses ×20 ne font plus disparaître en silence les conditions ;
au-delà, note et clauses sont tronquées avec renvoi déclaré « texte intégral
sur la proposition en ligne ». La page reste unique.

Oracle = positions des boîtes composées par WeasyPrint RÉEL (sauté sans
WeasyPrint). Test-du-test : ré-ancrer la mesure sur ``_formes_total_ttc``
seul (retirer ``_bas_bloc_fin`` de ``_mesure_onepage``) ⇒
``test_conditions_visibles`` échoue (« Acompte » hors de la zone).
"""
import unittest

from django.test import TestCase, tag

from apps.ventes.models import Devis
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

try:
    import weasyprint  # noqa: F401
    _WEASY = True
except Exception:  # noqa: BLE001
    _WEASY = False


@unittest.skipUnless(_WEASY, "WeasyPrint absent : mesure impossible")
@tag('pdf')
class OnepageDernierBlocTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot20-co', nom='AMOT20')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, [
                ('Panneau mono 550W', '10', '1100'),
                ('Onduleur réseau Huawei 5kW', '1', '8000'),
                ('Structure acier', '10', '300'),
                ('Installation et mise en service', '1', '4000'),
            ], reference='DEV-AMOT20-1')
        Devis.objects.filter(pk=self.devis.pk).update(
            note=('Note longue du commercial pour le client. ' * 60).strip(),
            clauses_appliquees=[
                {'type': 'clause', 'nom': f'Clause {i}',
                 'corps_texte': ('Texte contractuel de la clause. ' * 20)}
                for i in (1, 2, 3)])
        self.devis.refresh_from_db()

    def _rendu(self, langue):
        from weasyprint import HTML
        with G._RENDER_LOCK:
            data = build_quote_data(self.devis, clean_pdf_options(
                {'pdf_mode': 'onepage', 'langue_sortie': langue}))
            html = G.render_html_for({**data, 'pdf_mode': 'onepage'})
            formes_fin = G._formes_bloc_fin()
            formes_ttc = G._formes_total_ttc()
            renvoi = G._renvoi_texte_integral()
        pages = HTML(string=html).render().pages
        return html, pages, formes_fin, formes_ttc, renvoi

    def _boites_visibles(self, page):
        limite = page.height - G.ONEPAGE_FOOTER_PX
        return [b for b in G._boites_texte_onepage(page)
                if b.position_y + b.height <= limite + 0.5]

    def test_conditions_visibles(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                html, pages, formes_fin, formes_ttc, renvoi = self._rendu(
                    langue)
                self.assertEqual(len(pages), 1)
                visibles = ' | '.join(
                    b.text for b in self._boites_visibles(pages[0]))
                for forme in formes_fin:
                    if forme in html:
                        self.assertIn(forme, visibles, (langue, forme))
                self.assertTrue(any(f in visibles for f in formes_ttc))

    def test_renvoi_declare(self):
        html, pages, _f, _t, renvoi = self._rendu('fr')
        visibles = ' | '.join(b.text for b in self._boites_visibles(pages[0]))
        # La clause 2 est imprimée dans la zone visible, ou le texte long a
        # été remplacé par le renvoi déclaré.
        self.assertTrue('Clause 2' in visibles
                        or 'proposition en ligne' in visibles, visibles)
        self.assertIn('texte int&#233;gral sur la proposition en ligne', html)
        # Garde : l'ajustement ne laisse pas l'état tronqué derrière lui.
        self.assertFalse(G.ONEPAGE_TEXTES_TRONQUES)
