# -*- coding: utf-8 -*-
"""PV36 — sections de câble : la formule, la monotonie, et Ib ≤ In ≤ Iz.

Trois choses sont vérifiées ici et rien d'autre :

* la chute de tension SUIT la formule (calculée à la main dans le test, jamais
  recopiée du code) ;
* la section GRANDIT avec la longueur — c'est la propriété que tout le monde
  croit évidente et qu'une inversion de comparaison casse en silence ;
* la chaîne ``Ib ≤ In ≤ Iz`` tient sur les câbles réellement produits.

Aucune base de données : ``unittest`` pur.
"""

import math
import unittest

from core.electrique.cables import (
    AMPACITE_H1Z2Z2K,
    AMPACITE_U1000R2V_MONO,
    AMPACITE_U1000R2V_TRI,
    CHUTE_CIBLE_AC_PCT,
    CHUTE_CIBLE_DC_PCT,
    CHUTE_MAX_DC_PCT,
    COEFF_ISC_DIMENSIONNEMENT,
    CRITERE_CHUTE,
    RHO_CUIVRE_20C,
    SECTIONS_MM2,
    ampacite,
    chute_tension_pct,
    chute_tension_v,
    dimensionner_cables,
    proposer_section,
    verifier_ib_in_iz,
)
from core.electrique.chaines import concevoir_chaines
from core.electrique.onduleurs import dimensionner_onduleurs
from core.electrique.protections import concevoir_protections
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)


def _entree(nb_modules=24, dc_m=30.0, ac_m=10.0, phases=1, ac_kw=10.0,
            longueur=12, **kwargs):
    return EntreeElectrique(
        module=SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                          pmax_wc=550.0),
        onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                              v_max_abs=1000.0, i_max_mppt_a=60.0,
                              ac_kw=ac_kw, phases=phases, v_demarrage_v=90.0),
        groupes=(GroupePan("Sud", nb_modules, 180.0, 15.0),),
        dc_m=dc_m, ac_m=ac_m, phases=phases,
        longueur_chaine_forcee=longueur, **kwargs)


def _cables(entree):
    chaines = concevoir_chaines(entree)
    evaluation = dimensionner_onduleurs(entree)
    protections = concevoir_protections(entree, chaines, evaluation)
    return dimensionner_cables(entree, chaines, protections)


def _cable(resultat, repere):
    for cable in resultat.cables:
        if cable.repere == repere:
            return cable
    return None


class BaremeEtFormule(unittest.TestCase):
    def test_le_bareme_couvre_les_sections_normalisees(self):
        for bareme in (AMPACITE_H1Z2Z2K, AMPACITE_U1000R2V_MONO,
                       AMPACITE_U1000R2V_TRI):
            self.assertEqual(tuple(s for s, _ in bareme), SECTIONS_MM2)
            # Intensité admissible strictement croissante avec la section.
            valeurs = [iz for _, iz in bareme]
            self.assertEqual(valeurs, sorted(valeurs))
            self.assertEqual(len(valeurs), len(set(valeurs)))

    def test_le_cable_solaire_admet_plus_que_le_cable_ac(self):
        """H1Z2Z2-K est admis à 120 °C d'âme : à section égale il porte plus."""
        for section in SECTIONS_MM2:
            self.assertGreater(ampacite(section, AMPACITE_H1Z2Z2K),
                               ampacite(section, AMPACITE_U1000R2V_TRI))

    def test_hors_bareme_rend_none(self):
        self.assertIsNone(ampacite(1.5))
        self.assertIsNone(ampacite(35.0))

    def test_la_chute_suit_la_formule(self):
        """u = 2 × ρ × L × I / S, calculé à la main dans le test."""
        attendu = 2 * RHO_CUIVRE_20C * 30.0 * 13.0 / 6.0
        self.assertAlmostEqual(chute_tension_v(30.0, 13.0, 6.0), attendu,
                               places=12)
        self.assertAlmostEqual(
            chute_tension_pct(30.0, 13.0, 6.0, 408.0),
            attendu / 408.0 * 100.0, places=12)

    def test_le_triphase_utilise_racine_de_trois(self):
        mono = chute_tension_v(40.0, 30.0, 10.0, coefficient=2.0)
        tri = chute_tension_v(40.0, 30.0, 10.0, coefficient=math.sqrt(3.0))
        self.assertAlmostEqual(tri / mono, math.sqrt(3.0) / 2.0, places=12)

    def test_section_nulle_ne_divise_pas_par_zero(self):
        self.assertEqual(chute_tension_v(30.0, 13.0, 0.0), 0.0)
        self.assertEqual(chute_tension_pct(30.0, 13.0, 6.0, 0.0), 0.0)


