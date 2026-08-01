# -*- coding: utf-8 -*-
"""AOF185 — tests de PROPRIÉTÉS / fuzz géométrique.

Les goldens verrouillent trois toitures réelles ; ils ne voient rien de ce qui
sort de ces trois-là. Ce fichier est le filet : il engendre des enveloppes, des
obstacles, des zones et des kits ALÉATOIRES BORNÉS à graine FIXE, et vérifie
sur chacun les invariants qui doivent tenir quelle que soit la géométrie :

* **compteur == poseur** — les deux chemins de code indépendants s'accordent ;
* **aucun chevauchement** (SAT), toutes les rives tenues, tous les dégagements
  tenus — c'est ``garde_fous.valider`` qui l'affirme, la même porte qu'en
  production ;
* **monotonies** — ajouter un obstacle ne peut pas augmenter le compte ;
  élargir l'allée ne peut pas l'augmenter ; une zone PRÉFÉRÉE ne le change
  jamais ;
* **déterminisme** — même entrée ⇒ même plan et même hash, le garde-fou contre
  l'instabilité flottante Windows/Linux.

Tout contre-exemple est SÉRIALISÉ en JSON reproductible dans le message
d'échec : on rejoue le cas fautif sans deviner.
"""

import json
import random
import unittest

from core.calepinage.garde_fous import valider
from core.calepinage.moteur import compter_plan
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.perf import optimiser_economique
from core.calepinage.poseur import poser_plan
from core.calepinage.serialisation import EntreeCalepinage
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    KIT_VILLA_720,
    NatureZone,
    Obstacle,
    Parametres,
    Provenance,
    Rives,
    Zone,
)

#: graine FIXE : la CI doit être reproductible au cas près.
GRAINE = 20260801
#: 500 cas pour les invariants de comptage/pose (aucun DP : ils sont rapides)
NB_CAS = 500
#: sous-ensemble pour les monotonies qui exigent un DP complet
#: (chaque cas rejoue 2 DP : le budget d'AOF48 s'applique aussi aux tests)
NB_CAS_DP = 10

KITS = (KIT_AO_PORTRAIT, KIT_AO_PAYSAGE, KIT_VILLA_720)


def _generer(rng, indice):
    """Un cas ALÉATOIRE BORNÉ, entièrement décrit par des nombres simples."""
    forme = rng.choice(("rectangle", "rectangle", "polygone"))
    longueur = round(rng.uniform(12.0, 60.0), 2)
    largeur = round(rng.uniform(8.0, 30.0), 2)
    rive = round(rng.choice((0.0, 0.35, 0.50)), 2)
    kit = rng.randrange(len(KITS))
    obstacles = []
    for j in range(rng.randrange(0, 6)):
        ox = round(rng.uniform(0.0, max(0.5, longueur - 2.0)), 2)
        oy = round(rng.uniform(0.0, max(0.5, largeur - 2.0)), 2)
        obstacles.append({
            "repere": "O%d_%d" % (indice, j),
            "x0": ox, "x1": round(ox + rng.uniform(0.3, 3.0), 2),
            "y0": oy, "y1": round(oy + rng.uniform(0.3, 3.0), 2),
            "degagement_m": round(rng.choice((0.30, 0.35, 0.50)), 2),
        })
    return {"indice": indice, "forme": forme, "longueur_m": longueur,
            "largeur_m": largeur, "rive_m": rive, "kit": kit,
            "allee_m": round(rng.choice((0.0, 0.60, 1.20, 1.90)), 2),
            "obstacles": obstacles,
            "entaille": round(rng.uniform(0.1, 0.4), 3)}


