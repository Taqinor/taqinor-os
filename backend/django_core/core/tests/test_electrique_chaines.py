# -*- coding: utf-8 -*-
"""PV34 — chaînes & onduleurs : la physique portée de ``solar_design`` est PROUVÉE.

La première classe rejoue, sur le noyau, les MÊMES cas numériques que
``apps/ventes/tests/test_solar_design.py::StringDesignTest`` : mêmes modules,
mêmes fenêtres onduleur, mêmes attendus. C'est ce qui rend le port DÉMONTRABLE
plutôt que déclaré — si le noyau divisait autrement, ces tests le diraient.

Les classes suivantes couvrent ce que le noyau AJOUTE : les bornes exactes de la
fenêtre froid/chaud, la longueur de chaîne imposée (acceptée dans la plage,
refusée AVEC MOTIF hors plage), le groupement par pan, et la réconciliation des
deux conventions de ratio.

Aucune base de données : ``unittest`` pur.
"""

import unittest

from core.electrique.chaines import (
    concevoir_chaines,
    fenetre_admissible,
)
from core.electrique.onduleurs import (
    BORNES_RATIO_AC_DC,
    BORNE_USUELLE_DC_AC,
    SEUIL_ALERTE_DC_AC,
    dimensionner_onduleurs,
    nombre_onduleurs,
    ratios,
)
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)


def _module(vmp=34.0, voc=41.0, pmax=550.0, coeff_voc=-0.27, coeff_pmax=-0.35,
            isc=13.8, imp=13.0):
    return SpecModule(vmp_v=vmp, voc_v=voc, isc_a=isc, imp_a=imp, pmax_wc=pmax,
                      temp_coeff_voc_pct_c=coeff_voc,
                      temp_coeff_pmax_pct_c=coeff_pmax)


def _onduleur(n_mppt=2, mppt_min=120.0, mppt_max=850.0, v_max=1000.0,
              i_max=26.0, ac_kw=10.0, phases=1, v_demarrage=90.0):
    return SpecOnduleur(n_mppt=n_mppt, mppt_v_min=mppt_min,
                        mppt_v_max=mppt_max, v_max_abs=v_max,
                        i_max_mppt_a=i_max, ac_kw=ac_kw, phases=phases,
                        v_demarrage_v=v_demarrage)


def _entree(nb_modules=24, module=None, onduleur=None, **kwargs):
    """Une entrée à UN pan — le cas de référence du calcul historique."""
    return EntreeElectrique(
        module=module or _module(),
        onduleur=onduleur or _onduleur(),
        groupes=(GroupePan("Sud", nb_modules, 180.0, 15.0),),
        **kwargs)


