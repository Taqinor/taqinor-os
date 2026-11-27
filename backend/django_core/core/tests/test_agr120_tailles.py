# -*- coding: utf-8 -*-
"""AGR120 — trois tailles tirées du catalogue + hectares irrigables (noyau
pur, sans base).

Pompes : courbes OSP 30/8, 30/11, 30/13 recopiées du seed
(``seed_catalogue.py``) mais rendues CHIFFRABLES pour le test (dans le seed
elles sont à prix 0, QXG3) ; « Pompe test 4 kW » = donnée de test. Profils
horaires SYNTHÉTIQUES.
"""

import math
import unittest

from core.pompage.agronomie import besoin_agronomique
from core.pompage.selection import choisir_pompe
from core.pompage.tailles import (
    MOTIF_EXISTANTE, MOTIF_HA_VOLUME, MOTIF_INFERIEURE, proposer_tailles,
)
from core.pompage.volumes import _CLEARSKY_HOURLY_SHAPE

PIC = max(_CLEARSKY_HOURLY_SHAPE)
PICS = (650, 720, 820, 900, 950, 980, 990, 960, 880, 780, 680, 630)
PROFILS = tuple(tuple(f / PIC * g for f in _CLEARSKY_HOURLY_SHAPE)
                for g in PICS)

DEBITS = [0, 12, 24, 30, 36, 39]


def _pompe(id_, nom, kw, hmt=None, debits=DEBITS):
    return {"id": id_, "nom": nom, "role_pompage": "pompe",
            "type_pompe": "immergee", "alimentation": "tri",
            "pompe_kw": str(kw), "tension_v": 380,
            "courbe_pompe": {"debits_m3h": debits, "hmt_m": hmt},
            "fiche": None, "prix_connu": True}


POMPES = [
    _pompe(50, "Pompe immergée test 4 kW (380V)", 4, [90, 80, 62, 50],
           [0, 6, 12, 15]),
    _pompe(314, "Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3\", 380V)", 7.5,
           [91, 85, 70, 60, 43, 34]),
    _pompe(315, "Pompe immergée OSP 30/11 — 12.5 CV / 9.3 kW (3\", 380V)",
           9.3, [125, 117, 97, 83, 59, 46]),
    _pompe(316, "Pompe immergée OSP 30/13 — 15 CV / 11 kW (3\", 380V)", 11,
           [148, 138, 114, 98, 70, 55]),
]


def _var(id_, kw):
    return {"id": id_, "nom": "VARIATEUR VEICHI SI23 %sKW 380V" % kw,
            "role_pompage": "variateur_pompage", "pompe_kw": str(kw),
            "tension_v": 380, "fiche": None, "prix_connu": True}


VARIATEURS = [_var(1, 4), _var(2, 7.5), _var(3, 11)]
PANNEAU = {"id": 3, "nom": "Panneau 710W", "pmax_wc": 710, "vmp_v": 40.4,
           "voc_v": 48.6, "isc_a": 18.6, "imp_a": 17.6, "prix_connu": True}
KIT = {"structure": {"id": 51, "nom": "Structure au sol", "prix_connu": True}}

BESOIN = [135.0] * 12
HMT = 58.7


def _neuve(**extra):
    choix = choisir_pompe(POMPES, hmt_m=HMT, debit_conception_m3h=25,
                          alimentation="tri")
    params = dict(choix_pompe=choix, besoin_m3_jour_mois=BESOIN, hmt_m=HMT,
                  alimentation="tri", variateurs=VARIATEURS, panneau=PANNEAU,
                  profils_horaires=PROFILS, kit=KIT)
    params.update(extra)
    return choix, proposer_tailles(**params)


