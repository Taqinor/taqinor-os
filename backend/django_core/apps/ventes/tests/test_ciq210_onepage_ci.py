"""CIQ210 (complément) — le UNE-PAGE d'un devis commercial ou industriel lit
les MÊMES chiffres que le document complet et /proposition.

Avant : la rangée résumé du une-page (moteur legacy) imprimait la production
« par ville » (``prod_kwh``) et l'économie ``eco_s_ann`` de
``calculate_savings_roi`` (BT, autoconsommation fixe 60 %) — même quand le
bloc ``economie_ci`` était calculé. Après : production du moteur C&I,
économie et retour du bloc ``economie_ci`` (``synthese_ci.argent``) via
``chiffres_cles`` ; absent ⇒ vignette omise, jamais un repli.

Tests PURS : HTML EXACT des deux formats (aucune base, aucun WeasyPrint).
La parité sur un devis réel (builder + /proposition) est dans
``test_figures_parite`` (scénarios ``commercial`` / ``industriel``, formats
``full`` + ``onepage``).
"""
import copy
import json
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine import generate_devis_premium as legacy
from apps.ventes.quote_engine.ci.synthese import chiffres_cles, synthese_ci
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.figures import extract_figures
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

from ._moteur_fixtures import (
    donnees_legacy, etude_ci_au_kwc_servi, html_onepage,
)

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"


def _contrat(nom):
    return json.loads((_CONTRATS / nom).read_text(encoding="utf-8"))


ETUDE_CI = _contrat("etude_ci_preview.json")["exemple"]
ECONOMIE_CI = _contrat("economie_ci.json")["exemple"]

GABARITS = (
    ("commercial", c_sample, c_renderer, c_render),
    ("industriel", i_sample, i_renderer, i_render),
)

#: Les chiffres que la couverture du document complet et le une-page
#: partagent (clé ``data-figure`` → tolérance).
CLES = (("production_annuelle_kwh", Decimal("1")),
        ("economie_annuelle", Decimal("1")),
        ("payback_ans", Decimal("0.05")))


def _ci(data, mode, argent=True):
    data["mode_installation"] = mode
    data["etude"] = dict(data.get("etude") or {},
                         etude_ci=copy.deepcopy(ETUDE_CI))
    if argent:
        data["economie_ci"] = economie_ci_publique(copy.deepcopy(ECONOMIE_CI))
    else:
        data.pop("economie_ci", None)
    return etude_ci_au_kwc_servi(data)


def _onepage(mode, argent=True, **surcharges):
    data = _ci(donnees_legacy("deux", pdf_mode="onepage", **surcharges),
               mode, argent)
    return data, legacy.render_html_for(data)


def _valeurs(figures, cle):
    return [m.valeur for ident, ms in figures.items()
            if ident.split("@")[0] == cle for m in ms]


class OnePageCiLitSyntheseCi(SimpleTestCase):

    def test_parite_une_page_document_complet(self):
        for mode, sample, renderer, render in GABARITS:
            with self.subTest(mode=mode):
                complet = render.build_html(renderer._augment(
                    _ci(copy.deepcopy(sample.build()), mode)))
                data, une_page = _onepage(mode)
                f_complet = extract_figures(complet)
                f_une = extract_figures(une_page)
                attendus = chiffres_cles(synthese_ci(data))
                for cle, tol in CLES:
                    une = _valeurs(f_une, cle)
                    if cle == "production_annuelle_kwh":
                        source = attendus["production_kwh_an"]
                    elif cle == "economie_annuelle":
                        source = attendus["economie_annuelle_mad"]
                    else:
                        source = attendus["payback_ans"]
                    self.assertEqual(len(une), 1, (cle, une))
                    self.assertLessEqual(
                        abs(une[0] - Decimal(str(source))), tol, cle)
                    # Même chiffre sur le document complet quand il l'imprime
                    # (le commercial n'imprime pas la production).
                    for valeur in _valeurs(f_complet, cle):
                        self.assertLessEqual(abs(une[0] - valeur), tol, cle)

    def test_ni_production_par_ville_ni_economie_bt(self):
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                data, html = _onepage(mode)
                figures = extract_figures(html)
                self.assertNotIn(Decimal(str(data["prod_kwh"])),
                                 _valeurs(figures, "production_annuelle_kwh"))
                for cle in ("eco_s_ann", "eco_a_ann"):
                    self.assertNotIn(Decimal(str(data[cle])),
                                     _valeurs(figures, "economie_annuelle"))
                self.assertIn("conomies estim&#233;es / an", html)
                self.assertNotIn("(estimation)", html)

    def test_argent_absent_vignettes_omises_jamais_un_repli(self):
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                _data, html = _onepage(mode, argent=False)
                figures = extract_figures(html)
                self.assertEqual(_valeurs(figures, "economie_annuelle"), [])
                self.assertEqual(_valeurs(figures, "payback_ans"), [])
                self.assertNotIn("conomie annuelle", html)
                # La production reste : celle du moteur C&I.
                self.assertEqual(
                    _valeurs(figures, "production_annuelle_kwh"),
                    [Decimal(str(ETUDE_CI["bilan"]["production_kwh"]))])

    def test_etude_absente_production_omise(self):
        data = donnees_legacy("deux", pdf_mode="onepage",
                              mode_installation="industriel")
        html = legacy.render_html_for(data)
        figures = extract_figures(html)
        self.assertEqual(_valeurs(figures, "production_annuelle_kwh"), [])
        self.assertEqual(_valeurs(figures, "economie_annuelle"), [])

    def test_residentiel_inchange(self):
        """Le résidentiel garde ``prod_kwh`` et l'économie de sa branche."""
        data = donnees_legacy("deux", pdf_mode="onepage")
        html = html_onepage()
        figures = extract_figures(html)
        self.assertEqual(_valeurs(figures, "production_annuelle_kwh"),
                         [Decimal(str(int(data["prod_kwh"])))])
        self.assertNotIn("conomies estim&#233;es / an", html)
