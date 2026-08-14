# -*- coding: utf-8 -*-
"""PV48 — la charge utile des 4 tiroirs débutant : clés, honnêteté, coût.

Trois familles de tests, et la troisième est la moins évidente :

1. **Les clés** — chaque tiroir consomme un contrat écrit dans son composant
   (``TiroirKits``, ``TiroirAllees`` + ``AlleeGratuiteChart``, ``TiroirRives``,
   ``TiroirOrientation``). Une clé renommée ici casse un écran en silence.
2. **L'honnêteté** — la granularité « par segment » n'existe pas dans le
   moteur, le motif de refus d'orientation n'est pas réécrit, un bouton n'est
   jamais proposé sans son chiffre rejoué.
3. **Le coût** — un tiroir rejoue un DP complet par comparaison. Le budget
   d'appels est un GARDE-FOU vérifié, pas une intention.
"""

import unittest

from core.calepinage.obstacles import appliquer_regles
from core.calepinage.optimum import optimiser
from core.calepinage.orientation import motif_orientation
from core.calepinage.pose_uniforme import balayer_phase
from core.calepinage.recommandations import EntreeMoteur
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.tiroirs import (
    BUDGET_APPELS_DEFAUT,
    DonneesTiroirs,
    donnees_tiroirs,
)
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    Axe,
    Parametres,
    Rives,
)
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)
CATALOGUE = (KIT_AO_PORTRAIT, KIT_AO_PAYSAGE)


def _entree(kits=(KIT_AO_PORTRAIT,), obstacles=(), **champs):
    surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                               rives=RIVES_AO)
    parametres = Parametres(kits=kits, rives=RIVES_AO, allee_m=0.60,
                            pas_recherche_m=0.01, **champs)
    return EntreeMoteur(surface=surface, parametres=parametres,
                        obstacles=obstacles)


def _tiroirs(entree=None, catalogue=CATALOGUE, **options):
    entree = entree or _entree()
    resultat = optimiser(entree.surface, entree.parametres, entree.obstacles,
                         entree.zones)
    return donnees_tiroirs(entree, resultat, catalogue=catalogue, **options)


class LesClesDesQuatreTiroirs(unittest.TestCase):
    """Le contrat de charge utile de chaque composant, clé par clé."""

    @classmethod
    def setUpClass(cls):
        cls.donnees = _tiroirs()

    def test_la_sortie_porte_exactement_les_quatre_tiroirs(self):
        self.assertEqual(set(self.donnees.vers_dict()),
                         {"kits", "allees", "rives", "orientation"})
        self.assertIsInstance(self.donnees, DonneesTiroirs)

    def test_tiroir_kits(self):
        kits = self.donnees.kits
        self.assertEqual(set(kits) - {"recommandation", "composition",
                                      "contre_epreuve"},
                         {"kits", "granularites", "approvisionnement"})
        for ligne in kits["kits"]:
            self.assertEqual(set(ligne), {"code", "libelle", "recommande"})
        self.assertEqual(set(kits["recommandation"]), {"code", "libelle"})
        self.assertEqual(set(kits["composition"]), {"texte", "total_texte"})
        cas = kits["contre_epreuve"][0]
        self.assertEqual(set(cas), {"id", "segment", "options", "motif"})
        for option in cas["options"]:
            self.assertEqual(set(option), {"code", "libelle", "texte"})

    def test_tiroir_allees_et_graphe(self):
        allees = self.donnees.allees
        self.assertEqual(set(allees) - {"graphe"}, {"presets"})
        for preset in allees["presets"]:
            self.assertEqual(set(preset), {"code", "libelle", "largeur_m"})
        for point in allees["graphe"]["points"]:
            self.assertEqual(set(point), {"largeur_m", "compte",
                                          "texte_largeur", "texte_compte"})

    def test_tiroir_rives(self):
        champs = self.donnees.rives["champs"]
        self.assertEqual([c["code"] for c in champs],
                         ["rive_laterale_m", "rive_extremite_m",
                          "degagement_defaut_m",
                          "degagement_nature_inconnue_m"])
        for champ in champs:
            self.assertLessEqual({"code", "libelle", "unite", "min",
                                  "message_borne"}, set(champ))
        for impact in champs[0]["impacts"]:
            self.assertEqual(set(impact), {"valeur", "texte_valeur",
                                           "impact_texte", "sens"})
        variante = self.donnees.rives["variante_conservatrice"]
        self.assertEqual(set(variante),
                         {"libelle", "valeurs", "comparaison_texte"})
        self.assertEqual(variante["valeurs"],
                         {"rive_laterale_m": 1.50, "rive_extremite_m": 0.50,
                          "allee_m": 0.50})

    def test_tiroir_orientation(self):
        orientation = self.donnees.orientation
        self.assertEqual(set(orientation),
                         {"sens_rangees", "orientations_tables",
                          "segmentations", "formes_l"})
        for groupe in orientation.values():
            for option in groupe:
                self.assertLessEqual({"code", "libelle", "disponible"},
                                     set(option))