class TroisTailles(unittest.TestCase):

    def test_catalogue_a_3_paliers_tailles_ordonnees(self):
        choix, res = _neuve()
        self.assertEqual(choix["pompe"]["produit"], 314)
        self.assertEqual([t["cle"] for t in res["tailles"]],
                         ["inferieure", "recommandee", "superieure"])
        self.assertEqual([t["pompe_produit"] for t in res["tailles"]],
                         [50, 314, 315])
        self.assertEqual(res["defaut"], "recommandee")
        recommandee = res["tailles"][1]
        self.assertTrue(recommandee["retenue"])
        self.assertGreaterEqual(recommandee["couverture_mois_critique_pct"],
                                95)
        # Couverture de l'inférieure AFFICHÉE (jamais masquée) ; son débit à
        # la HMT est sous le débit de conception (12,8 < 25 m³/h).
        self.assertIsNotNone(
            res["tailles"][0]["couverture_mois_critique_pct"])
        self.assertLess(res["tailles"][0]["puissance_kw"],
                        recommandee["puissance_kw"])
        self.assertFalse(res["tailles"][0]["retenue"])
        # Composition AGR119 portée par chaque taille.
        cles = [x["cle"] for x in recommandee["composition"]["inclus"]]
        self.assertEqual(cles[:3], ["pompe", "variateur", "panneaux"])
        self.assertEqual(len(recommandee["m3_jour_mois"]), 12)

    def test_palier_absent_omis_avec_motif(self):
        choix = choisir_pompe(POMPES[1:3], hmt_m=HMT,
                              debit_conception_m3h=25, alimentation="tri")
        res = proposer_tailles(
            choix_pompe=choix, besoin_m3_jour_mois=BESOIN, hmt_m=HMT,
            alimentation="tri", variateurs=VARIATEURS, panneau=PANNEAU,
            profils_horaires=PROFILS, kit=KIT)
        self.assertEqual([t["cle"] for t in res["tailles"]],
                         ["recommandee", "superieure"])
        self.assertEqual(res["tailles_omises"],
                         [{"cle": "inferieure", "motif": MOTIF_INFERIEURE}])

    def test_aucune_pompe_chiffrable_trois_omises(self):
        choix = choisir_pompe([], hmt_m=HMT, debit_conception_m3h=25,
                              alimentation="tri")
        res = proposer_tailles(choix_pompe=choix, besoin_m3_jour_mois=BESOIN,
                               hmt_m=HMT, alimentation="tri",
                               variateurs=VARIATEURS, panneau=PANNEAU)
        self.assertEqual(res["tailles"], [])
        self.assertEqual(len(res["tailles_omises"]), 3)


class PreDimensionnement(unittest.TestCase):
    """T4-X1-009 — pompes monophasées SANS courbe : une taille proposée sous la
    puissance minimale que l'écran affiche le dit en mots."""

    def test_inferieure_sous_la_puissance_minimale_le_dit(self):
        def mono(id_, nom, kw):
            return {"id": id_, "nom": nom, "role_pompage": "pompe",
                    "type_pompe": "immergee", "alimentation": "mono",
                    "pompe_kw": str(kw), "tension_v": 220,
                    "courbe_pompe": None, "fiche": None, "prix_connu": True}
        pompes = [mono(60, "Pompe test 1,1 kW mono", 1.1),
                  mono(61, "Pompe test 2hp mono", 1.47),
                  mono(62, "Pompe test 2,2 kW mono", 2.2)]
        variateurs = [{"id": 9, "nom": "VARIATEUR VEICHI SI22 2.2KW 220V",
                       "role_pompage": "variateur_pompage", "pompe_kw": "2.2",
                       "tension_v": 220, "fiche": None, "prix_connu": True}]
        # HMT 40 m, 5 m³/h : il faut au moins 1,56 kW (message de l'écran).
        choix = choisir_pompe(pompes, hmt_m=40, debit_conception_m3h=5,
                              alimentation="mono")
        self.assertEqual(choix["etape"], "pre_dimensionnement")
        self.assertEqual(choix["pompe"]["produit"], 62)
        self.assertIn("au moins 1,56 kW", [
            a["message"] for a in choix["alertes"]
            if a["code"] == "pompe_sans_courbe"][0])
        res = proposer_tailles(
            choix_pompe=choix, besoin_m3_jour_mois=[35.0] * 12, hmt_m=40,
            alimentation="mono", variateurs=variateurs, panneau=PANNEAU,
            profils_horaires=PROFILS, kit=KIT)
        par_cle = {t["cle"]: t for t in res["tailles"]}
        self.assertEqual(par_cle["inferieure"]["pompe_produit"], 61)
        inferieure = par_cle["inferieure"]["motif"]
        self.assertIn("ne peut pas monter le débit demandé", inferieure)
        self.assertIn("1,47 kW", inferieure)
        self.assertIn("au moins 1,56 kW", inferieure)
        # La recommandée (2,2 kW ≥ 1,56 kW) garde la phrase d'avant.
        self.assertIn("couverture non calculée",
                      par_cle["recommandee"]["motif"])
        self.assertNotIn("ne peut pas", par_cle["recommandee"]["motif"])


