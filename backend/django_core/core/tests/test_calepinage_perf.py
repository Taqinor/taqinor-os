# -*- coding: utf-8 -*-
"""AOF48 — performance : points de rupture, mémoïsation, budget, bench plafonné.

Le bench est un GARDE-FOU, pas une mesure de machine : il compare deux chemins
sur le MÊME runner (grille aveugle contre positions utiles) et échoue sur une
régression de plus de 50 %. Aucune valeur absolue de temps n'est codée en dur,
sinon il serait rouge sur un runner chargé.
"""

import time
import unittest

from core.calepinage.moteur import (
    compter_rangee,
    info_cache,
    pas_constant,
    positions_de_rupture,
    vider_cache,
)
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.optimum import optimiser, positions_grille
from core.calepinage.perf import (
    CONTRAT_PERFORMANCE,
    BudgetCalcul,
    caper,
    estimer_cout,
    optimiser_economique,
    positions_utiles,
)
from core.calepinage.surfaces.arc import arc_frdisi
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    Parametres,
    Rives,
)
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES
from core.tests.test_calepinage_optimum import (
    RIVES_AO,
    obstacles_aile_l,
    surface_aile_l,
)


def _parametres(kits=(KIT_AO_PORTRAIT,)):
    return Parametres(kits=kits, rives=RIVES_AO, allee_m=0.60,
                      pas_recherche_m=0.01)


def _ecole():
    return SurfaceRectangle(repere="BAT_C", longueur_m=51.10, largeur_m=25.62,
                            rives=RIVES_AO)


class PointsDeRupture(unittest.TestCase):
    def test_le_pas_est_constant_en_plan_et_variable_sur_l_arc(self):
        self.assertTrue(pas_constant(_ecole(), KIT_AO_PORTRAIT))
        self.assertFalse(pas_constant(arc_frdisi(rives=RIVES_AO),
                                      KIT_AO_PAYSAGE))

    def test_l_arc_refuse_le_raccourci_et_garde_la_grille(self):
        arc = arc_frdisi(rives=RIVES_AO)
        self.assertIsNone(positions_de_rupture(arc, (KIT_AO_PAYSAGE,)))
        parametres = _parametres((KIT_AO_PAYSAGE,))
        self.assertEqual(len(positions_utiles(arc, parametres)),
                         len(positions_grille(*arc.bornes_transversales_utiles(),
                                              parametres.pas_recherche_m)))

    def test_les_ruptures_encadrent_chaque_obstacle(self):
        ruptures = positions_de_rupture(_ecole(), (KIT_AO_PORTRAIT,),
                                        appliquer_regles(ECOLE_OBSTACLES))
        self.assertTrue(ruptures)
        self.assertIn(round(18.20 + 0.30, 6),
                      tuple(round(r, 6) for r in ruptures))

    def test_le_jeu_utile_est_plus_petit_que_la_grille_sur_un_kit(self):
        surface, parametres = surface_aile_l(), _parametres()
        utiles = positions_utiles(surface, parametres, obstacles_aile_l())
        grille = positions_grille(*surface.bornes_transversales_utiles(),
                                  parametres.pas_recherche_m)
        self.assertLess(len(utiles), len(grille))


class LesComptesNeChangentJamais(unittest.TestCase):
    """Exigence dure : l'accélération ne déplace PAS un module."""

    def test_aile_l_un_kit(self):
        surface, obstacles = surface_aile_l(), obstacles_aile_l()
        parametres = _parametres()
        self.assertEqual(optimiser(surface, parametres, obstacles).modules,
                         optimiser_economique(surface, parametres,
                                              obstacles).modules)

    def test_aile_l_deux_kits(self):
        surface, obstacles = surface_aile_l(), obstacles_aile_l()
        parametres = _parametres((KIT_AO_PORTRAIT, KIT_AO_PAYSAGE))
        self.assertEqual(optimiser(surface, parametres, obstacles).modules,
                         optimiser_economique(surface, parametres,
                                              obstacles).modules)

    def test_ecole(self):
        surface = _ecole()
        obstacles = appliquer_regles(ECOLE_OBSTACLES)
        parametres = _parametres()
        self.assertEqual(optimiser(surface, parametres, obstacles).modules,
                         optimiser_economique(surface, parametres,
                                              obstacles).modules)

    def test_arc(self):
        arc = arc_frdisi(rives=RIVES_AO)
        parametres = _parametres((KIT_AO_PAYSAGE,))
        self.assertEqual(optimiser(arc, parametres).modules,
                         optimiser_economique(arc, parametres).modules)


