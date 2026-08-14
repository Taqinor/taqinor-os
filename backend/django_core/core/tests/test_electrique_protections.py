# -*- coding: utf-8 -*-
"""PV35 — protections : les règles sont testées SUR LEURS SEUILS.

Une règle « à partir de 3 chaînes » ne se teste pas avec 1 et 10 : elle se teste
avec 2 et 3. Idem pour le parafoudre « au-delà de 10 m » : 9 m et 11 m. C'est le
seul endroit où une erreur de comparaison (``>`` au lieu de ``>=``) se voit.

Aucune base de données : ``unittest`` pur.
"""

import unittest

from core.electrique.chaines import concevoir_chaines
from core.electrique.onduleurs import dimensionner_onduleurs
from core.electrique.protections import (
    CALIBRES_FUSIBLE_GPV_A,
    FACTEUR_FUSIBLE_MAX,
    FACTEUR_FUSIBLE_MIN,
    LONGUEUR_DC_SANS_PARAFOUDRE_M,
    SENSIBILITE_DDR_MA,
    SEUIL_CHAINES_PARALLELES_FUSIBLE,
    calibre_disjoncteur,
    calibre_fusible_chaine,
    concevoir_protections,
    courant_emploi_ac,
)
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)

NORMES = ("NF C 15-100", "UTE C 15-712-1", "IEC 62548", "IEC 62109",
          "IEC 60269")


def _entree(nb_modules=18, longueur=6, n_mppt=1, dc_m=15.0, ac_m=10.0,
            phases=1, ac_kw=10.0, isc=13.8, **kwargs):
    return EntreeElectrique(
        module=SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=isc, imp_a=13.0,
                          pmax_wc=550.0),
        onduleur=SpecOnduleur(n_mppt=n_mppt, mppt_v_min=120.0,
                              mppt_v_max=850.0, v_max_abs=1000.0,
                              i_max_mppt_a=60.0, ac_kw=ac_kw, phases=phases,
                              v_demarrage_v=90.0),
        groupes=(GroupePan("Sud", nb_modules, 180.0, 15.0),),
        dc_m=dc_m, ac_m=ac_m, phases=phases,
        longueur_chaine_forcee=longueur, **kwargs)


def _protections(entree):
    chaines = concevoir_chaines(entree)
    evaluation = dimensionner_onduleurs(entree)
    return concevoir_protections(entree, chaines, evaluation)


def _repere(resultat, repere):
    for protection in resultat.protections:
        if protection.repere == repere:
            return protection
    return None


class FusibleDeChaineAuSeuil(unittest.TestCase):
    def test_deux_chaines_en_parallele_ne_prennent_pas_de_fusible(self):
        resultat = _protections(_entree(nb_modules=24, longueur=12, n_mppt=1))
        self.assertIsNone(_repere(resultat, "F1"))
        self.assertFalse(resultat.fusibles_exiges)
        # La règle examinée sans se déclencher est une JUSTIFICATION (elle va
        # dans la note de calcul), pas une alerte de l'écran.
        self.assertTrue(any("NON exigés" in j
                            for j in resultat.justifications))
        self.assertFalse(any("NON exigés" in a for a in resultat.alertes))

    def test_trois_chaines_en_parallele_prennent_un_fusible(self):
        resultat = _protections(_entree(nb_modules=18, longueur=6, n_mppt=1))
        fusible = _repere(resultat, "F1")
        self.assertIsNotNone(fusible)
        self.assertTrue(resultat.fusibles_exiges)
        # Deux pôles par chaîne (+ et −) sur 3 chaînes.
        self.assertEqual(fusible.quantite, 6)
        self.assertIn("IEC 62548", fusible.regle_source)

    def test_le_seuil_est_bien_trois(self):
        self.assertEqual(SEUIL_CHAINES_PARALLELES_FUSIBLE, 3)

    def test_les_chaines_reparties_sur_deux_mppt_ne_sont_pas_en_parallele(self):
        """4 chaînes sur 2 entrées = 2 en parallèle par entrée → pas de fusible."""
        resultat = _protections(_entree(nb_modules=24, longueur=6, n_mppt=2))
        self.assertIsNone(_repere(resultat, "F1"))

    def test_calibre_dans_la_fourchette_1_5_a_2_4_isc(self):
        for isc in (9.0, 11.0, 13.8, 15.5):
            calibre, motif = calibre_fusible_chaine(isc)
            self.assertEqual(motif, "", isc)
            self.assertIn(calibre, [float(c) for c in CALIBRES_FUSIBLE_GPV_A])
            self.assertGreaterEqual(calibre, FACTEUR_FUSIBLE_MIN * isc - 1e-9)
            self.assertLessEqual(calibre, FACTEUR_FUSIBLE_MAX * isc + 1e-9)

    def test_calibre_hors_barreme_est_dit_pas_dissimule(self):
        calibre, motif = calibre_fusible_chaine(0.5)   # 0,75 A … 1,2 A
        self.assertIsNotNone(calibre)
        self.assertIn("2,4 × Isc", motif)

    def test_isc_inconnu_ne_leve_pas(self):
        calibre, motif = calibre_fusible_chaine(0.0)
        self.assertIsNone(calibre)
        self.assertTrue(motif)


