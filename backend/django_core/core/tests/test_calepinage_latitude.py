# -*- coding: utf-8 -*-
"""CAL167 — UNE seule politique de pas : latitude du site + empreinte du chevron.

Deux pas concurrents gouvernaient la même pose. D'un côté le noyau espaçait à
l'élévation NATIONALE de 21° et comptait l'ombre de faîte est-ouest PLEINE ; de
l'autre le cerveau du site calculait l'élévation du LIEU et retranchait
l'empreinte propre du chevron. Une villa recevait donc deux calepinages selon
l'écran qui l'avait produite.

Ce module prouve exactement quatre choses :

  1. **Sans latitude, RIEN ne bouge** — le pas est bit pour bit celui d'avant,
     et les goldens villa redonnent leurs comptes figés ;
  2. **Deux latitudes donnent deux pas** — et deux COMPTES, produits par le
     moteur, jamais estimés ;
  3. **Le noyau ne devine jamais un lieu** — ``latitude_deg`` vaut ``None`` par
     défaut, et la politique qui en a besoin REFUSE en nommant le champ ;
  4. **La politique est-ouest choisie est NOMMÉE dans la preuve**, l'ancienne
     reste le défaut, et l'écart entre les deux se DÉCOMPOSE entièrement en
     deux termes mesurés (direction de l'ombre + empreinte du pan) — aucune
     rangée n'est gagnée pour une raison qu'on ne sait pas nommer.

Aucune base de données : ``unittest`` pur.

Run :
    python -m unittest core.tests.test_calepinage_latitude -v
"""

import io
import json
import math
import os
import unittest

from core.calepinage.adaptateurs.villa import vers_entree
from core.calepinage.perf import optimiser_economique
from core.calepinage.politique_pas import (
    ELEVATION_DIMENSIONNEMENT_DEG,
    ELEVATION_PLANCHER_DEG,
    EW_EMPREINTE_RETRANCHEE,
    EW_OMBRE_PLEINE,
    PASSAGE_CHEVRON_EW_M,
    POLITIQUES_EW,
    AntiOmbrage,
    position_solaire_solstice,
)
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_VILLA_720,
    KIT_VILLA_EW,
    Axe,
    Parametres,
    Rives,
)

GOLDEN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "calepinage", "golden", "villa")

#: Les deux goldens villa et leurs comptes FIGÉS (mêmes valeurs que
#: ``test_calepinage_villa.ATTENDUS_VILLA`` — la non-régression de CAL167 est
#: précisément « ces nombres ne bougent pas »).
ATTENDUS_VILLA = (("villa_plate_14x10.json", 18),
                  ("villa_pente_12x8.json", 24))

#: Deux villes marocaines RÉELLES, aux deux bouts de la plage du pays.
AGADIR_LAT, TANGER_LAT = 30.4, 35.8


def _charger(nom):
    with io.open(os.path.join(GOLDEN, nom), encoding="utf-8") as fh:
        return json.load(fh)


def _toiture_plate(kit, longueur_m=20.0, largeur_m=14.0):
    """Une toiture d'essai LIBRE : aucun obstacle, aucune zone."""
    rives = Rives(laterale_m=0.50, extremite_m=0.50)
    surface = SurfaceRectangle(repere="ESSAI", longueur_m=longueur_m,
                               largeur_m=largeur_m, rives=rives,
                               axe_rangee=Axe.NORD_SUD)
    parametres = Parametres(kits=(kit,), rives=rives, axe_rangee=Axe.NORD_SUD,
                            allee_m=0.0, pas_recherche_m=0.01)
    return surface, parametres


def _compter(kit, politique, largeur_m=14.0):
    surface, parametres = _toiture_plate(kit, largeur_m=largeur_m)
    return optimiser_economique(surface, parametres, (), (), politique).modules