class Memoisation(unittest.TestCase):
    def test_le_second_appel_est_servi_par_le_cache(self):
        vider_cache()
        surface, obstacles = _ecole(), appliquer_regles(ECOLE_OBSTACLES)
        compter_rangee(surface, 0.35, KIT_AO_PORTRAIT, obstacles)
        premier = info_cache()
        compter_rangee(surface, 0.35, KIT_AO_PORTRAIT, obstacles)
        second = info_cache()
        self.assertEqual(second.hits, premier.hits + 1)
        self.assertEqual(second.misses, premier.misses)

    def test_le_cache_rend_le_meme_compte(self):
        vider_cache()
        surface, obstacles = _ecole(), appliquer_regles(ECOLE_OBSTACLES)
        premier = compter_rangee(surface, 0.35, KIT_AO_PORTRAIT, obstacles)
        second = compter_rangee(surface, 0.35, KIT_AO_PORTRAIT, obstacles)
        self.assertEqual(premier.modules, second.modules)
        self.assertEqual(premier.troncons, second.troncons)

    def test_une_entree_differente_ne_percute_pas_le_cache(self):
        vider_cache()
        surface = _ecole()
        avec = compter_rangee(surface, 13.55, KIT_AO_PORTRAIT,
                              appliquer_regles(ECOLE_OBSTACLES))
        sans = compter_rangee(surface, 13.55, KIT_AO_PORTRAIT)
        self.assertNotEqual(avec.modules, sans.modules)


class BudgetEtBascule(unittest.TestCase):
    def test_estimer_cout_dit_synchrone_sur_un_batiment(self):
        cout = estimer_cout(surface_aile_l(), _parametres(), obstacles_aile_l())
        self.assertTrue(cout.synchrone)
        self.assertIn("synchrone", cout.motif)
        self.assertGreater(cout.appels, 0)

    def test_estimer_cout_bascule_en_tache_de_fond_sur_un_site(self):
        cout = estimer_cout(surface_aile_l(), _parametres(), obstacles_aile_l(),
                            variantes=400)
        self.assertFalse(cout.synchrone)
        self.assertIn("tâche de fond", cout.motif)

    def test_le_seuil_est_un_argument_jamais_une_constante_planquee(self):
        budget = BudgetCalcul(seuil_synchrone_ms=1.0)
        self.assertFalse(estimer_cout(surface_aile_l(), _parametres(),
                                      obstacles_aile_l(), budget=budget).synchrone)

    def test_le_contrat_de_performance_est_publie(self):
        cles = tuple(cle for cle, _valeur, _texte in CONTRAT_PERFORMANCE)
        self.assertIn("apercu_ms", cles)
        self.assertIn("calcul_lourd_ms", cles)
        self.assertIn("plafond_recommandations", cles)
        for _cle, valeur, texte in CONTRAT_PERFORMANCE:
            self.assertGreater(valeur, 0)
            self.assertTrue(texte)

    def test_le_plafond_de_recommandations_est_applique(self):
        self.assertEqual(len(caper(range(100), 12)), 12)
        self.assertEqual(caper((1, 2), 12), (1, 2))
        with self.assertRaises(ValueError):
            caper((1,), -1)