class ParafoudreDcAuSeuil(unittest.TestCase):
    def test_neuf_metres_ne_declenchent_pas_le_parafoudre(self):
        resultat = _protections(_entree(dc_m=9.0))
        self.assertIsNone(_repere(resultat, "PDC1"))
        self.assertTrue(any("parafoudre DC non exigé" in j
                            for j in resultat.justifications))

    def test_onze_metres_declenchent_le_parafoudre(self):
        resultat = _protections(_entree(dc_m=11.0))
        parafoudre = _repere(resultat, "PDC1")
        self.assertIsNotNone(parafoudre)
        self.assertIn("UTE C 15-712-1", parafoudre.regle_source)
        self.assertIn("11", parafoudre.regle_source)

    def test_le_seuil_est_bien_dix_metres(self):
        self.assertEqual(LONGUEUR_DC_SANS_PARAFOUDRE_M, 10.0)
        self.assertIsNone(_repere(_protections(_entree(dc_m=10.0)), "PDC1"))

    def test_zone_keraunique_impose_le_parafoudre_a_neuf_metres(self):
        resultat = _protections(_entree(dc_m=9.0, zone_keraunique=True))
        parafoudre = _repere(resultat, "PDC1")
        self.assertIsNotNone(parafoudre)
        self.assertIn("kéraunique", parafoudre.regle_source)


class SectionneurEtDisjoncteur(unittest.TestCase):
    def test_le_sectionneur_dc_est_toujours_la(self):
        for dc_m in (5.0, 25.0):
            resultat = _protections(_entree(dc_m=dc_m))
            self.assertIsNotNone(_repere(resultat, "QDC1"), dc_m)

    def test_courant_d_emploi_mono_et_tri(self):
        self.assertAlmostEqual(courant_emploi_ac(6.0, 1), 6000.0 / 230.0,
                               places=6)
        self.assertAlmostEqual(courant_emploi_ac(20.0, 3),
                               20000.0 / (400.0 * 3 ** 0.5), places=6)
        self.assertEqual(courant_emploi_ac(0.0, 1), 0.0)

    def test_calibre_normalise_immediatement_superieur_a_ib(self):
        self.assertEqual(calibre_disjoncteur(26.1), 32.0)
        self.assertEqual(calibre_disjoncteur(25.0), 25.0)
        self.assertEqual(calibre_disjoncteur(0.5), 6.0)

    def test_disjoncteur_ac_mono(self):
        resultat = _protections(_entree(ac_kw=6.0, phases=1))
        disjoncteur = _repere(resultat, "QAC1")
        self.assertIn("bipolaire", disjoncteur.designation)
        self.assertEqual(resultat.calibre_ac_a, 32.0)   # Ib = 26,1 A
        self.assertGreaterEqual(resultat.calibre_ac_a, resultat.courant_ac_ib_a)

    def test_disjoncteur_ac_tri(self):
        resultat = _protections(_entree(ac_kw=20.0, phases=3))
        disjoncteur = _repere(resultat, "QAC1")
        self.assertIn("tétrapolaire", disjoncteur.designation)
        self.assertIn("400", disjoncteur.calibre)
        self.assertEqual(resultat.calibre_ac_a, 32.0)   # Ib = 28,9 A

    def test_parafoudre_ac_present(self):
        self.assertIsNotNone(_repere(_protections(_entree()), "PAC1"))


class DifferentielEtTerre(unittest.TestCase):
    def test_regime_tt_impose_un_ddr_type_a_300_ma(self):
        resultat = _protections(_entree())
        ddr = _repere(resultat, "DDR1")
        self.assertIsNotNone(ddr)
        self.assertIn("type A", ddr.designation)
        self.assertIn("%d mA" % SENSIBILITE_DDR_MA, ddr.calibre)
        self.assertIn("NF C 15-100", ddr.regle_source)

    def test_hors_regime_tt_le_ddr_de_tete_est_remplace_par_une_alerte(self):
        resultat = _protections(_entree(regime="TN"))
        self.assertIsNone(_repere(resultat, "DDR1"))
        self.assertTrue(any("TN" in a for a in resultat.alertes))

    def test_mise_a_la_terre_prise_et_equipotentielle(self):
        resultat = _protections(_entree())
        self.assertIsNotNone(_repere(resultat, "T1"))
        self.assertIsNotNone(_repere(resultat, "T2"))

    def test_le_parc_batterie_prend_son_sectionnement(self):
        self.assertIsNone(_repere(_protections(_entree()), "QBAT1"))
        avec = _protections(_entree(batterie=True))
        self.assertIsNotNone(_repere(avec, "QBAT1"))


class ChaqueProtectionPorteSaSource(unittest.TestCase):
    def test_toute_protection_cite_une_norme(self):
        resultat = _protections(_entree(dc_m=20.0, batterie=True))
        self.assertTrue(resultat.protections)
        for protection in resultat.protections:
            self.assertTrue(protection.regle_source, protection.repere)
            self.assertTrue(
                any(norme in protection.regle_source for norme in NORMES),
                "%s ne cite aucune norme : %r"
                % (protection.repere, protection.regle_source))
            self.assertTrue(protection.designation)
            self.assertGreaterEqual(protection.quantite, 1)

    def test_les_reperes_sont_uniques(self):
        resultat = _protections(_entree(dc_m=20.0, batterie=True))
        reperes = [p.repere for p in resultat.protections]
        self.assertEqual(len(reperes), len(set(reperes)))

    def test_installation_vide_ne_leve_pas(self):
        entree = EntreeElectrique(
            module=SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                              pmax_wc=550.0),
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                                  v_max_abs=1000.0, i_max_mppt_a=26.0,
                                  ac_kw=0.0))
        resultat = concevoir_protections(entree, concevoir_chaines(entree),
                                         dimensionner_onduleurs(entree))
        self.assertEqual(resultat.protections, ())
