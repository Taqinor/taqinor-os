"""CIQ330 — contenu par catégorie commerciale : UNE table trilingue
(``quote_engine/ci/categories.py``), servie dans ``synthese_ci['categorie']``
et rendue par ``commercial/categories.category_block``.

Tests sur le ``category_block`` RÉEL, alimenté par la synthèse réelle
(``synthese_ci``) d'un devis commercial — avec la sortie du moteur C&I et le
bloc ``economie_ci`` des contrats partagés pour la revente BT / MT.
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine.ci import categories as ci_categories
from apps.ventes.quote_engine.ci.mentions import TEXTES_82_21
from apps.ventes.quote_engine.ci.synthese import synthese_ci
from apps.ventes.quote_engine.commercial import categories
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"


def _contrat(nom):
    return json.loads((_CONTRATS / nom).read_text(encoding="utf-8"))


ECONOMIE_CI = _contrat("economie_ci.json")
ETUDE_CI = _contrat("etude_ci_preview.json")

INTERDITS = ("OTA", "injectable", "valorisable", "prévisible",
             "quasi-totalité", "peu d'export", "alignement idéal")


def _data(categorie, reponses, *, tension=None, economie=None):
    data = copy.deepcopy(c_sample.build(categorie))
    # CIQ129 — les réponses vivent dans l'entrée v2 du moteur C&I
    # (``rythme.reponses_categorie``), jamais à plat dans l'étude.
    etude = dict(data["etude"])
    etude["rythme"] = {"categorie_commerciale": categorie,
                       "reponses_categorie": dict(reponses)}
    if tension:
        etude["tension_raccordement"] = tension
    data["etude"] = etude
    if economie is not None:
        data["economie_ci"] = economie_ci_publique(copy.deepcopy(economie))
    return data


def _bloc(data):
    synthese = synthese_ci(data)
    html = categories.category_block(
        data["etude"].get("categorie_commerciale"), data["etude"],
        {}, str,
        categorie=synthese["categorie"])
    return synthese, html


class CategoriesCommerciales(SimpleTestCase):

    def test_boulangerie_sans_cuisson_nocturne(self):
        _s, html = _bloc(_data("boulangerie", {
            "four": "electrique", "cuisson_nocturne": False}))
        self.assertIn("Four électrique", html)
        self.assertNotIn("Four electrique", html)
        titre = html[html.index('c2b-h">'):html.index("</div>")]
        self.assertNotIn("nocturne", titre)

    def test_boulangerie_cuisson_nocturne_declaree(self):
        _s, html = _bloc(_data("boulangerie", {
            "four": "gaz", "cuisson_nocturne": True}))
        self.assertIn("Transparence sur la cuisson nocturne", html)
        self.assertIn("Four au gaz", html)

    def test_restaurant_soir_gaz(self):
        _s, html = _bloc(_data("restaurant", {
            "horaires": "soir", "cuisson": "gaz", "chambres_froides": 2}))
        self.assertIn("service du soir", html)
        self.assertIn("cuisson au gaz", html)
        self.assertIn("2 chambres froides", html)

    def test_ecole_bt_fermee_l_ete(self):
        data = _data("ecole", {"effectif": 300, "fermeture_estivale": True},
                     economie=ECONOMIE_CI["exemple"])
        synthese, html = _bloc(data)
        self.assertEqual(synthese["argent"]["revente"]["statut"], "absente_bt")
        self.assertIn("revente n'est pas ouverte en basse tension", html)
        self.assertIn("fermée l'été", html)
        for mot in INTERDITS:
            self.assertNotIn(mot, html)
        page = c_render.build_html(c_renderer._augment(data))
        for mot in ("injectable", "valorisable", "prévisible"):
            self.assertNotIn(mot, page)

    def test_ecole_bt_sans_economie_lue_sur_la_tension(self):
        _s, html = _bloc(_data("ecole", {"fermeture_estivale": True},
                               tension="bt"))
        self.assertIn("basse tension", html)
        self.assertNotIn("injectable", html)

    def test_ecole_mt_mention_sourcee(self):
        data = _data("ecole", {"fermeture_estivale": True}, tension="mt",
                     economie=ECONOMIE_CI["exemple_industriel_mt"])
        synthese, html = _bloc(data)
        self.assertIn(TEXTES_82_21["fr"], html)
        ligne = synthese["categorie"]["bloc"]["lignes"][-1]
        self.assertEqual(ligne["textes"], TEXTES_82_21)

    def test_ecole_ouverte_l_ete_aucune_phrase_d_injection(self):
        _s, html = _bloc(_data("ecole", {"fermeture_estivale": False},
                               tension="bt"))
        self.assertIn("Ouverte l'été", html)
        self.assertNotIn("Surplus", html)

    def test_bureau_sans_promesse(self):
        synthese, html = _bloc(_data("bureau", {"effectif": 40,
                                                "clim": True}))
        self.assertIn("40 postes, climatisation centralisée", html)
        for mot in INTERDITS:
            self.assertNotIn(mot, html)
        self.assertNotIn("peu d'export", synthese["categorie"]["accroche"])

    def test_aucune_occurrence_ota_ni_promesse_toutes_categories(self):
        for cle in ci_categories.CATEGORIES:
            with self.subTest(categorie=cle):
                synthese, html = _bloc(_data(cle, {}))
                accroche = synthese["categorie"]["accroche"]
                for mot in INTERDITS:
                    self.assertNotIn(mot, html)
                    self.assertNotIn(mot, accroche)

    def test_autre_commerce_libelle(self):
        synthese, _html = _bloc(_data("autre", {}))
        self.assertEqual(synthese["categorie"]["libelle"], "Autre commerce")

    def test_trilingue(self):
        data = _data("hotel", {"chambres": 12, "piscine": True})
        data["langue_sortie"] = "en"
        categorie = synthese_ci(data)["categorie"]
        self.assertEqual(categorie["bloc"]["titre"], "Your hotel")
        ligne = categorie["bloc"]["lignes"][0]["textes"]
        self.assertEqual(set(ligne), {"fr", "en", "ar"})
        self.assertIn("12 rooms", ligne["en"])

    def test_categorie_servie_en_commercial_seulement(self):
        data = _data("hotel", {})
        self.assertIn("categorie", synthese_ci(data))
        data["mode_installation"] = "industriel"
        self.assertNotIn("categorie", synthese_ci(data))

    def test_couverture_lit_l_accroche_servie(self):
        data = _data("bureau", {"effectif": 40})
        page = c_render.build_html(c_renderer._augment(data))
        self.assertIn(synthese_ci(data)["categorie"]["accroche"], page)