def _minimum_sur_essais_a_froid(fonction, essais=3):
    """Minimum de N essais À CACHE FROID (convention ``timeit`` : le bruit
    d'un runner partagé — pause GC, vol de CPU par un shard voisin — ne fait
    qu'AJOUTER du temps à une mesure, jamais en retirer ; un seul essai peut
    être heurté, le minimum converge vers le coût réel). Chaque essai reste
    un calcul complet isolé (cache vidé avant), fidèle à l'usage réel (un
    calepinage se calcule une fois, pas en boucle chaude)."""
    meilleure_duree = None
    dernier_resultat = None
    for _ in range(essais):
        vider_cache()
        debut = time.perf_counter()
        dernier_resultat = fonction()
        duree = time.perf_counter() - debut
        if meilleure_duree is None or duree < meilleure_duree:
            meilleure_duree = duree
    return meilleure_duree, dernier_resultat


class BenchPlafonne(unittest.TestCase):
    """ROUGE si l'accélération régresse de plus de 50 % — jamais une horloge.

    2026-08-14 (PR #518, job 94644261026) : un shard CI a mesuré 0.725 s
    (économique) contre 0.154 s (aveugle) — une inversion, alors qu'aucun
    fichier de ``core/calepinage`` n'était touché par ce lot (CRM/CPQ/
    marketing) ni par aucun de ses 4 essais de CI ; le même test est passé
    sur 3 des 4 exécutions de la même branche, dont une où le shard voisin
    portait de vraies régressions sans rapport. Conclusion : bruit machine
    sur un essai unique, pas une régression — cf. le commentaire de classe
    ci-dessus, qui l'anticipait déjà. Le seuil (50 %) est INCHANGÉ ; seule
    la mesure est robustifiée par un minimum de 3 essais par chemin.
    """

    def test_le_jeu_utile_est_au_moins_deux_fois_plus_rapide(self):
        surface, obstacles = surface_aile_l(), obstacles_aile_l()
        parametres = _parametres()
        duree_aveugle, aveugle = _minimum_sur_essais_a_froid(
            lambda: optimiser(surface, parametres, obstacles))
        duree_economique, economique = _minimum_sur_essais_a_froid(
            lambda: optimiser_economique(surface, parametres, obstacles))
        self.assertEqual(aveugle.modules, economique.modules)
        self.assertLess(duree_economique, duree_aveugle * 0.5,
                        "régression de performance : le balayage sur points de "
                        "rupture doit rester au moins 2× plus rapide que le "
                        "balayage aveugle, au MEILLEUR de 3 essais chacun "
                        "(%.3f s contre %.3f s)"
                        % (duree_economique, duree_aveugle))

    def test_etude_complete_d_un_batiment_sous_deux_secondes(self):
        """Plan + 6 sensibilités + échelle (8 marches) : le budget d'AOF48."""
        surface, obstacles = surface_aile_l(), obstacles_aile_l()
        parametres = _parametres()
        vider_cache()
        debut = time.perf_counter()
        optimiser_economique(surface, parametres, obstacles)
        for degagement in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60):
            durcis = appliquer_regles(tuple(
                type(o)(repere=o.repere, x0=o.x0, x1=o.x1, y0=o.y0, y1=o.y1,
                        type_obstacle=o.type_obstacle, provenance=o.provenance,
                        degagement_m=degagement)
                for o in obstacles))
            optimiser_economique(surface, parametres, durcis)
        for allee in (0.60, 0.80, 1.00, 1.20, 1.50, 1.70, 1.90, 2.10):
            optimiser_economique(surface, Parametres(
                kits=parametres.kits, rives=RIVES_AO, allee_m=allee,
                pas_recherche_m=0.01), obstacles)
        duree = time.perf_counter() - debut
        self.assertLess(duree, 2.0,
                        "étude complète du bâtiment A en %.2f s (budget 2 s)"
                        % duree)


class RivesEtParametres(unittest.TestCase):
    def test_rives_par_defaut_du_bench(self):
        self.assertAlmostEqual(RIVES_AO.laterale_m, 0.35)
        self.assertIsInstance(Rives(), Rives)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
