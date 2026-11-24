"""CIQ307 — les gabarits commercial et industriel lisent ``synthese_ci`` :
une seule source pour la couverture et /proposition, ancrée pour la parité,
avec le bandeau « Devis préliminaire — les prix pourront être ajustés
après la visite technique » (décision fondateur 26/10/2026 : sur TOUT
document C&I).

Tests PURS (``SimpleTestCase``) : rendu HTML RÉEL des deux gabarits sur leurs
fixtures, enrichies de la sortie du moteur C&I (contrat
``etude_ci_preview.json``) et du bloc PUBLIC ``economie_ci`` (contrat
``economie_ci.json``). La parité PDF ↔ /proposition sur un devis réel est
dans ``test_figures_parite`` (scénarios ``commercial`` / ``industriel``).
"""
import copy
import json
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine.ci.couverture import (
    BANDEAU_RESERVE, ans, retour_dixieme)
from apps.ventes.quote_engine.ci.synthese import chiffres_cles, synthese_ci
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.figures import extract_figures
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

from ._moteur_fixtures import etude_ci_au_kwc_servi

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"


def _contrat(nom):
    return json.loads((_CONTRATS / nom).read_text(encoding="utf-8"))


ETUDE_CI = _contrat("etude_ci_preview.json")
ECONOMIE_CI = _contrat("economie_ci.json")

GABARITS = (
    ("commercial", c_sample, c_renderer, c_render, 3),
    ("industriel", i_sample, i_renderer, i_render, 4),
)


def _data(sample, *, methode="declare", reserve=False, argent=True):
    data = copy.deepcopy(sample.build())
    etude_ci = copy.deepcopy(ETUDE_CI["exemple"])
    etude_ci["profil_charge"]["methode"] = methode
    etude_ci["sous_reserve_visite"] = {
        "valeur": reserve,
        "motif": "Toiture à relever à la visite" if reserve else None}
    data["etude"] = dict(data.get("etude") or {}, etude_ci=etude_ci)
    if argent:
        data["economie_ci"] = economie_ci_publique(
            copy.deepcopy(ECONOMIE_CI["exemple"]))
    return etude_ci_au_kwc_servi(data)


def _valeur(figures, cle):
    mesures = [m for ident, ms in figures.items()
               if ident.split("@")[0] == cle for m in ms]
    return mesures[0].valeur if mesures else None


class _ReglesCourantes(SimpleTestCase):
    """Le drapeau « règles d'avant le niveau 3 » est une ``ContextVar`` que
    ``poser_regles_origine`` pose sans la retirer : un test antérieur du même
    processus qui rend un devis ancien la laissait vraie (« 4 » au lieu de
    « 4,0 », file de merge #1132). Chaque test part des règles courantes."""

    def setUp(self):
        super().setUp()
        from apps.ventes.quote_engine.montants import poser_regles_origine
        poser_regles_origine(False)


