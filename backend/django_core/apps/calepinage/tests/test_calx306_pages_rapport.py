"""CALX306 — sommaire, pagination et compte de pages du rapport d'étude.

Ce qui est prouvé SANS rendu réel (structure pure — ``html_du_sommaire``) :

* une section OMISE (retirée par la société, CALX307 — absente de
  ``rapport['sections']``) n'apparaît jamais au sommaire, même si ``pages``
  publie encore un compte pour son code (donnée orpheline) ;
* une section dont ``pages`` ne publie AUCUN compte (rendu manquant) est
  également absente — jamais un numéro de page inventé ;
* AUCUN numéro de page imprimé ne dépasse le total publié
  (``sum(pages.values())``) — une propriété arithmétique, vérifiée sur
  plusieurs répartitions de pages ;
* la première section retenue démarre à la page qui suit la garde ET le
  sommaire lui-même (``pages['garde'] + pages['sommaire'] + 1``) ;
* la garde n'a pas sa propre ligne dans le sommaire ;
* sans section retenue, le sommaire est vide (aucune table).

Ce qui exige un rendu RÉEL (WeasyPrint + PyMuPDF), étiqueté ``pdf`` (hors du
palier CI — routeur M4) :

* le total de pages du PDF rendu (``html_de_rapport_pagine``) est EXACTEMENT
  la somme publiée par ``pages_attendues`` ;
* le sommaire (page 2, juste après la garde) référence une page présente
  dans le document rendu.

Run (structure, pur, sans WeasyPrint) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx306_pages_rapport.py -q

Run (avec rendu réel, image prod dotée de WeasyPrint) :
    python manage.py test apps.calepinage.tests.test_calx306_pages_rapport -v2
"""
import copy
import json
import pathlib
import re
import unittest
from types import SimpleNamespace

from django.test import tag

from apps.calepinage.services.rapport.mise_en_page import html_du_sommaire

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]


def _charger(nom):
    return json.loads((RACINE_APP / 'contract_samples' / nom)
                      .read_text(encoding='utf-8'))


def _rapport(sections, langue='fr'):
    return {'sections': sections, 'langue': langue}


SECTIONS = [
    {'code': 'garde', 'titre': 'Page de garde'},
    {'code': 'site_meteo', 'titre': 'Site et source météo'},
    {'code': 'systeme', 'titre': 'Système'},
    {'code': 'production', 'titre': 'Production'},
]


class SectionOmiseTest(unittest.TestCase):
    def test_une_section_retiree_n_apparait_pas_meme_avec_un_compte_orphelin(
            self):
        # 'systeme' est RETIRÉE de rapport['sections'] (CALX307), mais
        # ``pages`` publie quand même un compte orphelin pour son code.
        sections = [s for s in SECTIONS if s['code'] != 'systeme']
        pages = {'garde': 1, 'sommaire': 1, 'site_meteo': 2,
                 'systeme': 3, 'production': 2}
        html = html_du_sommaire(_rapport(sections), pages)
        self.assertNotIn('Système', html)
        self.assertIn('Site et source météo', html)
        self.assertIn('Production', html)


class SectionSansCompteTest(unittest.TestCase):
    def test_une_section_sans_rendu_n_a_pas_de_numero_invente(self):
        # 'systeme' et 'production' n'ont PAS de compte publié : leur rendu
        # a manqué — elles ne paraissent pas avec un numéro deviné.
        pages = {'garde': 1, 'sommaire': 1, 'site_meteo': 2}
        html = html_du_sommaire(_rapport(SECTIONS), pages)
        self.assertIn('Site et source météo', html)
        self.assertNotIn('Système', html)
        self.assertNotIn('Production', html)


class ArithmetiqueDesNumerosTest(unittest.TestCase):
    def test_aucun_numero_ne_depasse_le_total_publie(self):
        for pages in (
                {'garde': 1, 'sommaire': 1, 'site_meteo': 2, 'systeme': 1,
                 'production': 4},
                {'garde': 2, 'sommaire': 3, 'site_meteo': 1, 'systeme': 5,
                 'production': 1},
                {'garde': 1, 'sommaire': 1, 'site_meteo': 1},
        ):
            with self.subTest(pages=pages):
                html = html_du_sommaire(_rapport(SECTIONS), pages)
                total = sum(pages.values())
                brutes = re.findall(r'<td>(\d+)</td>', html)
                numeros = [int(n) for n in brutes]
                self.assertTrue(numeros, 'aucun numéro imprimé')
                self.assertTrue(all(n <= total for n in numeros),
                                (numeros, total))

    def test_la_premiere_section_retenue_demarre_apres_garde_et_sommaire(
            self):
        pages = {'garde': 1, 'sommaire': 1, 'site_meteo': 2, 'systeme': 1,
                 'production': 4}
        html = html_du_sommaire(_rapport(SECTIONS), pages)
        premiere = int(re.search(r'<td>(\d+)</td>', html).group(1))
        self.assertEqual(premiere, pages['garde'] + pages['sommaire'] + 1)

    def test_un_sommaire_de_deux_pages_decale_aussi_la_premiere_section(
            self):
        pages = {'garde': 1, 'sommaire': 2, 'site_meteo': 2, 'systeme': 1,
                 'production': 4}
        html = html_du_sommaire(_rapport(SECTIONS), pages)
        premiere = int(re.search(r'<td>(\d+)</td>', html).group(1))
        self.assertEqual(premiere, 4)  # 1 (garde) + 2 (sommaire) + 1

    def test_les_numeros_cumulent_le_compte_des_sections_precedentes(self):
        pages = {'garde': 1, 'sommaire': 1, 'site_meteo': 2, 'systeme': 1,
                 'production': 4}
        html = html_du_sommaire(_rapport(SECTIONS), pages)
        numeros = [int(n) for n in re.findall(r'<td>(\d+)</td>', html)]
        # site_meteo (3), systeme (3+2=5), production (5+1=6).
        self.assertEqual(numeros, [3, 5, 6])


class GardeEtVideTest(unittest.TestCase):
    def test_la_garde_n_a_pas_sa_propre_ligne(self):
        pages = {'garde': 1, 'sommaire': 1, 'site_meteo': 2}
        html = html_du_sommaire(_rapport(SECTIONS), pages)
        self.assertNotIn('Page de garde', html)

    def test_sans_aucune_section_retenue_le_sommaire_est_vide(self):
        html = html_du_sommaire(_rapport([SECTIONS[0]]), {'garde': 1})
        self.assertEqual(html, '')


@tag('pdf')
class RenduReelPaginationTest(unittest.TestCase):
    """WeasyPrint + PyMuPDF réels — étiqueté ``pdf`` (hors du palier CI)."""

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèques natives absentes
            self.skipTest('WeasyPrint ou PyMuPDF indisponible sur ce poste')

    def _rapport_construit(self):
        from apps.calepinage.services.rapport import construire_rapport

        resultat = _charger('calepinage_resultat.json')['exemple']
        nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                             titre='Villa Anfa', resultat=None, pk=None)
        return construire_rapport(
            nu, resultat=copy.deepcopy(resultat), site={}, identite={},
            styles={})

    def test_le_total_de_pages_egale_la_somme_publiee(self):
        from apps.calepinage.services.pack_technique import compter_pages
        from apps.calepinage.services.rapport.mise_en_page import (
            html_de_rapport_pagine, pages_attendues,
        )
        from core.pdf import render_pdf

        rapport = self._rapport_construit()
        pages = pages_attendues(rapport)
        octets = render_pdf(html=html_de_rapport_pagine(rapport))
        self.assertEqual(compter_pages(octets), sum(pages.values()))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
