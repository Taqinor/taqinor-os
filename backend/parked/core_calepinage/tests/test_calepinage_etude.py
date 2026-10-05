# -*- coding: utf-8 -*-
"""AOF55 — l'étude multi-variantes et son comparatif CALCULÉ."""

import unittest
from functools import lru_cache

from core.calepinage.etude import Etude, construire_variante
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.recommandations import EntreeMoteur
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    Parametres,
    Rives,
    remplacer,
)
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)


def _entree(allee=0.60, kits=(KIT_AO_PORTRAIT,)):
    return EntreeMoteur(
        surface=SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                 largeur_m=25.62, rives=RIVES_AO),
        parametres=Parametres(kits=kits, rives=RIVES_AO, allee_m=allee,
                              pas_recherche_m=0.01, engagement_modules=288),
        obstacles=appliquer_regles(ECOLE_OBSTACLES))


@lru_cache(maxsize=1)
def _etude():
    """Trois variantes de l'école : allée mini, allée de maintenance, mixte."""
    variantes = (
        construire_variante("MINI", "allées 0,60 (minimum)", _entree(0.60)),
        construire_variante("MAINTENANCE", "allées 1,90 offertes",
                            _entree(1.90)),
        construire_variante("MIXTE", "kits mixtes autorisés",
                            _entree(0.60, (KIT_AO_PORTRAIT, KIT_AO_PAYSAGE)),
                            avec_sensibilites=False),
    )
    return Etude(repere="BAT_C_ECOLE", variantes=variantes,
                 code_retenue="MAINTENANCE")


class UneEtudeATroisVariantes(unittest.TestCase):
    def test_le_comparatif_est_coherent(self):
        comparatif = _etude().comparatif
        self.assertEqual(len(comparatif), 3)
        for ligne in comparatif:
            self.assertGreater(ligne.modules, 0)
            self.assertAlmostEqual(ligne.kwc, ligne.modules * 0.625,
                                   delta=1e-6)
            self.assertTrue(ligne.kits)
            self.assertTrue(ligne.verdict)

    def test_la_retenue_est_explicite(self):
        etude = _etude()
        self.assertEqual(etude.retenue.code, "MAINTENANCE")
        retenues = [ligne for ligne in etude.comparatif if ligne.retenue]
        self.assertEqual(len(retenues), 1)
        self.assertEqual(retenues[0].code, "MAINTENANCE")

    def test_l_allee_de_maintenance_ne_coute_aucun_module(self):
        par_code = {ligne.code: ligne for ligne in _etude().comparatif}
        self.assertEqual(par_code["MINI"].modules,
                         par_code["MAINTENANCE"].modules)
        self.assertAlmostEqual(par_code["MAINTENANCE"].allee_m, 1.90)

    def test_le_comparatif_porte_les_marges_et_le_plancher(self):
        for ligne in _etude().comparatif:
            self.assertGreaterEqual(ligne.marge_troncon_cm, 0.0)
            self.assertGreaterEqual(ligne.marge_bande_cm, 0.0)
            self.assertLessEqual(ligne.plancher, ligne.modules)

    def test_la_meilleure_n_est_pas_forcement_la_retenue(self):
        etude = _etude()
        self.assertIsNotNone(etude.meilleure)
        self.assertGreaterEqual(etude.meilleure.modules, etude.retenue.modules)


class ChangerUneEntreeInvalideLeComparatif(unittest.TestCase):
    def test_le_comparatif_est_recalcule_a_la_lecture(self):
        etude = _etude()
        avant = etude.comparatif
        modifiee = construire_variante("MINI", "allées 1,00", _entree(1.00),
                                       avec_sensibilites=False)
        apres = etude.avec_variante(modifiee).comparatif
        self.assertNotEqual([ligne.allee_m for ligne in avant],
                            [ligne.allee_m for ligne in apres])

    def test_l_empreinte_change_avec_l_entree(self):
        etude = _etude()
        modifiee = construire_variante("MINI", "allées 1,00", _entree(1.00),
                                       avec_sensibilites=False)
        self.assertNotEqual(etude.empreinte,
                            etude.avec_variante(modifiee).empreinte)

    def test_l_empreinte_est_stable_a_entree_identique(self):
        self.assertEqual(_etude().empreinte, _etude().empreinte)

    def test_une_etude_ne_se_mute_pas(self):
        etude = _etude()
        codes_avant = tuple(v.code for v in etude.variantes)
        etude.avec_variante(construire_variante("NEUVE", "x", _entree(1.20),
                                                avec_sensibilites=False))
        self.assertEqual(tuple(v.code for v in etude.variantes), codes_avant)

    def test_retenir_rend_une_nouvelle_etude(self):
        etude = _etude()
        autre = etude.retenir("MINI")
        self.assertEqual(etude.retenue.code, "MAINTENANCE")
        self.assertEqual(autre.retenue.code, "MINI")


class ContratDeLEtude(unittest.TestCase):
    def test_codes_dupliques_refuses(self):
        variante = construire_variante("A", "x", _entree(1.20),
                                       avec_sensibilites=False)
        with self.assertRaises(ValueError):
            Etude(repere="E", variantes=(variante, variante))

    def test_retenue_inconnue_refusee(self):
        variante = construire_variante("A", "x", _entree(1.20),
                                       avec_sensibilites=False)
        with self.assertRaises(ValueError):
            Etude(repere="E", variantes=(variante,), code_retenue="Z")

    def test_etude_sans_retenue(self):
        variante = construire_variante("A", "x", _entree(1.20),
                                       avec_sensibilites=False)
        etude = Etude(repere="E", variantes=(variante,))
        self.assertIsNone(etude.retenue)
        self.assertFalse(etude.comparatif[0].retenue)

    def test_etude_vide(self):
        self.assertIsNone(Etude(repere="E", variantes=()).meilleure)

    def test_une_variante_porte_son_optimalite(self):
        variante = construire_variante("A", "x", _entree(1.20),
                                       avec_sensibilites=False)
        self.assertTrue(variante.optimal)
        self.assertTrue(variante.empreinte)

    def test_les_parametres_de_la_variante_restent_immuables(self):
        entree = _entree(1.20)
        construire_variante("A", "x", entree, avec_sensibilites=False)
        self.assertAlmostEqual(entree.parametres.allee_m, 1.20)
        self.assertAlmostEqual(
            remplacer(entree.parametres, allee_m=0.60).allee_m, 0.60)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