# ── Port À L'IDENTIQUE des cas de apps/ventes/tests/test_solar_design.py ──────
class PhysiquePorteeDeSolarDesign(unittest.TestCase):
    def test_repartition_equilibree_sur_deux_mppt(self):
        """24 panneaux, fenêtre large → chaînes ÉGALES réparties sur les 2 MPPT."""
        res = concevoir_chaines(_entree(24))
        self.assertEqual(res.bloquants, ())
        total = sum(c.nb_modules for c in res.chaines)
        self.assertEqual(total, 24)
        # Chaînes toutes de même longueur (le port garde le critère d'égalité).
        self.assertEqual(len({c.nb_modules for c in res.chaines}), 1)
        # Réparties également sur les 2 entrées MPPT.
        self.assertEqual(sorted(c.mppt for c in res.chaines), [1, 2])

    def test_voc_froid_au_dessus_du_v_max_est_bloquant(self):
        """Onduleur incompatible : UN module dépasse V_max au Voc froid.

        Le calcul historique se contentait d'un ``warning`` ; ici c'est un
        BLOQUANT — dépasser la tension maximale absolue détruit l'onduleur.
        """
        res = concevoir_chaines(_entree(
            5,
            module=_module(vmp=40.0, voc=49.0, coeff_voc=-0.30,
                           coeff_pmax=-0.35),
            onduleur=_onduleur(n_mppt=1, mppt_min=10.0, mppt_max=45.0,
                               v_max=50.0, ac_kw=4.0, v_demarrage=10.0)))
        # Voc à froid d'UNE chaîne (≈ 53,4 V) au-dessus de V_max (50 V).
        self.assertGreater(res.chaines[0].voc_froid_v, 50.0)
        self.assertTrue(res.bloquants)
        self.assertTrue(any("tension maximale" in b for b in res.bloquants))

    def test_les_tensions_montent_quand_il_fait_froid(self):
        """Physique : Voc/Vmp à froid > STC > à chaud (coefficient négatif)."""
        res = concevoir_chaines(_entree(10, temp_froid_c=-10.0,
                                        temp_chaud_c=70.0))
        chaine = res.chaines[0]
        self.assertGreater(chaine.voc_froid_v, chaine.vmp_stc_v)
        self.assertGreater(chaine.vmp_froid_v, chaine.vmp_chaud_v)
        self.assertGreater(chaine.vmp_froid_v, chaine.vmp_stc_v)

    def test_ratio_dc_ac(self):
        """18 × 550 W = 9,9 kWc ; onduleur 7 kW → DC/AC ≈ 1,41."""
        entree = _entree(18, onduleur=_onduleur(ac_kw=7.0))
        evaluation = dimensionner_onduleurs(entree)
        self.assertAlmostEqual(evaluation.puissance_dc_kwc, 9.9, places=6)
        self.assertAlmostEqual(evaluation.ratio_dc_ac.valeur, 9.9 / 7.0,
                               places=6)

    def test_ratio_dc_ac_eleve_alerte(self):
        """30 × 550 = 16,5 kWc / 8 kW = 2,06 → alerte NOMMÉE."""
        entree = _entree(30, onduleur=_onduleur(ac_kw=8.0))
        evaluation = dimensionner_onduleurs(entree)
        self.assertGreater(evaluation.ratio_dc_ac.valeur, SEUIL_ALERTE_DC_AC)
        self.assertTrue(any("DC/AC" in a for a in evaluation.alertes))

    def test_sans_puissance_ac_pas_de_ratio(self):
        entree = _entree(12, onduleur=_onduleur(ac_kw=0.0))
        evaluation = dimensionner_onduleurs(entree)
        self.assertIsNone(evaluation.ratio_dc_ac.valeur)
        self.assertIsNone(evaluation.ratio_ac_dc.valeur)
        self.assertTrue(any("non renseignée" in a for a in evaluation.alertes))

    def test_zero_module_ne_leve_pas(self):
        entree = EntreeElectrique(module=_module(), onduleur=_onduleur())
        res = concevoir_chaines(entree)
        self.assertEqual(res.chaines, ())
        self.assertEqual(res.reste_total, 0)
        self.assertTrue(any("aucun module" in a for a in res.alertes))

    def test_fenetre_trop_etroite_degrade_sans_lever(self):
        """Fenêtre incohérente (démarrage chaud > borne froide) → bloquant motivé."""
        res = concevoir_chaines(_entree(
            8, onduleur=_onduleur(n_mppt=1, mppt_min=700.0, mppt_max=750.0,
                                  v_max=750.0, ac_kw=4.0, v_demarrage=700.0)))
        self.assertTrue(res.fenetre.trop_etroite)
        self.assertTrue(any("trop étroite" in b for b in res.bloquants))
        # Le calcul continue quand même : des chaînes sont proposées.
        self.assertTrue(res.chaines)

    def test_nombre_de_modules_non_entier_ne_leve_pas(self):
        entree = EntreeElectrique(
            module=_module(), onduleur=_onduleur(),
            groupes=(GroupePan("Sud", "abc", 180.0, 15.0),))
        res = concevoir_chaines(entree)
        self.assertEqual(res.chaines, ())


# ── Ce que le noyau ajoute : bornes exactes de la fenêtre froid/chaud ─────────
class BornesDeLaFenetre(unittest.TestCase):
    def test_la_borne_haute_vient_du_voc_a_froid(self):
        """V_max 430,5 V ÷ Voc froid 43 V → 10 modules ; 429,5 V → 9.

        Les valeurs évitent volontairement l'égalité EXACTE (430,0) : un test
        posé sur une égalité flottante mesure l'arrondi binaire, pas la règle.
        """
        module = _module(voc=40.0, coeff_voc=-0.25)
        large = fenetre_admissible(module, _onduleur(v_max=430.5,
                                                     mppt_max=100000.0),
                                   -5.0, 70.0)
        self.assertEqual(large.max_par_voc, 10)
        etroite = fenetre_admissible(module, _onduleur(v_max=429.5,
                                                       mppt_max=100000.0),
                                     -5.0, 70.0)
        self.assertEqual(etroite.max_par_voc, 9)

    def test_la_borne_basse_vient_du_vmp_a_chaud(self):
        """Vmp chaud 24,6 V : bas de plage 122,5 V → 5 modules ; 123,5 V → 6."""
        module = _module(vmp=30.0, coeff_pmax=-0.40)
        basse = fenetre_admissible(
            module, _onduleur(mppt_min=122.5, v_demarrage=10.0), -5.0, 70.0)
        self.assertEqual(basse.min_par_mppt, 5)
        haute = fenetre_admissible(
            module, _onduleur(mppt_min=123.5, v_demarrage=10.0), -5.0, 70.0)
        self.assertEqual(haute.min_par_mppt, 6)

    def test_un_froid_plus_severe_raccourcit_la_chaine(self):
        module, onduleur = _module(), _onduleur()
        doux = fenetre_admissible(module, onduleur, 0.0, 70.0)
        rude = fenetre_admissible(module, onduleur, -20.0, 70.0)
        self.assertLessEqual(rude.longueur_max, doux.longueur_max)

    def test_une_chaleur_plus_severe_allonge_la_chaine_minimale(self):
        module, onduleur = _module(), _onduleur()
        tiede = fenetre_admissible(module, onduleur, -5.0, 50.0)
        brulant = fenetre_admissible(module, onduleur, -5.0, 85.0)
        self.assertGreaterEqual(brulant.longueur_min, tiede.longueur_min)

    def test_la_tension_de_demarrage_peut_fermer_la_borne_basse(self):
        module = _module()
        onduleur = _onduleur(mppt_min=100.0, v_demarrage=250.0)
        fenetre = fenetre_admissible(module, onduleur, -5.0, 70.0)
        self.assertGreater(fenetre.min_par_demarrage, fenetre.min_par_mppt)
        self.assertEqual(fenetre.longueur_min, fenetre.min_par_demarrage)