def _objets(cas, obstacles_en_plus=(), zones=()):
    kit = KITS[cas["kit"]]
    rives = Rives(laterale_m=cas["rive_m"], extremite_m=cas["rive_m"])
    longueur, largeur = cas["longueur_m"], cas["largeur_m"]
    if cas["forme"] == "rectangle":
        surface = SurfaceRectangle(repere="F%d" % cas["indice"],
                                   longueur_m=longueur, largeur_m=largeur,
                                   rives=rives)
    else:
        # un L : entaille du quart nord-est, proportion tirée au sort
        entaille_x = longueur * cas["entaille"]
        entaille_y = largeur * cas["entaille"]
        surface = SurfacePolygone(
            repere="F%d" % cas["indice"], rives=rives,
            contour=((0.0, 0.0), (longueur, 0.0),
                     (longueur, largeur - entaille_y),
                     (longueur - entaille_x, largeur - entaille_y),
                     (longueur - entaille_x, largeur), (0.0, largeur)))
    obstacles = appliquer_regles(tuple(
        Obstacle(repere=o["repere"], x0=o["x0"], x1=o["x1"], y0=o["y0"],
                 y1=o["y1"], provenance=Provenance.RELEVE,
                 degagement_m=o["degagement_m"])
        for o in list(cas["obstacles"]) + list(obstacles_en_plus)))
    parametres = Parametres(kits=(kit,), rives=rives, allee_m=cas["allee_m"],
                            pas_recherche_m=0.05,
                            axe_rangee=(KIT_AO_PORTRAIT.axe_faitage
                                        if kit is not KIT_VILLA_720
                                        else KIT_VILLA_720.axe_faitage))
    ymin, ymax = surface.bornes_transversales_utiles()
    rangees = []
    y0 = ymin
    while y0 + kit.emprise_transversale_m <= ymax + 1e-9:
        rangees.append((y0, kit))
        y0 += kit.emprise_transversale_m + max(cas["allee_m"], 0.0)
    return surface, parametres, obstacles, tuple(zones), tuple(rangees)


def _contre_exemple(cas, message):
    return "%s\ncontre-exemple reproductible :\n%s" % (
        message, json.dumps(cas, sort_keys=True, ensure_ascii=False))


class ProprietesGeometriques(unittest.TestCase):
    """500 cas à graine fixe — aucun DP, donc rapides."""

    @classmethod
    def setUpClass(cls):
        rng = random.Random(GRAINE)
        cls.cas = [_generer(rng, i) for i in range(NB_CAS)]

    def test_compteur_egale_poseur_sur_500_cas(self):
        for cas in self.cas:
            surface, _p, obstacles, zones, rangees = _objets(cas)
            if not rangees:
                continue
            plan = compter_plan(surface, rangees, obstacles, zones)
            tables = poser_plan(surface, rangees, obstacles, zones)
            kit = rangees[0][1]
            self.assertEqual(
                kit.modules_par_pas * len(tables), plan.modules,
                _contre_exemple(cas, "compteur ≠ poseur"))

    def test_tous_les_garde_fous_tiennent(self):
        """Sur un sous-ensemble : ``valider`` confronte les DEUX chemins de
        code et fait un SAT de toutes les paires de tables — c'est le contrôle
        le plus cher du moteur, 120 cas suffisent à attraper une régression."""
        for cas in self.cas[:120]:
            surface, parametres, obstacles, zones, rangees = _objets(cas)
            if not rangees:
                continue
            rapport = valider(surface, parametres, rangees, obstacles, zones,
                              strict=False)
            self.assertTrue(
                rapport.ok,
                _contre_exemple(cas, "garde-fou en échec : %s"
                                % [e.controle for e in rapport.echecs]))

    def test_determinisme_du_compte_et_du_hash(self):
        for cas in self.cas[:200]:
            surface, parametres, obstacles, zones, rangees = _objets(cas)
            if not rangees:
                continue
            premier = compter_plan(surface, rangees, obstacles, zones)
            second = compter_plan(surface, rangees, obstacles, zones)
            self.assertEqual(premier.modules, second.modules,
                             _contre_exemple(cas, "compte non déterministe"))
            entree = EntreeCalepinage(
                repere=surface.repere, surfaces=(surface,),
                kits=parametres.kits, parametres=parametres,
                obstacles=obstacles)
            self.assertEqual(entree.hash_entree, entree.hash_entree,
                             _contre_exemple(cas, "hash non déterministe"))

    def test_ajouter_un_obstacle_ne_peut_pas_augmenter_le_compte(self):
        for cas in self.cas[:200]:
            surface, _p, obstacles, zones, rangees = _objets(cas)
            if not rangees:
                continue
            avant = compter_plan(surface, rangees, obstacles, zones).modules
            surface2, _p2, obstacles2, _z2, rangees2 = _objets(cas, (
                {"repere": "SUP", "x0": 1.0, "x1": 3.0, "y0": 0.0,
                 "y1": cas["largeur_m"], "degagement_m": 0.30},))
            apres = compter_plan(surface2, rangees2, obstacles2, zones).modules
            self.assertLessEqual(
                apres, avant,
                _contre_exemple(cas, "ajouter un obstacle a fait GAGNER"))

    def test_une_zone_preferee_ne_change_jamais_le_compte(self):
        for cas in self.cas[:200]:
            surface, _p, obstacles, _z, rangees = _objets(cas)
            if not rangees:
                continue
            sans = compter_plan(surface, rangees, obstacles).modules
            preferee = Zone(repere="PREF", nature=NatureZone.PREFEREE,
                            sommets=((0.0, 0.0), (cas["longueur_m"], 0.0),
                                     (cas["longueur_m"], cas["largeur_m"]),
                                     (0.0, cas["largeur_m"])))
            avec = compter_plan(surface, rangees, obstacles,
                                (preferee,)).modules
            self.assertEqual(
                sans, avec,
                _contre_exemple(cas, "une zone préférée a changé le compte"))

    def test_une_zone_interdite_ne_peut_pas_faire_gagner(self):
        for cas in self.cas[:200]:
            surface, _p, obstacles, _z, rangees = _objets(cas)
            if not rangees:
                continue
            sans = compter_plan(surface, rangees, obstacles).modules
            interdite = Zone(repere="INT", nature=NatureZone.INTERDITE,
                             sommets=((2.0, 0.0), (5.0, 0.0),
                                      (5.0, cas["largeur_m"]),
                                      (2.0, cas["largeur_m"])))
            avec = compter_plan(surface, rangees, obstacles,
                                (interdite,)).modules
            self.assertLessEqual(
                avec, sans,
                _contre_exemple(cas, "une zone interdite a fait GAGNER"))