class GabaritsLisentSyntheseCi(_ReglesCourantes):

    def test_tuiles_ancrees_sur_la_synthese(self):
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                data = _data(sample)
                html = render.build_html(renderer._augment(data))
                synthese = synthese_ci(data)
                attendus = dict(chiffres_cles(synthese))
                # CPDF7 — le retour imprimé est celui du flux servi, au
                # dixième (« 2,5 »), plus l'année entière servie (« 3 »).
                attendus["payback_ans"] = retour_dixieme(
                    synthese.get("argent"), attendus["payback_ans"])
                self.assertNotEqual(attendus["payback_ans"], 3)
                figures = extract_figures(html)
                for cle, source, tolerance in (
                        ("autoconsommation_pct", "taux_autoconso_pct", 1),
                        ("couverture_pct", "taux_couverture_pct", 1),
                        ("economie_annuelle", "economie_annuelle_mad", 1),
                        ("payback_ans", "payback_ans", Decimal("0.05"))):
                    valeur = _valeur(figures, cle)
                    self.assertIsNotNone(valeur, cle)
                    self.assertLessEqual(
                        abs(valeur - Decimal(str(attendus[source]))),
                        Decimal(str(tolerance)), cle)
                self.assertIn("Économies estimées / an (HT)", html)
                self.assertIn("Retour estimé", html)
                self.assertNotIn("Économies / an<", html)

    def test_production_industrielle_celle_du_moteur(self):
        data = _data(i_sample)
        html = i_render.build_html(i_renderer._augment(data))
        production = _valeur(extract_figures(html), "production_annuelle_kwh")
        self.assertEqual(production, Decimal(str(
            ETUDE_CI["exemple"]["bilan"]["production_kwh"])))
        self.assertNotEqual(production, Decimal(str(data["prod_kwh"])))

    def test_profil_type_dit_estimation(self):
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                html = render.build_html(renderer._augment(
                    _data(sample, methode="archetype")))
                self.assertIn("profil type de votre activité — estimation",
                              html)

    def test_t4_u2_019_horaires_supposes_jamais_dits_declares(self):
        """T4-U2-019 — régime 2×8 sans heure ni jours : 6 h et lundi-samedi
        SUPPOSÉS (alertes du moteur). Au niveau 15 la couverture et la
        une-page disent le profil type ; dessous, le document d'hier."""
        from apps.ventes.quote_engine.ci.onepage import lire_synthese
        supposes = [{"code": "heure_debut_supposee", "niveau": "info"},
                    {"code": "jours_ouverts_supposes", "niveau": "info"}]
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                declare = _data(sample)
                suppose = _data(sample)
                suppose["etude"]["etude_ci"]["alertes"] = supposes
                hier = render.build_html(renderer._augment(suppose))
                self.assertEqual(hier, render.build_html(renderer._augment(declare)))
                self.assertIn("horaires déclarés", hier)
                niveau_15 = render.build_html(renderer._augment(
                    dict(suppose, regles_pose_reelle=True)))
                self.assertIn("profil type de votre activité — estimation", niveau_15)
                self.assertNotIn("horaires déclarés", niveau_15)
                self.assertEqual(lire_synthese(dict(suppose, regles_pose_reelle=True),
                                               nom)[1]["methode"], "archetype_estimation")
                # Horaires réellement déclarés : la phrase reste au niveau 15.
                self.assertIn("horaires déclarés", render.build_html(renderer._augment(
                    dict(declare, regles_pose_reelle=True))))

    def test_sous_reserve_bandeau_et_a_confirmer(self):
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                html = render.build_html(renderer._augment(
                    _data(sample, reserve=True)))
                self.assertIn(BANDEAU_RESERVE, html)
                # Décision fondateur 26/10/2026 — le bandeau garde son
                # titre, jamais la liste interne « À confirmer : … ».
                self.assertNotIn("Toiture à relever à la visite", html)
                self.assertNotIn("À confirmer", html)
                ferme = render.build_html(renderer._augment(_data(sample)))
                # Décision fondateur 26/10/2026 — le devis C&I entier est
                # préliminaire : le bandeau est imprimé même sans réserve.
                self.assertIn(BANDEAU_RESERVE, ferme)
                self.assertTrue(BANDEAU_RESERVE.startswith(
                    "Devis préliminaire — les prix pourront être ajustés"))

    def test_devis_final_ni_bandeau_ni_etape_visite(self):
        """Fondateur 19/11/2026 — « Devis final » (visite faite) : plus de
        « Devis préliminaire », plus d'étape « Visite technique » ; la
        synthèse servie le dit (clé additive), sans la case rien ne bouge."""
        from html import unescape
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                d = _data(sample, reserve=True)
                self.assertNotIn("devis_final", synthese_ci(d))
                hier = unescape(render.build_html(renderer._augment(
                    _data(sample, reserve=True))))
                d["devis_final"] = True
                html = unescape(render.build_html(renderer._augment(d)))
                self.assertNotIn("Devis préliminaire", html)
                self.assertNotIn("Visite technique de votre site", html)
                # Les étapes restantes, là où le gabarit imprime le bloc.
                for etape in ("Validation de l'offre définitive",
                              "Pose et mise en service"):
                    self.assertEqual(etape in html, etape in hier, etape)
                servie = synthese_ci(d)
                self.assertIs(servie["devis_final"], True)
                self.assertNotIn("visite", [
                    h.get("cle") for h in servie.get("hypotheses") or []])

    def test_devis_final_garde_les_postes_hors_total(self):
        """Les postes « à chiffrer » ne sont pas dans le total : leur ligne
        reste, seule ; sans poste, plus de bandeau du tout."""
        from unittest import mock

        from apps.ventes.quote_engine.ci import couverture
        d = {"devis_final": True}
        self.assertEqual(couverture.bandeau_reserve(d, "com", "c1c"), "")
        with mock.patch.object(couverture, "ligne_postes_hors_total",
                               return_value="À chiffrer : câble DC"):
            bandeau = couverture.bandeau_reserve(d, "com", "c1c")
        self.assertIn("À chiffrer : câble DC", bandeau)
        self.assertNotIn("Devis préliminaire", bandeau)

    def test_sans_argent_tuiles_omises_jamais_zero(self):
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                d = renderer._augment(_data(sample, argent=False))
                html = render.build_html(d)
                self.assertNotIn("Économies estimées", html)
                self.assertNotIn("Retour estimé", html)

    def test_batterie_servie_plus_de_non_promise(self):
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                data = _data(sample, argent=False)
                data["option_servie"] = "avec"
                html = render.build_html(renderer._augment(data))
                self.assertNotIn("non promise", html)
                self.assertIn("non chiffrée", html)

    def test_nombre_de_pages_inchange(self):
        for nom, sample, renderer, render, pages in GABARITS:
            for kwargs in ({}, {"reserve": True}, {"argent": False},
                           {"methode": "archetype", "reserve": True}):
                with self.subTest(gabarit=nom, **kwargs):
                    html = render.build_html(renderer._augment(
                        _data(sample, **kwargs)))
                    self.assertEqual(html.count('class="page"'), pages)