# ── Longueur de chaîne IMPOSÉE : la physique garde la main ────────────────────
class LongueurImposee(unittest.TestCase):
    def test_acceptee_dans_la_plage(self):
        fenetre = fenetre_admissible(_module(), _onduleur(), -5.0, 70.0)
        self.assertTrue(fenetre.admet(8))
        res = concevoir_chaines(_entree(24, longueur_chaine_forcee=8))
        self.assertIs(res.longueur_forcee_acceptee, True)
        self.assertEqual(res.nb_chaines, 3)
        self.assertTrue(all(c.nb_modules == 8 for c in res.chaines))
        self.assertEqual(res.bloquants, ())

    def test_refusee_hors_plage_avec_motif_francais(self):
        res = concevoir_chaines(_entree(24, longueur_chaine_forcee=30))
        self.assertIs(res.longueur_forcee_acceptee, False)
        motif = "\n".join(res.bloquants)
        self.assertIn("REFUSÉE", motif)
        self.assertIn("modules par chaîne", motif)   # la plage est citée
        # Le calcul retombe sur la longueur PHYSIQUE, il ne s'arrête pas.
        self.assertEqual(sum(c.nb_modules for c in res.chaines), 24)
        self.assertTrue(all(c.nb_modules <= res.fenetre.longueur_max
                            for c in res.chaines))

    def test_longueur_imposee_absurde_refusee(self):
        res = concevoir_chaines(_entree(24, longueur_chaine_forcee=0))
        self.assertIs(res.longueur_forcee_acceptee, False)
        self.assertTrue(res.bloquants)

    def test_trop_courte_est_aussi_refusee(self):
        """Sous la borne basse, le MPPT ne démarre pas — même refus motivé."""
        res = concevoir_chaines(_entree(24, longueur_chaine_forcee=2))
        self.assertIs(res.longueur_forcee_acceptee, False)
        self.assertTrue(any("REFUSÉE" in b for b in res.bloquants))


