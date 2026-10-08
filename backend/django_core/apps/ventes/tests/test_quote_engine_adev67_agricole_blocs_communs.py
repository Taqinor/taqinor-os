"""ADEV67 (C-ADEV-044) — le PDF premium AGRICOLE imprime les trois blocs
communs aux autres marchés : note client, clauses/CGV gelées, mention
« Document mis à jour le … / Remplace le devis … » — sans dépasser 3 pages
(D-AGR-2), et sans bloc vide quand rien n'est à dire.

Renderer agricole RÉEL (``agricole.pages.build_html`` puis
``agricole.renderer.render_pdf_bytes`` quand PyMuPDF est présent) sur les
données complètes d'AGR310.

Test-du-test : retirer l'appel à ``marques_correction`` dans
``agricole/pages.py`` ⇒ ``test_mention_mis_a_jour`` échoue.
"""
from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.agricole import pages, renderer
from apps.ventes.tests.test_agr310_renderer_agricole import (
    data_complete, fitz, pages_et_debordements,
)

CLAUSE = {'nom': 'Garantie de bonne fin', 'corps_texte': 'CLAUSE-QA-ADEV67'}


def _data(**extra):
    d = data_complete()
    d.update(extra)
    return d


class BlocsCommunsParModeTests(SimpleTestCase):

    def test_note_client(self):
        html = pages.build_html(_data(note_client='NOTE-QA'))
        self.assertIn('NOTE-QA', html)

    def test_clauses_gelees(self):
        html = pages.build_html(_data(clauses_cgv=[CLAUSE]))
        self.assertIn('CLAUSE-QA-ADEV67', html)
        self.assertIn('Garantie de bonne fin', html)

    def test_mention_mis_a_jour(self):
        html = pages.build_html(_data(mis_a_jour_le='07/10/2026',
                                      remplace_reference='DEV-202610-0001'))
        self.assertIn('Document mis à jour le 07/10/2026', html)
        self.assertIn('Remplace le devis DEV-202610-0001', html)

    def test_aucun_bloc_vide(self):
        html = pages.build_html(_data(note_client='', clauses_cgv=[],
                                      mis_a_jour_le=None,
                                      remplace_reference=None))
        self.assertNotIn('clauses-cgv', html)
        self.assertNotIn('mis à jour le', html)


@tag('pdf')
class BlocsCommunsPdfReelTests(SimpleTestCase):

    def setUp(self):
        if fitz is None:  # pragma: no cover
            self.skipTest('PyMuPDF absent')

    def test_trois_pages_avec_les_trois_blocs(self):
        pdf = renderer.render_pdf_bytes(_data(
            note_client='NOTE-QA', clauses_cgv=[CLAUSE],
            mis_a_jour_le='07/10/2026'))
        n, debords = pages_et_debordements(pdf)
        self.assertEqual(n, 3)
        self.assertEqual(debords, [])
        doc = fitz.open(stream=pdf, filetype='pdf')
        try:
            texte = '\n'.join(p.get_text() for p in doc)
        finally:
            doc.close()
        for attendu in ('NOTE-QA', 'CLAUSE-QA-ADEV67', 'mis à jour'):
            self.assertIn(attendu, texte)
