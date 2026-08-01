# -*- coding: utf-8 -*-
"""AOF54 — recommandations applicables : le gain est REJOUÉ, jamais estimé."""

import unittest
from functools import lru_cache

from core.calepinage.obstacles import appliquer_regles
from core.calepinage.recommandations import (
    PLAFOND_RECOMMANDATIONS,
    EntreeMoteur,
    appliquer_patch,
    proposer,
)
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    Axe,
    Confiance,
    Parametres,
    Provenance,
)
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES
from core.tests.test_calepinage_optimum import (
    RIVES_AO,
    obstacles_aile_l,
    surface_aile_l,
)

CATALOGUE = (KIT_AO_PORTRAIT, KIT_AO_PAYSAGE)


def _entree_aile_l(kits=(KIT_AO_PORTRAIT,)):
    return EntreeMoteur(
        surface=surface_aile_l(),
        parametres=Parametres(kits=kits, rives=RIVES_AO, allee_m=0.60,
                              pas_recherche_m=0.01, engagement_modules=152),
        obstacles=obstacles_aile_l())


@lru_cache(maxsize=2)
def _propositions():
    """Le balayage rejoue une vingtaine de DP : on ne le relance pas par test."""
    return proposer(_entree_aile_l(), catalogue_kits=CATALOGUE)


class LAileLProposeLesKitsMixtes(unittest.TestCase):
    def _par_code(self, code):
        for proposition in _propositions():
            if proposition.code == code:
                return proposition
        self.fail("recommandation %s absente" % code)

    def test_la_reference_est_celle_du_script_temoin(self):
        self.assertEqual(_entree_aile_l().compter(), 148)

    def test_les_kits_mixtes_ressortent_avec_leur_gain_recalcule(self):
        """Réconcilié : 148 → 172, soit +24 modules exactement."""
        proposition = self._par_code("KITS_MIXTES")
        self.assertEqual(proposition.gain_modules, 24)
        self.assertAlmostEqual(proposition.gain_kwc, 24 * 0.625, delta=1e-9)
        self.assertIs(proposition.confiance, Confiance.HAUTE)

    def test_appliquer_le_patch_reproduit_le_resultat_annonce(self):
        proposition = self._par_code("KITS_MIXTES")
        entree = _entree_aile_l()
        patchee = appliquer_patch(entree, proposition.patch_entree, CATALOGUE)
        self.assertEqual(patchee.compter(),
                         entree.compter() + proposition.gain_modules)

    def test_l_arbitrage_de_grect_vaut_8_modules(self):
        """Le script témoin l'annonce : « +8 modules s'il est écarté »."""
        self.assertEqual(self._par_code("ARBITRER_GRECT").gain_modules, 8)

    def test_l_arbitrage_du_pan_vaut_4_modules(self):
        """Le script témoin l'annonce : « +4 si l'angle est droit »."""
        self.assertEqual(self._par_code("ARBITRER_PAN").gain_modules, 4)

    def test_chaque_emprise_non_mesuree_est_arbitree(self):
        codes = {p.code for p in _propositions()}
        for o in obstacles_aile_l():
            if o.provenance in (Provenance.PLAN, Provenance.DEVINE):
                self.assertIn("ARBITRER_%s" % o.repere, codes)

    def test_l_impact_est_chiffre_des_deux_cotes(self):
        proposition = self._par_code("ARBITRER_GRECT")
        self.assertIn("retirée", proposition.cout_qualitatif)
        self.assertIn("confirmée", proposition.cout_qualitatif)

    def test_la_question_a_poser_est_pre_remplie_de_son_impact(self):
        for proposition in _propositions():
            self.assertTrue(proposition.question_a_poser)
            self.assertTrue(any(c.isdigit()
                                for c in proposition.question_a_poser))

    def test_les_propositions_sont_triees_par_gain(self):
        gains = [p.gain_modules for p in _propositions()]
        self.assertEqual(gains, sorted(gains, reverse=True))

    def test_le_balayage_est_cape(self):
        self.assertLessEqual(len(_propositions()), PLAFOND_RECOMMANDATIONS)
        self.assertLessEqual(len(proposer(_entree_aile_l(),
                                          catalogue_kits=CATALOGUE,
                                          plafond=3)), 3)