class Hectares(unittest.TestCase):

    def test_ha_derives_et_etiquetes_estimation(self):
        agro = besoin_agronomique(
            [{"culture": "olivier", "surface_ha": 4, "methode": "goutte"}],
            region="tadla")
        _choix, res = _neuve(besoin_m3_jour_mois=agro["m3_jour_mois"],
                             besoin_agronomique=agro)
        ha = res["tailles"][1]["ha_irrigables"]
        self.assertIsNotNone(ha["valeur"])
        self.assertIn("estimation", ha["motif"])
        taille = res["tailles"][1]
        mois = taille["champ"]["mois_critique"]
        attendu = round(taille["m3_jour_mois"][mois - 1]
                        / agro["m3_ha_jour_mois"][mois - 1], 1)
        self.assertEqual(ha["valeur"], attendu)

    def test_besoin_declare_aucun_ha(self):
        _choix, res = _neuve()
        ha = res["tailles"][1]["ha_irrigables"]
        self.assertIsNone(ha["valeur"])
        self.assertEqual(ha["motif"], MOTIF_HA_VOLUME)


class Existante(unittest.TestCase):

    def test_une_seule_taille_avec_motif(self):
        res = proposer_tailles(
            mode_pompe="existante",
            plaque={"kw": 4, "tension_v": 380, "phases": 3},
            debit_declare_m3h=12, besoin_m3_jour_mois=[60.0] * 12,
            hmt_m=50, variateurs=VARIATEURS, panneau=PANNEAU,
            profils_horaires=PROFILS, kit=KIT)
        self.assertEqual(len(res["tailles"]), 1)
        taille = res["tailles"][0]
        self.assertEqual(taille["motif"], MOTIF_EXISTANTE)
        self.assertIsNone(taille["pompe_produit"])
        self.assertNotIn("pompe", [x["cle"] for x in
                                   taille["composition"]["inclus"]])
        self.assertEqual({o["cle"] for o in res["tailles_omises"]},
                         {"inferieure", "superieure"})


class BesoinIncouvrable(unittest.TestCase):
    """AGM2 (D-AGM-2) — un besoin que la pompe ne couvre jamais ne produit
    pas un champ sans borne : couverture < 100 % affichee, champ <= 1,5 × la
    plaque (a l'arrondi de panneau pres)."""

    def test_champ_borne_et_couverture_honnete(self):
        _choix, res = _neuve(besoin_m3_jour_mois=[800.0] * 12)
        for taille in res["tailles"]:
            kw = taille["puissance_kw"]
            self.assertLessEqual(taille["champ"]["nb_panneaux"],
                                 math.ceil(1.5 * kw * 1000 / 710))
            self.assertLess(taille["couverture_mois_critique_pct"], 100)


class PompeQuiNeDelivrePasLeDebit(unittest.TestCase):
    """T4-V2-003 — HMT 80 m, débit souhaité 20 m³/h : l'OSP 30/8 (≈ 16 m³/h
    à 80 m) ne « couvre » plus le besoin sous un champ de 4 à 8 fois sa
    puissance ; elle est dite insuffisante, champ dans la bande."""

    def _tailles(self):
        from core.pompage.conception import heures_pic

        heures = [heures_pic(p) for p in PROFILS]
        besoin = [20.0 * h for h in heures]
        choix = choisir_pompe(POMPES, hmt_m=80, debit_conception_m3h=20,
                              alimentation="tri")
        res = proposer_tailles(
            choix_pompe=choix, besoin_m3_jour_mois=besoin, hmt_m=80,
            alimentation="tri", variateurs=VARIATEURS, panneau=PANNEAU,
            profils_horaires=PROFILS, kit=KIT)
        return {t["cle"]: t for t in res["tailles"]}

    def test_inferieure_bornee_et_dite_insuffisante(self):
        tailles = self._tailles()
        inf, reco = tailles["inferieure"], tailles["recommandee"]
        self.assertEqual(inf["pompe_produit"], 314)
        self.assertLessEqual(inf["nb_panneaux"],
                             math.floor(1.5 * 7.5 * 1000 / 710))
        self.assertLessEqual(inf["nb_panneaux"], reco["nb_panneaux"])
        self.assertLess(inf["couverture_mois_critique_pct"], 100)
        self.assertIn("ne délivre pas le débit demandé", inf["motif"])
        self.assertIn("80 m", inf["motif"])
        codes = [a["code"] for a in inf["champ"]["alertes"]]
        self.assertIn("besoin_non_couvert_champ", codes)

    def test_recommandee_et_superieure_inchangees(self):
        tailles = self._tailles()
        self.assertIsNone(tailles["recommandee"]["motif"])
        self.assertIsNone(tailles["superieure"]["motif"])
        self.assertGreaterEqual(
            tailles["recommandee"]["couverture_mois_critique_pct"], 95)


