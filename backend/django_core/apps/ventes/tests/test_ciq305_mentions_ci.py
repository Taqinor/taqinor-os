"""CIQ305 — Mentions et hypothèses C&I : UNE table (``quote_engine/ci/
mentions.py``), sourcée et trilingue, servie à ``synthese_ci['hypotheses']``
et aux gabarits PDF commercial / industriel.

Tests PURS (``SimpleTestCase``) + rendu HTML réel des deux gabarits.
"""
import copy
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.quote_engine.ci.mentions import (
    TEXTES_POINTE_AVEC_NON_CHIFFREE,
    TEXTES_POINTE_SANS,
    mentions_ci,
    valeur_option_avec,
)
from apps.ventes.quote_engine.ci.synthese import synthese_ci
from apps.ventes.quote_engine.commercial import render as com_render
from apps.ventes.quote_engine.commercial import renderer as com_renderer
from apps.ventes.quote_engine.commercial import sample_data as com_sample
from apps.ventes.quote_engine.constants_82_21 import (
    MENTION_82_21,
    MENTION_ART13,
    MENTION_BT,
)
from apps.ventes.quote_engine.industriel import render as ind_render
from apps.ventes.quote_engine.industriel import renderer as ind_renderer
from apps.ventes.quote_engine.industriel import sample_data as ind_sample
from apps.ventes.tests.test_ciq303_synthese_ci_coeur import _data, _etude_ci

QUOTE_ENGINE = Path(__file__).resolve().parents[1] / "quote_engine"
COPIES_INTERDITES = ("net des frais réseau", "plafond en révision",
                     "heures les plus chères", "puissance souscrite lissée")


def _par_cle(entrees):
    return {e["cle"]: e for e in entrees}


def _etude(tension):
    etude = _etude_ci()
    etude["entrees_resolues"]["tension"]["valeur"] = tension
    return etude