class MonotoniesQuiExigentLeDP(unittest.TestCase):
    """Sous-ensemble : chaque cas rejoue deux DP complets."""

    @classmethod
    def setUpClass(cls):
        rng = random.Random(GRAINE + 1)
        cls.cas = []
        while len(cls.cas) < NB_CAS_DP:
            cas = _generer(rng, 10000 + len(cls.cas))
            # toitures VOLONTAIREMENT petites : un DP au pas de 5 cm sur
            # 60 x 30 m coûte une seconde, et douze cas suffisent à
            # attraper une inversion de monotonie
            if cas["longueur_m"] <= 30.0 and cas["largeur_m"] <= 16.0:
                cls.cas.append(cas)

    def test_elargir_l_allee_ne_peut_pas_augmenter_le_compte(self):
        for cas in self.cas:
            etroit = dict(cas, allee_m=0.60)
            large = dict(cas, allee_m=1.90)
            surface, parametres, obstacles, zones, _r = _objets(etroit)
            _s2, parametres2, _o2, _z2, _r2 = _objets(large)
            petit = optimiser_economique(surface, parametres, obstacles,
                                         zones).modules
            grand = optimiser_economique(surface, parametres2, obstacles,
                                         zones).modules
            self.assertLessEqual(
                grand, petit,
                _contre_exemple(cas, "élargir l'allée a fait GAGNER"))

    def test_le_dp_ne_fait_jamais_moins_que_les_rangees_regulieres(self):
        for cas in self.cas:
            surface, parametres, obstacles, zones, rangees = _objets(cas)
            if not rangees:
                continue
            regulier = compter_plan(surface, rangees, obstacles,
                                    zones).modules
            optimal = optimiser_economique(surface, parametres, obstacles,
                                           zones).modules
            self.assertGreaterEqual(
                optimal, regulier,
                _contre_exemple(cas, "le DP fait MOINS que des rangées "
                                     "régulières"))

    def test_le_dp_est_deterministe(self):
        for cas in self.cas:
            surface, parametres, obstacles, zones, _r = _objets(cas)
            premier = optimiser_economique(surface, parametres, obstacles,
                                           zones)
            second = optimiser_economique(surface, parametres, obstacles,
                                          zones)
            self.assertEqual(premier.modules, second.modules,
                             _contre_exemple(cas, "DP non déterministe"))
            self.assertEqual(premier.rangees, second.rangees,
                             _contre_exemple(cas, "plan DP non déterministe"))


class LeFuzzEstReproductible(unittest.TestCase):
    def test_la_graine_est_fixe(self):
        premier = [_generer(random.Random(GRAINE), i) for i in range(5)]
        second = [_generer(random.Random(GRAINE), i) for i in range(5)]
        self.assertEqual(premier, second)

    def test_un_contre_exemple_est_rejouable(self):
        cas = _generer(random.Random(GRAINE), 0)
        message = _contre_exemple(cas, "essai")
        rejoue = json.loads(message.split("\n", 2)[2])
        self.assertEqual(rejoue, cas)
        surface, _p, _o, _z, _r = _objets(rejoue)
        self.assertTrue(surface.repere)

    def test_le_nombre_de_cas_est_celui_annonce(self):
        self.assertEqual(NB_CAS, 500)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