class RienNEstInvente(unittest.TestCase):
    """Ce que le moteur ne sait pas faire ne devient JAMAIS une option."""

    @classmethod
    def setUpClass(cls):
        cls.donnees = _tiroirs()

    def test_la_seule_granularite_est_la_toiture_entiere(self):
        self.assertEqual(self.donnees.kits["granularites"],
                         [{"code": "site", "libelle": "Toute la toiture"}])

    def test_ni_segmentation_ni_forme_l_ne_sont_meublees(self):
        self.assertEqual(self.donnees.orientation["segmentations"], [])
        self.assertEqual(self.donnees.orientation["formes_l"], [])

    def test_l_approvisionnement_n_est_jamais_confirme_par_ce_module(self):
        self.assertEqual(self.donnees.kits["approvisionnement"],
                         {"confirme": False})

    def test_le_motif_de_refus_est_repris_VERBATIM_du_moteur(self):
        refus = [o for o in self.donnees.orientation["sens_rangees"]
                 if not o["disponible"]]
        self.assertEqual(len(refus), 1)
        self.assertEqual(refus[0]["code"], Axe.EST_OUEST.value)
        self.assertEqual(refus[0]["motif"],
                         motif_orientation(KIT_AO_PORTRAIT, Axe.EST_OUEST))

    def test_une_contre_epreuve_d_une_seule_option_n_est_pas_publiee(self):
        seul = _tiroirs(catalogue=(KIT_AO_PORTRAIT,))
        self.assertNotIn("contre_epreuve", seul.kits)

    def test_la_contre_epreuve_rejoue_bien_chaque_kit(self):
        cas = self.donnees.kits["contre_epreuve"][0]
        comptes = {}
        for kit in CATALOGUE:
            entree = _entree(kits=(kit,))
            comptes[kit.code] = optimiser(entree.surface,
                                          entree.parametres).modules
        for option in cas["options"]:
            self.assertEqual(option["texte"],
                             "%d modules" % comptes[option["code"]])
        self.assertIn("rejoués par le moteur", cas["motif"])


class LesImpactsSontMesures(unittest.TestCase):
    """Un impact affiché est un DP rejoué — jamais une extrapolation."""

    @classmethod
    def setUpClass(cls):
        cls.donnees = _tiroirs()

    def _champ(self, code):
        return next(c for c in self.donnees.rives["champs"]
                    if c["code"] == code)

    def _impacts(self, code):
        return {impact["valeur"]: impact
                for impact in self._champ(code)["impacts"]}

    def test_la_valeur_courante_vaut_zero_par_definition(self):
        courant = self._impacts("rive_laterale_m")[0.35]
        self.assertEqual(courant["impact_texte"], "aucun changement")
        self.assertEqual(courant["sens"], "neutre")
        self.assertEqual(courant["texte_valeur"], "0,35 m")

    def test_une_rive_d_extremite_plus_large_coute_des_modules(self):
        """20,00 - 2 × 0,40 = 19,20 : 16 pas au lieu de 17, sur 2 rangées."""
        perte = self._impacts("rive_extremite_m")[0.40]
        self.assertEqual(perte["impact_texte"], "-4 modules")
        self.assertEqual(perte["sens"], "perte")

    def test_les_ancres_sont_capees_a_la_valeur_courante_plus_ou_moins_10cm(self):
        valeurs = sorted(self._impacts("rive_laterale_m"))
        self.assertEqual(valeurs, [0.25, 0.30, 0.35, 0.40, 0.45])

    def test_les_degagements_ne_sont_pas_chiffres_ici(self):
        """Les obstacles portent DÉJÀ leur dégagement dérivé : annoncer
        « aucun changement » serait un mensonge, pas une mesure."""
        for code in ("degagement_defaut_m", "degagement_nature_inconnue_m"):
            self.assertNotIn("impacts", self._champ(code))

    def test_la_variante_conservatrice_porte_son_compte_rejoue(self):
        conservatrices = Rives(laterale_m=1.50, extremite_m=0.50)
        attendu = optimiser(
            SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                             rives=conservatrices),
            Parametres(kits=(KIT_AO_PORTRAIT,), rives=conservatrices,
                       allee_m=0.50, pas_recherche_m=0.01)).modules
        self.assertIn("%d modules contre" % attendu,
                      self.donnees.rives["variante_conservatrice"][
                          "comparaison_texte"])