class LaSectionGranditAvecLaLongueur(unittest.TestCase):
    def test_monotonie_stricte_sur_la_proposition(self):
        sections = []
        for longueur in (10.0, 40.0, 80.0, 150.0):
            proposee = proposer_section(
                courant_ib_a=13.0, longueur_m=longueur, tension_v=408.0,
                cible_pct=CHUTE_CIBLE_DC_PCT)
            sections.append(proposee.section_mm2)
        self.assertEqual(sections, sorted(sections))
        self.assertGreater(sections[-1], sections[0])

    def test_sur_une_longue_liaison_c_est_la_chute_qui_tranche(self):
        proposee = proposer_section(
            courant_ib_a=13.0, longueur_m=150.0, tension_v=408.0,
            cible_pct=CHUTE_CIBLE_DC_PCT)
        self.assertEqual(proposee.critere, CRITERE_CHUTE)
        self.assertGreater(proposee.section_par_chute_mm2,
                           proposee.section_par_echauffement_mm2)

    def test_sur_une_liaison_courte_c_est_l_echauffement_qui_tranche(self):
        proposee = proposer_section(
            courant_ib_a=90.0, longueur_m=2.0, tension_v=400.0,
            cible_pct=CHUTE_CIBLE_AC_PCT, bareme=AMPACITE_U1000R2V_TRI,
            coefficient=math.sqrt(3.0))
        self.assertGreaterEqual(proposee.iz_a, 90.0)
        self.assertGreaterEqual(proposee.section_par_echauffement_mm2,
                                proposee.section_par_chute_mm2)

    def test_la_cible_intenable_est_signalee_pas_dissimulee(self):
        proposee = proposer_section(
            courant_ib_a=13.0, longueur_m=2000.0, tension_v=408.0,
            cible_pct=CHUTE_CIBLE_DC_PCT)
        self.assertTrue(proposee.hors_bareme)
        self.assertEqual(proposee.section_mm2, SECTIONS_MM2[-1])

    def test_le_calibre_de_protection_peut_imposer_la_section(self):
        """Iz doit tenir In, pas seulement Ib (NF C 15-100 §433.1)."""
        sans = proposer_section(courant_ib_a=17.0, longueur_m=5.0,
                                tension_v=408.0, cible_pct=CHUTE_CIBLE_DC_PCT)
        avec = proposer_section(courant_ib_a=17.0, longueur_m=5.0,
                                tension_v=408.0, cible_pct=CHUTE_CIBLE_DC_PCT,
                                calibre_in_a=63.0)
        self.assertGreater(avec.section_mm2, sans.section_mm2)
        self.assertGreaterEqual(avec.iz_a, 63.0)


class ChaineIbInIz(unittest.TestCase):
    def test_la_regle_accepte_une_chaine_ordonnee(self):
        conforme, motif = verifier_ib_in_iz(17.0, 25.0, 41.0)
        self.assertTrue(conforme)
        self.assertEqual(motif, "")

    def test_ib_au_dessus_du_calibre_est_refuse(self):
        conforme, motif = verifier_ib_in_iz(30.0, 25.0, 41.0)
        self.assertFalse(conforme)
        self.assertIn("Ib", motif)

    def test_calibre_au_dessus_de_l_ampacite_est_refuse(self):
        conforme, motif = verifier_ib_in_iz(17.0, 50.0, 41.0)
        self.assertFalse(conforme)
        self.assertIn("chaufferait", motif)

    def test_sans_protection_la_regle_se_reduit_a_ib_sous_iz(self):
        self.assertTrue(verifier_ib_in_iz(17.0, None, 41.0)[0])
        self.assertFalse(verifier_ib_in_iz(60.0, None, 41.0)[0])


class CablesDeLInstallation(unittest.TestCase):
    def test_les_deux_cables_sont_produits_et_conformes(self):
        resultat = _cables(_entree())
        self.assertEqual(resultat.bloquants, ())
        dc, ac = _cable(resultat, "W1"), _cable(resultat, "W2")
        self.assertIsNotNone(dc)
        self.assertIsNotNone(ac)
        for cable in (dc, ac):
            self.assertTrue(cable.conforme, cable.repere)
            self.assertTrue(verifier_ib_in_iz(cable.ib_a, cable.in_a,
                                              cable.iz_a)[0], cable.repere)
            self.assertLessEqual(cable.chute_tension_pct, cable.chute_max_pct)
            self.assertIn("NF C 15-100", cable.regle_source)

    def test_le_cable_dc_se_dimensionne_sur_1_25_isc(self):
        entree = _entree()
        dc = _cable(_cables(entree), "W1")
        self.assertAlmostEqual(
            dc.ib_a, entree.module.isc_a * COEFF_ISC_DIMENSIONNEMENT, places=9)

    def test_deux_conducteurs_par_chaine(self):
        resultat = _cables(_entree(nb_modules=24, longueur=12))
        self.assertEqual(_cable(resultat, "W1").nb_conducteurs, 4)  # 2 chaînes

    def test_le_triphase_change_le_bareme_et_le_nombre_de_conducteurs(self):
        ac = _cable(_cables(_entree(phases=3, ac_kw=20.0)), "W2")
        self.assertEqual(ac.nb_conducteurs, 5)
        self.assertIn("triphasé", ac.designation)
        self.assertEqual(ac.iz_a, ampacite(ac.section_mm2,
                                           AMPACITE_U1000R2V_TRI))

    def test_une_liaison_dc_demesuree_est_bloquante(self):
        resultat = _cables(_entree(dc_m=1200.0))
        self.assertTrue(any("câble DC" in b and "chute de tension" in b
                            for b in resultat.bloquants))
        self.assertFalse(_cable(resultat, "W1").conforme)

    def test_une_longue_liaison_grossit_la_section_dc(self):
        court = _cable(_cables(_entree(dc_m=10.0)), "W1")
        long_ = _cable(_cables(_entree(dc_m=120.0)), "W1")
        self.assertGreater(long_.section_mm2, court.section_mm2)
        self.assertLessEqual(long_.chute_tension_pct, CHUTE_MAX_DC_PCT)

    def test_le_critere_dimensionnant_est_nomme(self):
        for cable in _cables(_entree()).cables:
            self.assertTrue(cable.critere_dimensionnant)

    def test_installation_vide_ne_produit_aucun_cable(self):
        entree = EntreeElectrique(
            module=SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                              pmax_wc=550.0),
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                                  v_max_abs=1000.0, i_max_mppt_a=26.0,
                                  ac_kw=0.0))
        self.assertEqual(_cables(entree).cables, ())