class SansLatitudeRienNeBouge(unittest.TestCase):
    """Le chemin historique reste BIT-IDENTIQUE — c'est la contrepartie."""

    def test_le_pas_est_exactement_l_ancienne_formule(self):
        politique = AntiOmbrage()
        self.assertIsNone(politique.latitude_deg)
        for kit in (KIT_VILLA_720, KIT_VILLA_EW):
            hauteur = (kit.cote_dans_la_pente_m
                       * math.sin(math.radians(kit.inclinaison_deg)))
            attendu = hauteur / math.tan(
                math.radians(ELEVATION_DIMENSIONNEMENT_DEG))
            # Égalité EXACTE, pas « presque » : un golden se rejoue au bit.
            self.assertEqual(politique.longueur_ombre_m(kit), attendu)
            self.assertEqual(politique.pas_apres_rangee(kit, 0.0),
                             attendu + politique.marge_m)

    def test_le_defaut_est_l_ombre_de_faite_pleine(self):
        self.assertEqual(AntiOmbrage().politique_ew, EW_OMBRE_PLEINE)

    def test_les_goldens_villa_redonnent_leurs_comptes(self):
        for nom, modules in ATTENDUS_VILLA:
            entree, _projection, politique = vers_entree(_charger(nom))
            resultat = optimiser_economique(entree.surfaces[0],
                                            entree.parametres,
                                            entree.obstacles, entree.zones,
                                            politique)
            self.assertEqual(resultat.modules, modules, nom)


class DeuxLatitudesDonnentDeuxPas(unittest.TestCase):
    def test_agadir_est_plus_dense_que_tanger(self):
        agadir = AntiOmbrage(latitude_deg=AGADIR_LAT)
        tanger = AntiOmbrage(latitude_deg=TANGER_LAT)
        # Plus au sud => soleil plus haut => ombre plus courte => pas plus court.
        self.assertGreater(agadir.elevation_effective_deg(),
                           tanger.elevation_effective_deg())
        self.assertLess(agadir.pas_apres_rangee(KIT_VILLA_720, 0.0),
                        tanger.pas_apres_rangee(KIT_VILLA_720, 0.0))

    def test_deux_latitudes_donnent_deux_comptes_produits_par_le_moteur(self):
        # 16,50 m de profondeur : l'ombre plus courte d'Agadir y loge une
        # rangée de plus que Tanger. Les nombres SORTENT du moteur.
        modules_agadir = _compter(KIT_VILLA_720,
                                  AntiOmbrage(latitude_deg=AGADIR_LAT),
                                  largeur_m=16.50)
        modules_tanger = _compter(KIT_VILLA_720,
                                  AntiOmbrage(latitude_deg=TANGER_LAT),
                                  largeur_m=16.50)
        self.assertGreater(modules_agadir, modules_tanger)

    def test_le_plancher_soleil_tres_bas_tient_encore(self):
        polaire = AntiOmbrage(latitude_deg=80.0)
        self.assertEqual(polaire.elevation_effective_deg(),
                         ELEVATION_PLANCHER_DEG)


class LeNoyauNeDevineJamaisUnLieu(unittest.TestCase):
    def test_aucune_latitude_par_defaut(self):
        # PV65 : la latitude vient de l'APPELANT (le point GPS du calepinage).
        self.assertIsNone(AntiOmbrage().latitude_deg)

    def test_la_politique_empreinte_refuse_sans_latitude_en_nommant_le_champ(self):
        with self.assertRaises(ValueError) as contexte:
            AntiOmbrage(politique_ew=EW_EMPREINTE_RETRANCHEE)
        message = str(contexte.exception)
        self.assertIn("latitude_deg", message)
        self.assertIn("GPS", message)

    def test_l_ombre_est_ouest_refuse_sans_latitude(self):
        with self.assertRaises(ValueError) as contexte:
            AntiOmbrage().ombre_de_faite_ew_m(KIT_VILLA_EW)
        self.assertIn("latitude_deg", str(contexte.exception))

    def test_une_politique_est_ouest_inconnue_est_refusee(self):
        with self.assertRaises(ValueError) as contexte:
            AntiOmbrage(latitude_deg=AGADIR_LAT, politique_ew="AU_PIF")
        self.assertIn("politique_ew", str(contexte.exception))

    def test_il_n_y_a_que_deux_politiques_est_ouest(self):
        self.assertEqual(POLITIQUES_EW,
                         (EW_OMBRE_PLEINE, EW_EMPREINTE_RETRANCHEE))