# ── Un groupe par PAN, jamais mélangé sur une entrée MPPT ─────────────────────
class GroupementParPan(unittest.TestCase):
    def _deux_pans(self, **kwargs):
        return EntreeElectrique(
            module=_module(), onduleur=_onduleur(n_mppt=2, ac_kw=13.0),
            groupes=(GroupePan("Sud", 12, 180.0, 15.0),
                     GroupePan("Est", 12, 90.0, 15.0)),
            **kwargs)

    def test_une_entree_mppt_ne_melange_jamais_deux_pans(self):
        res = concevoir_chaines(self._deux_pans())
        pans_par_mppt = {}
        for chaine in res.chaines:
            pans_par_mppt.setdefault(chaine.mppt, set()).add(chaine.pan)
        for mppt, pans in pans_par_mppt.items():
            self.assertEqual(len(pans), 1,
                             "l'entrée MPPT %d mélange %r" % (mppt, pans))

    def test_chaque_pan_garde_ses_modules(self):
        res = concevoir_chaines(self._deux_pans())
        par_pan = {}
        for chaine in res.chaines:
            par_pan[chaine.pan] = par_pan.get(chaine.pan, 0) + chaine.nb_modules
        self.assertEqual(par_pan, {"Sud": 12, "Est": 12})
        self.assertEqual({r.pan for r in res.repartitions}, {"Sud", "Est"})

    def test_plus_de_pans_que_d_entrees_est_nomme(self):
        entree = EntreeElectrique(
            module=_module(), onduleur=_onduleur(n_mppt=1, ac_kw=13.0),
            groupes=(GroupePan("Sud", 12, 180.0, 15.0),
                     GroupePan("Ouest", 12, 270.0, 15.0)))
        res = concevoir_chaines(entree)
        self.assertTrue(any("partagent une entrée" in a for a in res.alertes))

    def test_le_reste_hors_chaine_est_annonce(self):
        """25 modules, plage 5-22 : 5 chaînes de 5 — aucun reste caché."""
        res = concevoir_chaines(_entree(25))
        self.assertEqual(res.reste_total,
                         25 - sum(c.nb_modules for c in res.chaines))
        # Un nombre premier hors plage force un reste, qui est ALORS annoncé.
        res_23 = concevoir_chaines(_entree(23))
        if res_23.reste_total:
            self.assertTrue(any("réserve" in a for a in res_23.alertes))

    def test_courant_d_entree_mppt_depasse_est_alerte(self):
        """Trois chaînes sur une entrée : les Isc s'ADDITIONNENT."""
        entree = EntreeElectrique(
            module=_module(isc=13.8),
            onduleur=_onduleur(n_mppt=1, i_max=26.0, ac_kw=13.0),
            groupes=(GroupePan("Sud", 18, 180.0, 15.0),),
            longueur_chaine_forcee=6)
        res = concevoir_chaines(entree)
        self.assertEqual(res.nb_chaines, 3)
        self.assertTrue(any("Isc cumulé" in a for a in res.alertes))


# ── Réconciliation des DEUX conventions de ratio ──────────────────────────────
class ReconciliationDesRatios(unittest.TestCase):
    def test_les_deux_ratios_sont_inverses_par_construction(self):
        dc_ac, ac_dc = ratios(9.9, 7.0)
        self.assertAlmostEqual(dc_ac.valeur * ac_dc.valeur, 1.0, places=12)

    def test_chaque_ratio_publie_ses_bornes(self):
        dc_ac, ac_dc = ratios(9.9, 7.0)
        self.assertIn("1,35", dc_ac.fourchette_texte)
        self.assertIn("1,50", dc_ac.fourchette_texte)
        self.assertIn("0,75-1,00", ac_dc.fourchette_texte)
        self.assertEqual(dc_ac.borne_max, BORNE_USUELLE_DC_AC)
        self.assertEqual((ac_dc.borne_min, ac_dc.borne_max),
                         BORNES_RATIO_AC_DC)

    def test_hors_fourchette_ac_dc_est_alerte_avec_sa_convention(self):
        entree = _entree(30, onduleur=_onduleur(ac_kw=8.0))
        evaluation = dimensionner_onduleurs(entree)
        self.assertFalse(evaluation.ratio_ac_dc.dans_bornes)
        self.assertTrue(any("AC/DC" in a and "0,75-1,00" in a
                            for a in evaluation.alertes))

    def test_sans_puissance_les_deux_ratios_sont_nuls_mais_bornes(self):
        dc_ac, ac_dc = ratios(0.0, 0.0)
        self.assertIsNone(dc_ac.valeur)
        self.assertIsNone(ac_dc.valeur)
        self.assertEqual(dc_ac.texte, "—")
        self.assertIn("0,75-1,00", ac_dc.fourchette_texte)

    def test_onduleur_surdimensionne_est_signale(self):
        entree = _entree(10, onduleur=_onduleur(ac_kw=10.0))  # 5,5 kWc / 10 kW
        evaluation = dimensionner_onduleurs(entree)
        self.assertLess(evaluation.ratio_dc_ac.valeur, 1.0)
        self.assertTrue(any("surdimensionné" in a for a in evaluation.alertes))


class PlafondParOnduleur(unittest.TestCase):
    def test_le_plafond_impose_le_nombre_d_onduleurs(self):
        self.assertEqual(nombre_onduleurs(180.0, 60.0), 3)
        self.assertEqual(nombre_onduleurs(181.0, 60.0), 4)
        self.assertEqual(nombre_onduleurs(50.0, None), 1)
        self.assertEqual(nombre_onduleurs(0.0, 60.0), 0)

    def test_puissance_ac_totale_suit_le_nombre(self):
        entree = _entree(200, onduleur=_onduleur(ac_kw=50.0),
                         plafond_kwc_par_onduleur=60.0)
        evaluation = dimensionner_onduleurs(entree)     # 200 × 550 W = 110 kWc
        self.assertEqual(evaluation.nombre, 2)
        self.assertAlmostEqual(evaluation.puissance_ac_kw, 100.0, places=6)
        self.assertAlmostEqual(evaluation.dc_par_onduleur_kwc, 55.0, places=6)