class LeBudgetDAppelsEstUnGardeFou(unittest.TestCase):
    """Chaque comparaison rejoue un DP : le coût est BORNÉ et RAPPORTÉ."""

    def test_le_budget_par_defaut_n_est_jamais_depasse(self):
        donnees = _tiroirs()
        self.assertLessEqual(donnees.appels_moteur, BUDGET_APPELS_DEFAUT)
        self.assertEqual(donnees.budget_appels, BUDGET_APPELS_DEFAUT)
        self.assertLessEqual(BUDGET_APPELS_DEFAUT, 12)

    def test_un_budget_nul_ne_lance_aucun_calcul(self):
        donnees = _tiroirs(budget_appels=0)
        self.assertEqual(donnees.appels_moteur, 0)
        self.assertEqual(donnees.recherches_allee, 0)
        self.assertNotIn("contre_epreuve", donnees.kits)
        self.assertNotIn("variante_conservatrice", donnees.rives)
        self.assertNotIn("graphe", donnees.allees)
        # Les quatre tiroirs restent STRUCTURÉS : l'écran dégrade, il ne casse pas.
        self.assertEqual(set(donnees.vers_dict()),
                         {"kits", "allees", "rives", "orientation"})

    def test_un_budget_serre_chiffre_moins_mais_ne_ment_jamais(self):
        donnees = _tiroirs(budget_appels=3)
        self.assertLessEqual(donnees.appels_moteur, 3)
        for champ in donnees.rives["champs"]:
            for impact in champ.get("impacts", ()):
                self.assertIn(impact["sens"], ("gain", "perte", "neutre"))

    def test_un_budget_negatif_est_refuse(self):
        with self.assertRaises(ValueError):
            _tiroirs(budget_appels=-1)

    def test_la_recherche_d_allee_est_comptee_a_part(self):
        donnees = _tiroirs()
        self.assertEqual(donnees.recherches_allee, 1)

    def test_un_resultat_heuristique_fait_recalculer_la_reference(self):
        """Comparer un impact DP à un compte de balayage publierait un écart
        qui n'existe pas : la référence est alors REJOUÉE, et elle coûte."""
        entree = _entree()
        heuristique = balayer_phase(entree.surface, entree.parametres)
        donnees = donnees_tiroirs(entree, heuristique,
                                  catalogue=(KIT_AO_PORTRAIT,),
                                  budget_appels=1)
        self.assertEqual(donnees.appels_moteur, 1)
        self.assertTrue(donnees.budget_atteint)


class LePlateauGratuitDeLEcole(unittest.TestCase):
    """Le cas réel d'AOF50 : 314 modules de 0,60 m à plus de 1,90 m d'allée."""

    @classmethod
    def setUpClass(cls):
        surface = SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                allee_m=0.60, pas_recherche_m=0.01)
        entree = EntreeMoteur(surface=surface, parametres=parametres,
                              obstacles=appliquer_regles(ECOLE_OBSTACLES))
        cls.donnees = _tiroirs(entree, catalogue=(KIT_AO_PORTRAIT,))

    def test_le_plateau_porte_les_cles_du_graphe(self):
        plateau = self.donnees.allees["graphe"]["plateau"]
        self.assertEqual(set(plateau),
                         {"debut_m", "fin_m", "texte_debut", "texte_fin",
                          "resume", "largeur_offerte_m", "libelle_bouton"})
        self.assertGreater(plateau["fin_m"], plateau["debut_m"])
        self.assertIn("314 modules", plateau["resume"])
        self.assertIn("aucun module perdu", plateau["libelle_bouton"])

    def test_l_allee_offerte_est_proposee_en_prereglage(self):
        codes = [p["code"] for p in self.donnees.allees["presets"]]
        self.assertEqual(codes, ["minimale", "offerte"])
        offerte = self.donnees.allees["presets"][1]
        self.assertEqual(offerte["largeur_m"],
                         self.donnees.allees["graphe"]["plateau"][
                             "largeur_offerte_m"])

    def test_la_composition_retenue_vient_du_plan(self):
        composition = self.donnees.kits["composition"]
        self.assertEqual(composition["texte"], "4 rangées : 4 × AO_PORTRAIT")
        self.assertIn("314 modules", composition["total_texte"])
        self.assertIn("kWc", composition["total_texte"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
