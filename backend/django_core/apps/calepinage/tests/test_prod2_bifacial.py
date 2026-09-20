"""CAL141 — le gain bifacial n'existe que s'il est SOURÇABLE.

Ce que ces tests tiennent :

* un seul paramètre manquant ⇒ AUCUN gain, et la raison NOMME le paramètre ;
* le gain est un POSTE séparé, jamais fondu dans une production ;
* la physique va dans le bon sens (albédo, hauteur, écartement).

Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.bifacial import (
    PARAMETRES_REQUIS, gain_bifacial, poste_bifacial,
)

#: Un jeu COMPLET — fiche bifaciale, albédo saisi, pose surélevée. Les
#: valeurs servent la mécanique, elles ne chiffrent aucun client.
COMPLET = {
    'bifacialite_pct': 70.0,
    'albedo': 0.25,
    'source_albedo': 'saisie',
    'hauteur_pose_m': 1.0,
    'taux_occupation': 0.5,
    'pas_rangee_m': 4.0,
    'inclinaison_deg': 15.0,
}


class ParametreManquantTest(unittest.TestCase):

    def test_chaque_parametre_manquant_empeche_le_calcul_et_est_nomme(self):
        for cle, libelle in PARAMETRES_REQUIS:
            with self.subTest(parametre=cle):
                entree = dict(COMPLET)
                entree[cle] = None
                resultat = gain_bifacial(**entree)
                self.assertFalse(resultat['calculable'])
                self.assertIsNone(resultat['gain_pct'])
                self.assertIn(libelle, resultat['manquants'])
                self.assertIn(libelle, resultat['motif'])

    def test_sans_inclinaison_aucun_facteur_de_vue_donc_aucun_gain(self):
        resultat = gain_bifacial(**dict(COMPLET, inclinaison_deg=None))
        self.assertFalse(resultat['calculable'])
        self.assertIn('inclinaison', resultat['motif'])

    def test_aucun_albedo_par_defaut_n_est_fabrique(self):
        """Le cas qui compte : la fiche est bifaciale, le sol est inconnu."""
        resultat = gain_bifacial(**dict(COMPLET, albedo=None))
        self.assertFalse(resultat['calculable'])
        self.assertEqual(resultat['facteurs'], {})

    def test_un_albedo_hors_bornes_est_refuse_sans_gain(self):
        resultat = gain_bifacial(**dict(COMPLET, albedo=4.0))
        self.assertFalse(resultat['calculable'])
        self.assertIn('albédo', resultat['motif'])


class CalculTest(unittest.TestCase):

    def test_le_gain_est_calcule_et_porte_ses_facteurs(self):
        resultat = gain_bifacial(**COMPLET)
        self.assertTrue(resultat['calculable'])
        self.assertGreater(resultat['gain_pct'], 0.0)
        for cle in ('bifacialite_pct', 'albedo', 'hauteur_pose_m',
                    'taux_occupation', 'facteur_de_vue_arriere_sol',
                    'fraction_de_sol_vue'):
            self.assertIn(cle, resultat['facteurs'])

    def test_un_sol_plus_clair_donne_plus_de_gain(self):
        sombre = gain_bifacial(**dict(COMPLET, albedo=0.12))
        clair = gain_bifacial(**dict(COMPLET, albedo=0.50))
        self.assertGreater(clair['gain_pct'], sombre['gain_pct'])

    def test_une_pose_plus_haute_voit_moins_la_bande_de_sol_proche(self):
        """La fraction ANGULAIRE de la bande libre décroît avec la hauteur."""
        bas = gain_bifacial(**dict(COMPLET, hauteur_pose_m=0.5))
        haut = gain_bifacial(**dict(COMPLET, hauteur_pose_m=3.0))
        self.assertGreater(bas['facteurs']['fraction_de_sol_vue'],
                           haut['facteurs']['fraction_de_sol_vue'])

    def test_un_champ_plus_dense_laisse_moins_de_sol_libre(self):
        aere = gain_bifacial(**dict(COMPLET, taux_occupation=0.3))
        dense = gain_bifacial(**dict(COMPLET, taux_occupation=0.8))
        self.assertGreater(aere['gain_pct'], dense['gain_pct'])

    def test_un_module_monofacial_ne_gagne_rien(self):
        resultat = gain_bifacial(**dict(COMPLET, bifacialite_pct=0.0))
        self.assertTrue(resultat['calculable'])
        self.assertEqual(resultat['gain_pct'], 0.0)

    def test_le_mismatch_arriere_saisi_reduit_le_gain(self):
        brut = gain_bifacial(**COMPLET)
        net = gain_bifacial(**dict(COMPLET, mismatch_arriere_pct=10.0))
        self.assertAlmostEqual(net['gain_pct'], brut['gain_pct'] * 0.9,
                               places=3)

    def test_sans_mismatch_saisi_l_hypothese_est_annoncee(self):
        resultat = gain_bifacial(**COMPLET)
        self.assertTrue(any('mismatch' in h for h in resultat['hypotheses']))
        self.assertIn('mismatch', resultat['motif'])

    def test_un_albedo_sans_source_est_publie_non_source(self):
        resultat = gain_bifacial(**dict(COMPLET, source_albedo=None))
        self.assertTrue(resultat['calculable'])
        self.assertIsNone(resultat['facteurs']['albedo_source'])
        self.assertTrue(any('source' in h for h in resultat['hypotheses']))


class PosteSepareTest(unittest.TestCase):

    def test_le_gain_est_un_poste_nomme_jamais_une_perte(self):
        poste, diagnostic = poste_bifacial(**COMPLET)
        self.assertEqual(poste['poste'], 'gain_bifacial')
        self.assertIn('gain_pct', poste)
        # Un gain n'a PAS de clé ``pct`` : il ne peut donc pas être avalé par
        # la somme des pertes envoyée à PVGIS (CAL238).
        self.assertNotIn('pct', poste)
        self.assertEqual(poste['gain_pct'], diagnostic['gain_pct'])

    def test_sans_source_aucun_poste_n_est_publie(self):
        poste, diagnostic = poste_bifacial(**dict(COMPLET, albedo=None))
        self.assertIsNone(poste)
        self.assertFalse(diagnostic['calculable'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
