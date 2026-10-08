"""AGR319 — annexe « Note de calcul du kit de pompage » (pièce du dossier
FDA, Guide FDA 2024 p.21), rendue par le renderer agricole SEULEMENT sur
l'option explicite ``include_note_calcul``.

HTML réel (``pages.build_html``) : option off → 3 pages inchangées ; option
on → 4 pages, annexe sans « None », aucun montant d'aide ni ``prix_achat``.
La whitelist ``clean_pdf_options`` ne laisse passer qu'un booléen, défaut off.
PDF réel (``@tag('pdf')``) : 4 pages, aucun débordement.
"""
import re

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.agricole import pages, renderer
from apps.ventes.quote_engine.builder import clean_pdf_options
from apps.ventes.tests.test_agr310_renderer_agricole import (
    data_complete, fitz, pages_et_debordements,
)

HYPOTHESES = [
    {'cle': 'energie_hydraulique_wh_par_m3_m', 'valeur': 2.725,
     'statut': 'physique', 'source': 'ρ·g/3600'},
    {'cle': 'rendement_pompe_pct', 'valeur': 55, 'statut': 'estimation',
     'source': None},
]


def _data(option=True, references=None, **kw):
    d = data_complete(**kw)
    d['etude'].update({
        'hmt_composantes': {'niveau_dynamique_m': 40, 'denivele_m': 4,
                            'pertes_lineaires_m': 3.7,
                            'pertes_singulieres_m': 0.8,
                            'pression_service_m': 10.2},
        'conception': {'mois_critique': 12, 'debit_conception_m3h': 30.7},
        'hypotheses_pompage': list(HYPOTHESES),
    })
    # AMOT43 — forme réelle : la HMT saisie vit sous ``entrees.hmt_saisie_m``.
    d['etude']['provenance_pompage']['entrees']['hmt_saisie_m'] = {
        'origine': 'calculee', 'detail': None, 'date': '2026-09-15'}
    for it in d['all_items']:
        it['description'] = f"Fiche de {it['designation']}"
        it['prix_achat'] = 1234.0  # jamais imprimé
    if option:
        d['include_note_calcul'] = True
        d['references_pompage'] = list(references or [])
    return d


def _html(d):
    return pages.build_html(renderer._augment(d))


def _annexe(html):
    return html.split('<div class="page">')[4]


class Agr319NoteCalculTests(SimpleTestCase):

    def test_option_off_trois_pages_inchangees(self):
        sans = _html(_data(option=False))
        self.assertEqual(sans.count('<div class="page">'), 3)
        self.assertNotIn('Note de calcul', sans)
        self.assertIn('Page 3 / 3', sans)

    def test_option_on_quatre_pages_et_contenu(self):
        html = _html(_data())
        self.assertEqual(html.count('<div class="page">'), 4)
        self.assertIn('Page 4 / 4', html)
        annexe = _annexe(html)
        for attendu in ('Note de calcul du kit de pompage',
                        'Champ photovoltaïque : 7,7 kWc, 14 panneaux',
                        'Pompe immergée OSP 30/8 10 CV',
                        'garantie 3 ans',
                        'Hauteur manométrique totale retenue : 58,7 m',
                        'Pertes linéaires', 'Pression de service',
                        'Débit de conception : 30,7 m³/h (mois critique : '
                        'décembre)',
                        'energie_hydraulique_wh_par_m3_m', 'EST.',
                        'Fiche de VARIATEUR VEICHI SI23 7.5KW 380V',
                        'Aucune référence de pompage à ce jour.'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, annexe)
        self.assertNotIn('None', annexe)

    def test_references_agricoles_servies(self):
        html = _html(_data(references=[
            {'titre': 'Pompage 7,5 kW', 'ville': 'Taroudant',
             'mise_en_service': '2026-05'}]))
        annexe = _annexe(html)
        self.assertIn('Pompage 7,5 kW — Taroudant (2026-05)', annexe)
        self.assertNotIn('Aucune référence de pompage', annexe)

    def test_aucun_montant_d_aide_ni_prix_achat(self):
        annexe = _annexe(_html(_data()))
        self.assertNotIn('1234', annexe)
        self.assertNotIn('1 234', annexe)
        self.assertNotIn('prix_achat', annexe)
        self.assertNotIn('FDA :', annexe)
        # Aucun montant en dirhams dans l'annexe (ni aide, ni prix).
        self.assertIsNone(re.search(r'\d[\d\s ]*(MAD|DH)\b', annexe))

    def test_whitelist_booleen_defaut_off(self):
        self.assertFalse(clean_pdf_options({})['include_note_calcul'])
        self.assertTrue(
            clean_pdf_options({'include_note_calcul': 1})['include_note_calcul'])
        self.assertFalse(clean_pdf_options(
            {'include_note_calcul': ''})['include_note_calcul'])


@tag('pdf')
class Agr319PdfReelTests(SimpleTestCase):

    def setUp(self):
        if fitz is None:  # pragma: no cover
            self.skipTest('PyMuPDF absent')

    def test_off_trois_pages_on_quatre_pages(self):
        for option, attendu in ((False, 3), (True, 4)):
            with self.subTest(option=option):
                n, debords = pages_et_debordements(
                    renderer.render_pdf_bytes(_data(option=option)))
                self.assertEqual(n, attendu)
                self.assertEqual(debords, [])