class Cpdf7RetourAuDixieme(_ReglesCourantes):
    """CPDF7 — un retour au dixième, au même format partout : interpolé
    dans l'année où le cumul SERVI passe à zéro ; virgule en FR / AR, point
    en EN ; sans flux, la valeur servie telle quelle."""

    #: Cumul −221 656 fin d'année 3, +6 557 fin d'année 4 (flux 228 213) :
    #: 3 + 221 656 / 228 213 = 3,97 ⇒ « 4,0 ».
    ARGENT = {"base": "deux", "flux_ht": {"flux": [
        {"annee": 0, "flux_mad": -906295.0, "cumul_mad": -906295.0},
        {"annee": 1, "flux_mad": 228213.0, "cumul_mad": -678082.0},
        {"annee": 2, "flux_mad": 228213.0, "cumul_mad": -449869.0},
        {"annee": 3, "flux_mad": 228213.0, "cumul_mad": -221656.0},
        {"annee": 4, "flux_mad": 228213.0, "cumul_mad": 6557.0}]}}

    def test_interpolation_epinglee(self):
        retour = retour_dixieme(self.ARGENT, 4)
        self.assertEqual(retour, 4.0)
        self.assertEqual(ans(retour), "4,0")
        self.assertEqual(ans(2.3), "2,3")

    def test_format_anglais(self):
        from apps.ventes.quote_engine.montants import format_langue
        with format_langue({"mode_installation": "commercial",
                            "langue_sortie": "en"}):
            self.assertEqual(ans(2.3), "2.3")

    def test_sans_flux_valeur_servie(self):
        self.assertEqual(retour_dixieme({"base": "ht"}, 3), 3)
        self.assertEqual(retour_dixieme(None, 3), 3)
        self.assertIsNone(retour_dixieme(self.ARGENT, None))
        base_ttc = dict(self.ARGENT, base="ttc")
        self.assertEqual(retour_dixieme(base_ttc, 4), 4)

    def test_couverture_et_une_page_meme_retour(self):
        from apps.ventes.quote_engine.ci.onepage import lire_synthese
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                data = _data(sample)
                html = render.build_html(renderer._augment(data))
                _synthese, chiffres = lire_synthese(data, nom)
                self.assertEqual(chiffres["payback_ans"], 2.5)
                self.assertIn("2,5", html.split('class="page"')[1])
