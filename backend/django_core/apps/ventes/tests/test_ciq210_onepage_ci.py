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

from html import unescape

from django.test import SimpleTestCase, tag

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

    def test_postes_hors_total_sans_prix_par_kwc(self):
        """AMOT86 (D-ACI-2=a) — un poste « à chiffrer après la visite » hors
        total : le une-page n'imprime plus « Prix par kWc » (prix
        incomplet) ; sans poste hors total, la vignette reste."""
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                data = _ci(donnees_legacy("deux", pdf_mode="onepage"), mode)
                data["etude"]["etude_ci"]["composition"][
                    "a_chiffrer_visite"] = ["Structure C&I"]
                html = legacy.render_html_for(data)
                self.assertEqual(_valeurs(extract_figures(html), "prix_kwc"),
                                 [])
                self.assertNotIn("Prix par kWc", unescape(html))
                _data, html_ok = _onepage(mode)
                self.assertEqual(
                    len(_valeurs(extract_figures(html_ok), "prix_kwc")), 1)

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


def _onepage_reserve(mode, reserve, **surcharges):
    data = _ci(donnees_legacy("deux", pdf_mode="onepage", **surcharges), mode)
    data["etude"]["etude_ci"]["sous_reserve_visite"] = {
        "valeur": reserve, "motif": "surface disponible inconnue"}
    return data, legacy.render_html_for(data)


class Amot82OnePageSousReserve(SimpleTestCase):
    """AMOT82 (D-ACI-10=a) — une-page C&I « sous réserve de visite » : le
    bandeau de la couverture et la ligne de méthode sous les cartes ; sans
    réserve, ni l'un ni l'autre ; plus jamais « Prix ONEE en hausse »."""

    BANDEAU = "Estimation sous réserve de la visite technique"

    def test_sous_reserve_bandeau_et_methode(self):
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                data, html = _onepage_reserve(mode, True)
                methode = chiffres_cles(synthese_ci(data))["libelle_methode"]
                self.assertTrue(methode)
                self.assertIn(self.BANDEAU, unescape(html))
                self.assertIn(methode, unescape(html))

    def test_sans_reserve_ni_bandeau_ni_methode(self):
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                data, html = _onepage_reserve(mode, False)
                methode = chiffres_cles(synthese_ci(data))["libelle_methode"]
                self.assertNotIn(self.BANDEAU, unescape(html))
                self.assertNotIn(methode, unescape(html))
                self.assertNotIn("Prix ONEE en hausse", unescape(html))

    def test_traduit_en_anglais(self):
        _data, html = _onepage_reserve("industriel", True, langue_sortie="en")
        self.assertIn("Estimate subject to the technical site visit",
                      unescape(html))
        self.assertNotIn(self.BANDEAU, unescape(html))

    @tag("weasyprint")  # rendu PDF réel
    def test_une_seule_page(self):
        from weasyprint import HTML
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                _data, html = _onepage_reserve(mode, True)
                self.assertEqual(len(HTML(string=html).render().pages), 1)


def _onepage_hors_total(mode, postes=("Structure C&I", "Câble DC"),
                        **surcharges):
    data = _ci(donnees_legacy("deux", pdf_mode="onepage", **surcharges), mode)
    data["etude"]["etude_ci"]["composition"]["a_chiffrer_visite"] = list(
        postes)
    return data, legacy.render_html_for(data)