class LaPolitiqueChoisieEstNommeeDansLaPreuve(unittest.TestCase):
    def test_l_hypothese_nomme_la_valeur_nationale_quand_la_latitude_manque(self):
        hypothese = AntiOmbrage().hypothese
        self.assertIn("valeur nationale", hypothese)
        self.assertIn("non transmise", hypothese)
        self.assertIn("21", hypothese)

    def test_l_hypothese_nomme_la_latitude_et_l_heure_de_design(self):
        hypothese = AntiOmbrage(latitude_deg=AGADIR_LAT).hypothese
        self.assertIn("30.400", hypothese)
        self.assertIn("10 h solaire", hypothese)

    def test_les_deux_politiques_est_ouest_ne_disent_pas_la_meme_chose(self):
        pleine = AntiOmbrage(latitude_deg=AGADIR_LAT).hypothese
        empreinte = AntiOmbrage(
            latitude_deg=AGADIR_LAT,
            politique_ew=EW_EMPREINTE_RETRANCHEE).hypothese
        self.assertIn("PLEINE", pleine)
        self.assertIn("empreinte du pan", empreinte)
        self.assertNotEqual(pleine, empreinte)

    def test_toute_politique_sait_se_nommer(self):
        # Le slot existe sur le CONTRAT, pas seulement sur l'anti-ombrage.
        from core.calepinage.politique_pas import Affleurant, AlleeFixe
        self.assertEqual(AlleeFixe().hypothese, "ALLEE_FIXE")
        self.assertEqual(Affleurant().hypothese, "AFFLEURANT")


