"""CIQ304 — ``synthese_ci(data)`` (2/2) : le bloc ``argent`` recopie le bloc
PUBLIC ``economie_ci`` tel quel (contrat CIQ3), sans calcul ; base HT / TTC
dite ; VAN, LCOE et sensibilités en industriel seulement (D-CIQ-10) ; un seul
payback ; sans bloc moteur, ``argent`` est ABSENT et ``omissions`` dit ce que
le client peut fournir.

Tests PURS (``SimpleTestCase``) sur les exemples du contrat partagé
``contract_samples/economie_ci.json``.
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.economie_ci import (
    BASE_DEUX,
    BASE_HT,
    BASE_TTC,
    MOTIF_BASE_HT,
    MOTIF_BASE_TTC,
    economie_ci_publique,
)
from apps.ventes.quote_engine.ci.synthese import (
    MOTIF_ARGENT_BT,
    MOTIF_ARGENT_MT,
    synthese_ci,
)
from apps.ventes.tests.test_ciq303_synthese_ci_coeur import _data, _etude_ci

CONTRAT = json.loads(
    (Path(__file__).resolve().parents[1] / "contract_samples"
     / "economie_ci.json").read_text(encoding="utf-8"))


def _economie(nom="exemple"):
    return copy.deepcopy(CONTRAT[nom])


def _cles_recursives(valeur):
    if isinstance(valeur, dict):
        for k, v in valeur.items():
            yield k
            yield from _cles_recursives(v)
    elif isinstance(valeur, list):
        for v in valeur:
            yield from _cles_recursives(v)


class TestSyntheseCiArgent(SimpleTestCase):

    def _industriel(self, economie):
        return synthese_ci(_data(_etude_ci(), mode_installation="industriel",
                                 economie_ci=economie))

    def test_bloc_complet_recopie_au_centime_en_industriel(self):
        economie = _economie()
        s = self._industriel(economie)
        # Égal au bloc PUBLIC, clé par clé, valeur par valeur : aucun calcul.
        self.assertEqual(s["argent"], economie_ci_publique(economie))
        self.assertEqual(s["argent"]["economie_annee1"]["total_mad"],
                         economie["economie_annee1"]["total_mad"])
        self.assertEqual(s["argent"]["flux_ht"]["flux"],
                         economie["flux_ht"]["flux"])
        self.assertNotIn("vue_interne", s["argent"])
        self.assertNotIn("alertes_internes", s["argent"])
        self.assertNotIn("argent", {o["bloc"] for o in s["omissions"]})

    def test_industriel_garde_van_lcoe_et_sensibilites(self):
        s = self._industriel(_economie())
        self.assertIn("lcoe_mad_kwh", s["argent"]["indicateurs"])
        self.assertIn("van_mad", s["argent"]["indicateurs"])
        self.assertIn("sensibilites", s["argent"])

    def test_commercial_ni_van_ni_lcoe_ni_sensibilites(self):
        economie = _economie()
        s = synthese_ci(_data(_etude_ci(), economie_ci=economie))
        cles = set(_cles_recursives(s["argent"]))
        for interdite in ("van_mad", "van_motif", "lcoe_mad_kwh",
                          "lcoe_actualise", "retour_actualise_ans",
                          "sensibilites"):
            self.assertNotIn(interdite, cles)
        omissions = [o.get("cle") for o in s["argent"]["omissions"]]
        self.assertNotIn("van_mad", omissions)
        # Le reste est recopié tel quel.
        self.assertEqual(s["argent"]["economie_annee1"],
                         economie["economie_annee1"])
        self.assertEqual(s["argent"]["indicateurs"]["tri_pct"],
                         economie["indicateurs"]["tri_pct"])
        # L'entrée n'est jamais modifiée (fonction pure).
        self.assertEqual(economie, _economie())

    def test_base_ht_ttc_inconnue_et_motif(self):
        for base, motif in ((BASE_HT, MOTIF_BASE_HT),
                            (BASE_TTC, MOTIF_BASE_TTC)):
            economie = _economie()
            economie["base"], economie["motif_base"] = base, motif
            s = self._industriel(economie)
            self.assertEqual(s["argent"]["base"], base)
            self.assertEqual(s["argent"]["motif_base"], motif)
        s = self._industriel(_economie())
        self.assertEqual(s["argent"]["base"], BASE_DEUX)
        self.assertEqual(s["argent"]["motif_base"],
                         CONTRAT["exemple"]["motif_base"])

    def test_bloc_absent_ou_omis_motif_bt(self):
        for economie in (None, _economie("exemple_omis")):
            s = synthese_ci(_data(_etude_ci(), economie_ci=economie))
            self.assertNotIn("argent", s)
            self.assertIn({"bloc": "argent", "motif": MOTIF_ARGENT_BT},
                          s["omissions"])

    def test_bloc_absent_motif_mt(self):
        etude = _etude_ci()
        etude["entrees_resolues"]["tension"]["valeur"] = "mt"
        s = synthese_ci(_data(etude, mode_installation="industriel"))
        self.assertNotIn("argent", s)
        self.assertIn({"bloc": "argent", "motif": MOTIF_ARGENT_MT},
                      s["omissions"])
        for o in s["omissions"]:
            self.assertNotIn("répartition horaire", o["motif"])

    def test_un_seul_payback_celui_du_flux(self):
        for segment in ("commercial", "industriel"):
            s = synthese_ci(_data(_etude_ci(), mode_installation=segment,
                                  economie_ci=_economie()))
            cles = list(_cles_recursives(s))
            self.assertNotIn("payback", cles)
            self.assertNotIn("roi", cles)
            argent = s["argent"]
            self.assertEqual(argent["indicateurs"]["retour_ans"],
                             argent["flux_ht"]["retour_ans"])
            if segment == "commercial":
                self.assertNotIn("retour_actualise_ans", cles)

    def test_aucun_prix_achat(self):
        s = self._industriel(_economie())
        self.assertNotIn("prix_achat", json.dumps(s, ensure_ascii=False))