class TestTableMentions(SimpleTestCase):

    def test_forme_trilingue_sourcee(self):
        for e in synthese_ci(_data(_etude("bt")))["hypotheses"]:
            self.assertEqual(set(e), {"cle", "textes", "source", "date"})
            self.assertEqual(set(e["textes"]), {"fr", "en", "ar"})
            self.assertTrue(all(e["textes"].values()))
            self.assertTrue(e["source"])

    def test_bt_ligne_bt_aucune_revente(self):
        h = _par_cle(mentions_ci(_data(_etude("bt"))))
        self.assertEqual(h["revente_bt"]["textes"]["fr"], MENTION_BT)
        self.assertNotIn("revente", h)
        self.assertEqual(h["contribution_art13"]["textes"]["fr"],
                         MENTION_ART13)
        self.assertNotIn("puissance_souscrite", h)

    def test_mt_avec_revente_mention_8221_lue(self):
        data = _data(_etude("mt"), mode_installation="industriel",
                     economie_ci={"statut": "calcule",
                                  "revente": {"statut": "calculee"}})
        h = _par_cle(mentions_ci(data))
        self.assertEqual(h["revente"]["textes"]["fr"], MENTION_82_21)
        self.assertNotIn("revente_bt", h)
        # Convention 2 : site MT ⇒ la puissance souscrite ne change pas.
        self.assertIn("puissance souscrite",
                      h["puissance_souscrite"]["textes"]["fr"])

    def test_mt_sans_revente_aucune_ligne_de_revente(self):
        h = _par_cle(mentions_ci(_data(_etude("mt"))))
        self.assertNotIn("revente", h)
        self.assertNotIn("revente_bt", h)

    def test_puissance_souscrite_declaree_en_bt(self):
        etude = _etude("bt")
        etude["entrees_resolues"]["puissance_souscrite_kva"] = {
            "valeur": 60, "provenance": None}
        self.assertIn("puissance_souscrite",
                      _par_cle(mentions_ci(_data(etude))))

    def test_note_pointe_selon_la_composition(self):
        sans = _par_cle(mentions_ci(_data(_etude("bt"))))["pointe"]
        self.assertEqual(sans["textes"], TEXTES_POINTE_SANS)
        avec = _par_cle(mentions_ci(_data(
            _etude("bt"), option_servie="avec")))["pointe"]
        self.assertEqual(avec["textes"], TEXTES_POINTE_AVEC_NON_CHIFFREE)
        self.assertNotIn("non promise", avec["textes"]["fr"])
        # Batterie différée (onduleur hybride sans batterie) : phrase « sans ».
        differee = _par_cle(mentions_ci(_data(
            _etude("bt"), option_servie="avec",
            avec_batterie_differee=True)))["pointe"]
        self.assertEqual(differee["textes"], TEXTES_POINTE_SANS)
        # Fondateur 27/10/2026 — un fait, jamais « non promise » ; l'offre
        # réseau d'un devis à deux options renvoie à l'option « avec ».
        self.assertEqual(TEXTES_POINTE_SANS["fr"],
                         "Le soir et la nuit, votre consommation reste fournie par le réseau.")
        # CPDF9 — sans part du soir servie par l'étude (aucun
        # ``option_avec``), la phrase perd sa seconde moitié.
        deux = _par_cle(mentions_ci(_data(
            _etude("bt"), option_servie="sans",
            option_batterie={"totaux": {}, "valeur_chiffree": None})))["pointe"]
        self.assertEqual(deux["textes"], TEXTES_POINTE_SANS)
        for textes in (sans["textes"], deux["textes"]):
            self.assertNotIn("non promise", textes["fr"])

    @staticmethod
    def _deux_options(restitue_kwh_an, besoin_nocturne_kwh=100):
        etude = _etude("bt")
        etude["option_avec"] = {
            "economie_annuelle_mad": 95767.0,
            "batterie": {"capacite_utile_kwh": 92.2,
                         "besoin_nocturne_kwh": besoin_nocturne_kwh},
            "bilan": {"batterie": {"capacite_utile_kwh": 92.2,
                                   "restitue_kwh_an": restitue_kwh_an}}}
        return _data(etude, option_servie="sans", option_batterie={
            "totaux": {"ht_net": 394250}, "valeur_chiffree": None})

    def test_cpdf9_phrase_soir_selon_la_part_couverte(self):
        # 100 kWh/jour hors production × 365 = 36 500 kWh/an.
        couvre = _par_cle(mentions_ci(self._deux_options(33000)))["pointe"]
        self.assertEqual(couvre["textes"]["fr"], (
            "Le soir et la nuit, votre consommation reste fournie par le "
            "réseau ; l'option avec batterie la couvre."))
        partie = _par_cle(mentions_ci(self._deux_options(13505)))["pointe"]
        self.assertEqual(partie["textes"]["fr"], (
            "Le soir et la nuit, votre consommation reste fournie par le "
            "réseau ; l'option avec batterie en couvre 37\u00a0%."))
        self.assertIn("covers 37% of it", partie["textes"]["en"])
        self.assertIn("37", partie["textes"]["ar"])
        self.assertNotIn("la couvre", partie["textes"]["fr"])
        # Besoin du soir non servi : la phrase sans sa seconde moitié.
        absent = _par_cle(mentions_ci(self._deux_options(
            31000, besoin_nocturne_kwh=None)))["pointe"]
        self.assertEqual(absent["textes"], TEXTES_POINTE_SANS)
        # Besoin du soir non servi (devis rafraîchi) : aucun repli sur les
        # taux de couverture globaux (critique Fable 28/10) — la phrase seule.
        data = self._deux_options(31000, besoin_nocturne_kwh=None)
        data["etude"]["etude_ci"].setdefault("bilan", {})[
            "taux_couverture"] = 0.52
        data["etude"]["etude_ci"]["option_avec"].setdefault("bilan", {})[
            "taux_couverture"] = 0.93
        repli = _par_cle(mentions_ci(data))["pointe"]
        self.assertEqual(repli["textes"], TEXTES_POINTE_SANS)

    def test_cpdf2_retour_option_avec_servi_jamais_recalcule(self):
        data = self._deux_options(31000)
        data["etude"]["etude_ci"]["option_avec"]["retour_simple_ans"] = 22.1
        valeur = valeur_option_avec(data)
        # Quotient HT ÷ économie = 4,1 ans : jamais imprimé.
        self.assertEqual(valeur["retour_simple_ans"], 22.1)
        del data["etude"]["etude_ci"]["option_avec"]["retour_simple_ans"]
        self.assertIsNone(valeur_option_avec(data)["retour_simple_ans"])

    def test_tarif_utilise_et_sa_source(self):
        tarif = {"origine": "grille_officielle", "contrat": "bt_patente",
                 "mention": "Grille ONEE, repli",
                 "tarifs_par_poste": [{"releve_le": "2026-10-03"}]}
        h = _par_cle(mentions_ci(_data(
            _etude("bt"), economie_ci={"tarif": tarif})))
        # AMOT88 — le texte client dit « tarif officiel ONEE publié »,
        # jamais « repli » (le mot reste dans la source, interne).
        self.assertEqual(h["tarif"]["textes"]["fr"],
                         "Prix du kWh : tarif officiel ONEE publié, en "
                         "attendant la lecture de votre facture.")
        self.assertNotIn("repli", " ".join(h["tarif"]["textes"].values()))
        self.assertEqual(h["tarif"]["source"], "Grille ONEE, repli")
        self.assertEqual(h["tarif"]["date"], "2026-10-03")
        self.assertNotIn("tarif", _par_cle(mentions_ci(_data(_etude("bt")))))

    def test_visite_si_sous_reserve(self):
        etude = _etude("bt")
        etude["sous_reserve_visite"] = {"valeur": True, "motif": None}
        h = _par_cle(synthese_ci(_data(etude))["hypotheses"])
        self.assertIn("visite technique", h["visite"]["textes"]["fr"])
        self.assertNotIn("visite", _par_cle(
            synthese_ci(_data(_etude("bt")))["hypotheses"]))


class TestGabaritsLisentLaTable(SimpleTestCase):

    def _avec_injection(self, sample):
        # CIQ129 — l'injection est celle du moteur C&I (``economie_ci.
        # revente`` calculée, contrat partagé), plus une clé d'étude écran.
        base = copy.deepcopy(sample.build())
        base["economie_ci"] = ind_sample.economie_ci()
        return base

    def test_rendu_reel_des_deux_gabarits(self):
        html_com = com_render.build_html(
            com_renderer._augment(self._avec_injection(com_sample)))
        html_ind = ind_render.build_html(
            ind_renderer._augment(self._avec_injection(ind_sample)))
        for html in (html_com, html_ind):
            self.assertIn(MENTION_82_21, html)
            for copie in COPIES_INTERDITES:
                self.assertNotIn(copie, html)

    def test_aucune_copie_8221_dans_le_moteur(self):
        for chemin in QUOTE_ENGINE.rglob("*.py"):
            if chemin.name == "mentions.py":
                continue
            source = chemin.read_text(encoding="utf-8")
            for copie in COPIES_INTERDITES[:2]:
                self.assertNotIn(copie, source, msg=str(chemin))