class LEmpreinteDuChevronEstLeSeulEcart(unittest.TestCase):
    """L'écart entre les deux politiques se DÉCOMPOSE, terme par terme."""

    def _paire(self, latitude=AGADIR_LAT):
        return (AntiOmbrage(latitude_deg=latitude),
                AntiOmbrage(latitude_deg=latitude,
                            politique_ew=EW_EMPREINTE_RETRANCHEE))

    def test_le_pas_chevron_est_l_identite_du_site(self):
        _pleine, empreinte = self._paire()
        attendu = (max(0.0, empreinte.ombre_de_faite_ew_m(KIT_VILLA_EW)
                       - empreinte.empreinte_pan_m(KIT_VILLA_EW))
                   + PASSAGE_CHEVRON_EW_M)
        self.assertAlmostEqual(empreinte.pas_chevron_ew_m(KIT_VILLA_EW),
                               attendu, places=12)

    def test_l_ecart_se_decompose_en_direction_plus_empreinte(self):
        pleine, empreinte = self._paire()
        kit = KIT_VILLA_EW
        gap_pleine = pleine.pas_apres_rangee(kit, 0.0)
        gap_empreinte = empreinte.pas_apres_rangee(kit, 0.0)
        ecart = gap_pleine - gap_empreinte

        # Terme 1 — la DIRECTION de l'ombre. Les chevrons s'empilent vers
        # l'est : ce qui les sépare est la composante est-ouest |sin γ| de
        # l'ombre, pas la composante nord-sud |cos γ| d'une rangée sud.
        direction = (empreinte.longueur_ombre_m(kit)
                     - empreinte.ombre_de_faite_ew_m(kit))
        # Terme 2 — l'EMPREINTE du pan ouest, qui absorbe l'ombre de faîte,
        # au prix du passage de maintenance qui remplace la marge.
        absorbe = min(empreinte.ombre_de_faite_ew_m(kit),
                      empreinte.empreinte_pan_m(kit))
        passage = PASSAGE_CHEVRON_EW_M - empreinte.marge_m

        self.assertAlmostEqual(ecart, direction + absorbe - passage,
                               places=12)
        # Rien d'autre ne bouge : même solstice, même heure, même élévation.
        self.assertEqual(pleine.elevation_effective_deg(),
                         empreinte.elevation_effective_deg())
        self.assertEqual(pleine.heure_solaire, empreinte.heure_solaire)

    def test_l_ecart_publie_est_celui_qu_on_mesure(self):
        pleine, empreinte = self._paire()
        self.assertAlmostEqual(
            empreinte.ecart_a_l_ombre_pleine_m(KIT_VILLA_EW),
            pleine.pas_apres_rangee(KIT_VILLA_EW, 0.0)
            - empreinte.pas_apres_rangee(KIT_VILLA_EW, 0.0),
            places=12)

    def test_l_ecart_est_borne_par_l_ombre_pleine(self):
        _pleine, empreinte = self._paire()
        for kit in (KIT_VILLA_EW,):
            ecart = empreinte.ecart_a_l_ombre_pleine_m(kit)
            borne = (empreinte.longueur_ombre_m(kit) + empreinte.marge_m
                     - PASSAGE_CHEVRON_EW_M)
            self.assertGreater(ecart, 0.0)
            self.assertLessEqual(ecart, borne + 1e-12)

    def test_la_politique_ne_touche_QUE_les_chevrons_dos_a_dos(self):
        pleine, empreinte = self._paire()
        # Module unique plein sud : aucun pan ouest pour absorber l'ombre.
        self.assertFalse(empreinte.empreinte_ew_active(KIT_VILLA_720))
        self.assertEqual(empreinte.pas_apres_rangee(KIT_VILLA_720, 0.0),
                         pleine.pas_apres_rangee(KIT_VILLA_720, 0.0))
        self.assertTrue(empreinte.empreinte_ew_active(KIT_VILLA_EW))

    def test_le_chevron_absorbe_sa_propre_ombre_au_maroc(self):
        # Constat du site : le résidu est ≈ 0 aux latitudes marocaines, donc
        # l'écart entre chevrons se réduit au passage de maintenance.
        for latitude in (AGADIR_LAT, TANGER_LAT):
            empreinte = AntiOmbrage(latitude_deg=latitude,
                                    politique_ew=EW_EMPREINTE_RETRANCHEE)
            self.assertLess(empreinte.ombre_de_faite_ew_m(KIT_VILLA_EW),
                            empreinte.empreinte_pan_m(KIT_VILLA_EW))
            self.assertAlmostEqual(empreinte.pas_chevron_ew_m(KIT_VILLA_EW),
                                   PASSAGE_CHEVRON_EW_M, places=12)

    def test_le_compte_suit_et_le_moteur_le_produit(self):
        pleine, empreinte = self._paire()
        # 15,00 m de profondeur : l'ombre de faîte absorbée par le pan y loge
        # un chevron de plus. Sur une toiture qui ne le permet pas, les deux
        # politiques rendent le MÊME compte — c'est bien un gain de place,
        # jamais un compte gonflé.
        dense = _compter(KIT_VILLA_EW, empreinte, largeur_m=15.00)
        conservateur = _compter(KIT_VILLA_EW, pleine, largeur_m=15.00)
        self.assertGreater(dense, conservateur)
        self.assertEqual(_compter(KIT_VILLA_EW, empreinte, largeur_m=14.00),
                         _compter(KIT_VILLA_EW, pleine, largeur_m=14.00))
        # Le pas COMPLET publié suit la même politique que le vide posé.
        self.assertAlmostEqual(
            empreinte.pas_de_rangee_m(KIT_VILLA_EW),
            KIT_VILLA_EW.emprise_transversale_m
            + empreinte.pas_chevron_ew_m(KIT_VILLA_EW), places=12)


class LAzimutDuSolsticeEstCeluiDuSite(unittest.TestCase):
    """Le portage des deux composantes d'ombre est FIDÈLE, pas approché."""

    def test_les_deux_composantes_viennent_du_meme_azimut(self):
        politique = AntiOmbrage(latitude_deg=AGADIR_LAT)
        alpha, azimut = position_solaire_solstice(AGADIR_LAT,
                                                  politique.heure_solaire)
        self.assertAlmostEqual(politique.elevation_effective_deg(),
                               max(ELEVATION_PLANCHER_DEG, alpha), places=12)
        hauteur = politique.hauteur_module_m(KIT_VILLA_EW)
        tangente = math.tan(math.radians(politique.elevation_effective_deg()))
        self.assertAlmostEqual(
            politique.longueur_ombre_m(KIT_VILLA_EW),
            hauteur * abs(math.cos(math.radians(azimut))) / tangente,
            places=12)
        self.assertAlmostEqual(
            politique.ombre_de_faite_ew_m(KIT_VILLA_EW),
            hauteur * abs(math.sin(math.radians(azimut))) / tangente,
            places=12)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