class DisjoncteurSurLeKwDuVariateur(unittest.TestCase):
    """Revue R4 — UNE pompe, UN kW : une pompe aux seuls CV (sans pompe_kw)
    est dimensionnée variateur ET disjoncteur sur le MÊME kW
    (``selection.kw_pompe``), et la phrase d'hypothèse le dit."""

    def test_pompe_aux_seuls_cv(self):
        cv_seuls = [dict(p, pompe_kw=None, pompe_cv="10") if p["id"] == 314
                    else p for p in POMPES]
        disjoncteurs = [
            {"id": 900 + a, "nom": "Disjoncteur AC courbe C %d A tétrapolaire"
             % a, "role_pompage": "protection_ac", "prix_connu": True}
            for a in (16, 20, 25, 32)]
        choix = choisir_pompe(cv_seuls, hmt_m=HMT, debit_conception_m3h=25,
                              alimentation="tri")
        res = proposer_tailles(
            choix_pompe=choix, besoin_m3_jour_mois=BESOIN, hmt_m=HMT,
            alimentation="tri", variateurs=VARIATEURS, panneau=PANNEAU,
            profils_horaires=PROFILS,
            kit=dict(KIT, produits_options=disjoncteurs))
        taille = next(t for t in res["tailles"] if t["pompe_produit"] == 314)
        inclus = {x["cle"]: x for x in taille["composition"]["inclus"]}
        # 10 CV ⇒ 7,5 kW (moteur normalisé) : variateur 7,5 kW (id 2) …
        self.assertEqual(inclus["variateur"]["produit"], 2)
        # … et disjoncteur sur ces 7,5 kW : 7 500 / (√3 × 380) ≈ 11,4 A ⇒ 16 A.
        self.assertEqual(inclus["disjoncteur_ac"]["produit"], 916)
        self.assertIn("déduit des 10 CV de la pompe (7,5 kW) et 380 V",
                      inclus["disjoncteur_ac"]["hypothese"])
        self.assertIn("11,4 A", inclus["disjoncteur_ac"]["hypothese"])


class ArticlesSansPrix(unittest.TestCase):
    """ACAL1257 — chaque taille NOMME les lignes ``inclus`` de son kit sans
    prix (libellé du catalogue, dans l'ordre du kit, jamais un prix) ; liste
    vide quand tout est chiffré ; ``prix_connu`` inchangé."""

    def test_structure_sans_prix_nommee(self):
        kit = {"structure": {"id": 51, "nom": "Structure au sol pompage",
                             "prix_connu": False}}
        _choix, res = _neuve(kit=kit)
        self.assertEqual(len(res["tailles"]), 3)
        for taille in res["tailles"]:
            attendus = [x for x in taille["composition"]["inclus"]
                        if not x["prix_connu"]]
            self.assertIn("Structure au sol pompage",
                          taille["articles_sans_prix"])
            self.assertEqual(len(taille["articles_sans_prix"]),
                             len(attendus))
            self.assertFalse(taille["prix_connu"])
            self.assertFalse(any("prix à renseigner" in a
                                 for a in taille["articles_sans_prix"]))

    def test_kit_tout_chiffre_liste_vide(self):
        _choix, res = _neuve()
        for taille in res["tailles"]:
            self.assertEqual(taille["prix_connu"],
                             taille["articles_sans_prix"] == [])

    def test_pompe_existante_porte_la_cle(self):
        kit = {"structure": {"id": 51, "nom": "Structure au sol pompage",
                             "prix_connu": False}}
        res = proposer_tailles(
            mode_pompe="existante",
            plaque={"kw": 4, "tension_v": 380, "phases": 3},
            debit_declare_m3h=12, besoin_m3_jour_mois=[60.0] * 12,
            hmt_m=50, variateurs=VARIATEURS, panneau=PANNEAU,
            profils_horaires=PROFILS, kit=kit)
        self.assertIn("Structure au sol pompage",
                      res["tailles"][0]["articles_sans_prix"])


if __name__ == "__main__":
    unittest.main()
