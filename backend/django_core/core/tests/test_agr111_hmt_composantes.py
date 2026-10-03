# -*- coding: utf-8 -*-
"""AGR111 — HMT par composantes (noyau pur, sans base de données).

Valeurs de référence W1-05 (recalcul vérifié) : C = 150, L = 500 m,
Q = 30 m³/h → pertes ≈ 5,2 m (Ø int. 100 mm), 15,3 m (80 mm), 94,4 m (55 mm).
"""

import unittest

from core.pompage.hydraulique import (
    CHAMP_C_HAZEN_WILLIAMS, METRES_PAR_BAR, hmt_composantes,
    pertes_hazen_williams,
)

COMPLET = dict(niveau_dynamique_m=40, denivele_m=4, longueur_conduite_m=500,
               diametre_interieur_mm=100, materiau_conduite="PEHD",
               pertes_singulieres_m=0.8, pression_service_bar=1,
               debit_m3h=30, hmt_saisie=70)


class PertesHazenWilliams(unittest.TestCase):

    def test_references_w1_05(self):
        for diametre, attendu in ((100, 5.2), (80, 15.3), (55, 94.4)):
            pertes = pertes_hazen_williams(longueur_m=500, debit_m3h=30,
                                           diametre_interieur_mm=diametre,
                                           c_hazen_williams=150)
            self.assertAlmostEqual(round(pertes, 1), attendu, places=6,
                                   msg="Ø %s mm" % diametre)

    def test_donnee_absente_rend_none(self):
        self.assertIsNone(pertes_hazen_williams(
            longueur_m=500, debit_m3h=30, diametre_interieur_mm=None,
            c_hazen_williams=150))


class HmtComposantes(unittest.TestCase):

    def test_pvc_prend_c_150_de_la_table(self):
        r = hmt_composantes(**dict(COMPLET, materiau_conduite="PVC"))
        self.assertEqual(r["source"], "calculee")
        self.assertEqual(r["composantes"]["pertes_lineaires_m"], 5.2)
        self.assertEqual(r["provenance"]["c_hazen_williams"]["detail"],
                         "hypotheses_pompage.json › hazen_williams_c_pvc_pehd")

    def test_somme_des_cinq_composantes(self):
        r = hmt_composantes(**COMPLET)
        attendu = (40 + 4 + pertes_hazen_williams(
            longueur_m=500, debit_m3h=30, diametre_interieur_mm=100,
            c_hazen_williams=150) + 0.8 + 1 * METRES_PAR_BAR)
        self.assertAlmostEqual(r["valeur_m"], round(attendu, 1), places=6)
        self.assertEqual(r["composantes"]["pression_service_m"], 10.2)
        self.assertEqual(r["alertes"], [])

    def test_materiau_sans_c_pertes_null_et_alerte(self):
        r = hmt_composantes(**dict(COMPLET, materiau_conduite="acier"))
        self.assertIsNone(r["composantes"]["pertes_lineaires_m"])
        self.assertEqual(r["source"], "saisie")
        self.assertEqual(r["valeur_m"], 70)
        self.assertIn("pertes_lineaires_m", r["manquantes"])
        self.assertEqual([a["champ"] for a in r["alertes"]],
                         [CHAMP_C_HAZEN_WILLIAMS])

    def test_materiau_hors_table_avec_c_saisi(self):
        r = hmt_composantes(**dict(COMPLET, materiau_conduite="acier",
                                   c_hazen_williams=120))
        self.assertEqual(r["source"], "calculee")
        self.assertEqual(r["provenance"]["c_hazen_williams"]["origine"],
                         "saisie")

    def test_composante_manquante_repli_saisie_annonce(self):
        r = hmt_composantes(**dict(COMPLET, pertes_singulieres_m=None))
        self.assertEqual(r["source"], "saisie")
        self.assertEqual(r["valeur_m"], 70)
        self.assertEqual(r["manquantes"], ["pertes_singulieres_m"])
        # Les composantes connues restent servies.
        self.assertEqual(r["composantes"]["niveau_dynamique_m"], 40)

    def test_niveau_dynamique_depuis_statique_et_rabattement(self):
        r = hmt_composantes(**dict(COMPLET, niveau_dynamique_m=None,
                                   niveau_statique_m=30,
                                   rabattement_specifique_m_par_m3h=0.2))
        self.assertEqual(r["composantes"]["niveau_dynamique_m"], 36.0)
        self.assertEqual(r["provenance"]["niveau_dynamique_m"]["origine"],
                         "calculee")

    def test_chemin_coefficient_frottement_reste_accepte(self):
        r = hmt_composantes(niveau_dynamique_m=40, denivele_m=0,
                            longueur_conduite_m=100,
                            coefficient_frottement=0.0001,
                            pertes_singulieres_m=0, pression_service_bar=0,
                            debit_m3h=10)
        self.assertEqual(r["source"], "calculee")
        self.assertEqual(r["composantes"]["pertes_lineaires_m"], 1.0)
        self.assertEqual(r["alertes"], [])

    def test_iteration_avec_courbe(self):
        courbe = {"debits_m3h": [0, 10, 20, 30, 40],
                  "hmt_m": [90, 85, 75, 60, 40]}
        r = hmt_composantes(**dict(COMPLET, debit_m3h=None,
                                   courbe_pompe=courbe))
        self.assertEqual(r["source"], "calculee")
        self.assertIsNotNone(r["debit_convergence_m3h"])
        self.assertGreater(r["iterations"], 0)

    def test_provenance_saisie_fournie_par_l_appelant(self):
        prov = {"origine": "lead", "detail": "mesure_visite",
                "date": "2026-10-01"}
        r = hmt_composantes(**dict(COMPLET,
                                   provenances={"niveau_dynamique_m": prov}))
        self.assertEqual(r["provenance"]["niveau_dynamique_m"], prov)
