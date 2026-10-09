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

    def test_tarif_utilise_et_sa_source(self):
        tarif = {"origine": "grille_officielle", "contrat": "bt_patente",
                 "mention": "Grille ONEE, repli",
                 "tarifs_par_poste": [{"releve_le": "2026-10-03"}]}
        h = _par_cle(mentions_ci(_data(
            _etude("bt"), economie_ci={"tarif": tarif})))
        self.assertIn("repli", h["tarif"]["textes"]["fr"])
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
        # AMOT40 — le PDF imprime les mentions SERVIES par ``revente_ci`` (et
        # non plus une mention 82-21 fixe) : la revente porte ici la liste
        # que le moteur sert réellement (``economie_ci.revente_ci``), pas les
        # libellés abrégés de l'exemple du contrat.
        from apps.ventes import economie_ci as eco
        base["economie_ci"]["revente"]["mentions"] = [
            MENTION_82_21, eco.MENTION_NON_GARANTI,
            eco.MENTION_SECOND_COMPTEUR, eco.MENTION_TSS,
            eco.MENTION_TARIF_ARRETE, MENTION_ART13]
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