class AucuneRecommandationSansGainRecalcule(unittest.TestCase):
    def test_toute_recommandation_porte_un_patch_applicable(self):
        entree = _entree_aile_l()
        reference = entree.compter()
        for proposition in _propositions():
            self.assertTrue(proposition.patch_entree,
                            "recommandation sans patch : %s" % proposition.code)
            patchee = appliquer_patch(entree, proposition.patch_entree,
                                      CATALOGUE)
            self.assertEqual(patchee.compter() - reference,
                             proposition.gain_modules,
                             "gain non reproductible : %s" % proposition.code)


class ApplicationDesPatchs(unittest.TestCase):
    def setUp(self):
        self.surface = SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                        largeur_m=25.62, rives=RIVES_AO)
        self.entree = EntreeMoteur(
            surface=self.surface,
            parametres=Parametres(kits=(KIT_AO_PORTRAIT,), rives=RIVES_AO,
                                  allee_m=0.60, pas_recherche_m=0.01),
            obstacles=appliquer_regles(ECOLE_OBSTACLES))

    def test_patch_allee(self):
        patchee = appliquer_patch(self.entree, (("allee_m", "1.90"),))
        self.assertAlmostEqual(patchee.parametres.allee_m, 1.90)
        self.assertAlmostEqual(self.entree.parametres.allee_m, 0.60)

    def test_patch_kits(self):
        patchee = appliquer_patch(self.entree,
                                  (("kits", "AO_PORTRAIT+AO_PAYSAGE"),),
                                  CATALOGUE)
        self.assertEqual(len(patchee.parametres.kits), 2)

    def test_patch_kit_inconnu_leve(self):
        with self.assertRaises(KeyError):
            appliquer_patch(self.entree, (("kits", "INEXISTANT"),), CATALOGUE)

    def test_patch_rive(self):
        patchee = appliquer_patch(self.entree, (("rive_laterale_m", "0.30"),))
        self.assertAlmostEqual(patchee.parametres.rives.laterale_m, 0.30)
        self.assertAlmostEqual(patchee.surface.rives.laterale_m, 0.30)

    def test_patch_ecarter_et_confirmer(self):
        ecarte = appliquer_patch(self.entree, (("ecarter", "GENE"),))
        vise = [o for o in ecarte.obstacles if o.repere == "GENE"][0]
        self.assertIs(vise.provenance, Provenance.ECARTE)
        confirme = appliquer_patch(self.entree, (("confirmer", "GENE"),))
        vise = [o for o in confirme.obstacles if o.repere == "GENE"][0]
        self.assertIs(vise.provenance, Provenance.RELEVE)

    def test_patch_axe(self):
        patchee = appliquer_patch(self.entree,
                                  (("axe_rangee", "EST_OUEST"),))
        self.assertIs(patchee.parametres.axe_rangee, Axe.EST_OUEST)

    def test_cle_de_patch_inconnue_leve(self):
        with self.assertRaises(KeyError):
            appliquer_patch(self.entree, (("couleur", "vert"),))

    def test_le_patch_ne_mute_jamais_l_entree(self):
        avant = self.entree.parametres.allee_m
        appliquer_patch(self.entree, (("allee_m", "1.90"),))
        self.assertAlmostEqual(self.entree.parametres.allee_m, avant)


class ContreEpreuveDeKit(unittest.TestCase):
    def test_un_kit_seul_ne_bat_jamais_le_jeu_mixte(self):
        """``assert n_alt <= n_show`` du script d'origine, remonté en moteur."""
        entree = _entree_aile_l()
        mixte = appliquer_patch(entree,
                                (("kits", "AO_PORTRAIT+AO_PAYSAGE"),),
                                CATALOGUE).compter()
        for kit in CATALOGUE:
            seul = appliquer_patch(entree, (("kits", kit.code),),
                                   CATALOGUE).compter()
            self.assertLessEqual(seul, mixte, "kit %s bat le mixte" % kit.code)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