class Amot86OnePagePostesHorsTotal(SimpleTestCase):
    """AMOT86 (D-ACI-2=a, clause « ou la une-page C&I ») — des postes « à
    chiffrer après la visite » hors total : le bloc de totaux porte le titre
    SERVI de la couverture (``titre_investissement``), une ligne nomme les
    postes SANS montant et la vignette économie porte la légende « retour
    calculé sur le prix complet » ; sans poste, rien de tout cela."""

    PREFIXE = "À chiffrer après la visite technique (hors total) : "

    def test_titre_postes_et_legende(self):
        from apps.ventes.quote_engine.ci.couverture import (
            titre_investissement,
        )
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                data, html = _onepage_hors_total(mode)
                texte = unescape(html)
                syn = synthese_ci(data)
                titre = titre_investissement(
                    {"langue_sortie": "fr"}, syn,
                    (syn.get("argent") or {}).get("base"))
                self.assertIn("hors postes à chiffrer après la visite", titre)
                self.assertIn(titre, texte)
                self.assertNotIn("clé en main", texte)
                self.assertIn(self.PREFIXE + "Structure C&I, Câble DC",
                              texte)
                ligne = texte.split(self.PREFIXE, 1)[1].split("<", 1)[0]
                self.assertNotIn("MAD", ligne)
                self.assertIn("retour calculé sur le prix complet, après "
                              "la visite", texte)

    def test_sans_poste_rien(self):
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                _data, html = _onepage(mode)
                texte = unescape(html)
                self.assertNotIn("hors postes à chiffrer", texte)
                self.assertNotIn(self.PREFIXE, texte)
                self.assertNotIn("retour calculé sur le prix complet",
                                 texte)

    def test_traduit_en_anglais(self):
        _data, html = _onepage_hors_total("commercial", langue_sortie="en")
        texte = unescape(html)
        self.assertIn("excluding items to be priced after the site visit",
                      texte)
        self.assertIn("To be priced after the site visit (not in the "
                      "total): ", texte)
        self.assertIn("payback calculated on the full price", texte)
        self.assertNotIn(self.PREFIXE, texte)

    def test_telephone_mis_en_forme(self):
        """AMOT92 — le une-page C&I imprime le téléphone comme les
        couvertures (« +212 6 61 23 45 93 »), jamais les chiffres bruts."""
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                _data, html = _onepage(mode, client_phone="212661234593")
                self.assertIn("+212 6 61 23 45 93", unescape(html))
                self.assertNotIn("212661234593", html)

    @tag("weasyprint")  # rendu PDF réel
    def test_une_seule_page(self):
        from weasyprint import HTML
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                _data, html = _onepage_hors_total(mode)
                self.assertEqual(len(HTML(string=html).render().pages), 1)


class Amot84UnitesDuUnePageCi(SimpleTestCase):
    """AMOT84 — le une-page C&I anglais imprime « kWp » et « kWh/yr » (comme
    son titre) ; le français garde « kWc » / « kWh/an », octet pour octet,
    et le résidentiel est inchangé."""

    def _texte(self, html):
        import re
        texte = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
        texte = unescape(re.sub(r"<[^>]+>", " ", texte))
        return re.sub(r"\s+", " ", texte.replace(" ", " "))

    def test_anglais_kwp_kwh_yr(self):
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                data, html = _onepage(mode, langue_sortie="en")
                texte = self._texte(html)
                kwc = legacy.kwc_fr(float(data["puissance_kwc"]))
                # AMOT101 (D-ACI-21=a) — format anglais : « 5.68 kWp ».
                self.assertIn(f"{kwc.replace(',', '.')} kWp", texte)
                self.assertNotIn(f"{kwc} kWc", texte)
                self.assertNotIn(f"{kwc} kWp", texte)
                self.assertIn("MAD/kWp", texte)
                self.assertNotIn("MAD/kWc", texte)
                self.assertIn(" kWh/yr", texte)
                self.assertNotIn(" kWh/an", texte)

    def test_francais_inchange(self):
        for mode, *_ in GABARITS:
            with self.subTest(mode=mode):
                data, html = _onepage(mode)
                texte = self._texte(html)
                kwc = legacy.kwc_fr(float(data["puissance_kwc"]))
                self.assertIn(f"{kwc} kWc", texte)
                self.assertIn("MAD/kWc", texte)
                self.assertIn(" kWh/an", texte)
                self.assertNotIn("kWp", texte)
