"""CALX260 — le Ramadan décale la courbe de consommation, sans chiffre neuf.

Ce qui est prouvé ici :

* une date HORS de la plage rend la MÊME liste (identité) ;
* une date DANS la plage (Ramadan 1447, 2026 — l'horloge marocaine repassait
  alors à UTC+0 pendant le mois) décale la courbe d'UNE heure et conserve
  l'intégrale au kWh près (test de propriété sur 200 courbes) ;
* le décalage publié est EXACTEMENT l'écart lu dans la base de fuseaux
  (``apps.ventes.ramadan.decalage_maroc_h``) — pour n'importe quel Ramadan de
  la table, quelle que soit la version de la base (depuis le décret
  n° 2.26.530 il n'y a plus de changement d'heure : écart nul, identité) ;
* la part du mois et la mention du fuseau sont publiées ;
* GARDE : aucune constante horaire n'est écrite dans ``consommation.py`` — le
  code du Ramadan n'y porte AUCUN littéral numérique et le module ne contient
  ni décalage « UTC±n », ni ``hours=``, ni table de dates, ni lecture directe
  du fuseau : tout est relu dans ``apps.ventes.ramadan``.

Fonction PURE : aucune base de données.
"""
from __future__ import annotations

import ast
import pathlib
import random
import re
import unittest
from datetime import date

from apps.calepinage.services import consommation
from apps.calepinage.services.consommation import (
    ProfilInvalide, appliquer_ramadan,
)
from apps.ventes import ramadan

#: Un jour du Ramadan 1447 (18/02 → 19/03/2026, ``ramadan.RAMADAN_PLAGES``).
JOUR_RAMADAN_2026 = date(2026, 3, 1)
#: Un jour ordinaire entre deux Ramadans.
JOUR_ORDINAIRE = date(2026, 6, 15)


def courbe_type():
    return [float(heure) + 0.5 for heure in range(24)]


class HorsRamadanTest(unittest.TestCase):

    def test_une_date_hors_plage_rend_la_meme_liste(self):
        courbe = courbe_type()
        resultat = appliquer_ramadan(courbe, jour=JOUR_ORDINAIRE)
        self.assertEqual(resultat['courbe24'], courbe)
        self.assertFalse(resultat['dans_ramadan'])
        self.assertIsNone(resultat['decalage_h'])

    def test_une_date_au_dela_de_la_table_rend_la_meme_liste(self):
        courbe = courbe_type()
        resultat = appliquer_ramadan(courbe, jour=date(2040, 6, 1))
        self.assertEqual(resultat['courbe24'], courbe)
        self.assertTrue(resultat['avertissements'])

    def test_courbe_de_23_valeurs_refusee_en_la_nommant(self):
        with self.assertRaises(ProfilInvalide) as capture:
            appliquer_ramadan([1.0] * 23, jour=JOUR_ORDINAIRE)
        self.assertEqual(capture.exception.champ, 'courbe24')

    def test_jour_qui_nest_pas_une_date_refuse_en_le_nommant(self):
        with self.assertRaises(ProfilInvalide) as capture:
            appliquer_ramadan(courbe_type(), jour='2026-03-01')
        self.assertEqual(capture.exception.champ, 'jour')


class DansRamadanTest(unittest.TestCase):

    def test_une_date_dans_la_plage_decale_dune_heure(self):
        courbe = courbe_type()
        resultat = appliquer_ramadan(courbe, jour=JOUR_RAMADAN_2026)
        self.assertTrue(resultat['dans_ramadan'])
        self.assertEqual(resultat['decalage_h'], 1)
        decalee = resultat['courbe24']
        for heure in range(24):
            self.assertEqual(decalee[heure], courbe[(heure - 1) % 24])
        self.assertNotEqual(decalee, courbe)

    def test_lintegrale_est_conservee_au_kwh_pres(self):
        alea = random.Random(260)
        for _ in range(200):
            courbe = [round(alea.uniform(0, 4), 3) for _ in range(24)]
            resultat = appliquer_ramadan(courbe, jour=JOUR_RAMADAN_2026)
            self.assertAlmostEqual(sum(resultat['courbe24']), sum(courbe),
                                   delta=1e-6)
            self.assertEqual(sorted(resultat['courbe24']), sorted(courbe))

    def test_le_decalage_est_celui_de_la_base_de_fuseaux(self):
        # Pour CHAQUE Ramadan de la table, le décalage publié est l'écart
        # d'heure légale lu dans la base — jamais un chiffre écrit.
        for plage in ramadan.RAMADAN_PLAGES:
            jour = plage['debut']
            ordinaire = plage['debut'] - (plage['fin'] - plage['debut'])
            attendu = (ramadan.decalage_maroc_h(ordinaire)
                       - ramadan.decalage_maroc_h(jour))
            resultat = appliquer_ramadan(courbe_type(), jour=jour)
            self.assertEqual(resultat['decalage_h'], attendu, plage['hijri'])
            if attendu == 0:
                self.assertEqual(resultat['courbe24'], courbe_type())

    def test_part_du_mois_et_mention_du_fuseau_publiees(self):
        resultat = appliquer_ramadan(courbe_type(), jour=JOUR_RAMADAN_2026,
                                     lat=33.57, lon=-7.59)
        parts = ramadan.part_ramadan_par_mois(JOUR_RAMADAN_2026)
        self.assertEqual(resultat['part_du_mois'], parts[2])   # mars
        self.assertEqual(resultat['hijri'], 1447)
        self.assertIn('Africa/Casablanca', resultat['fuseau']['mention'])
        self.assertEqual(resultat['fuseau']['utc_jour_h'],
                         ramadan.decalage_maroc_h(JOUR_RAMADAN_2026))
        self.assertIsNotNone(resultat['fenetre'])


#: Ce qui trahirait une heure écrite dans le module (au lieu d'être relue).
MOTIFS_HEURE_ECRITE = (
    re.compile(r'UTC\s*[+-]\s*\d'),         # « UTC+1 » codé en dur
    re.compile(r'\bhours\s*='),             # timedelta(hours=…)
    re.compile(r'\bZoneInfo\s*\('),         # fuseau lu en direct
    re.compile(r'\butcoffset\s*\('),
    re.compile(r'\bdate\s*\(\s*20\d\d'),    # une seconde table de dates
)

#: Le code du Ramadan dans ``consommation.py``.
FONCTIONS_RAMADAN = ('appliquer_ramadan', '_tourner')


class GardeAucuneHeureEcriteTest(unittest.TestCase):

    def setUp(self):
        self.source = pathlib.Path(consommation.__file__).read_text(
            encoding='utf-8')
        self.arbre = ast.parse(self.source)

    def test_le_code_du_ramadan_ne_porte_aucun_litteral_numerique(self):
        fonctions = {noeud.name: noeud for noeud in ast.walk(self.arbre)
                     if isinstance(noeud, ast.FunctionDef)}
        for nom in FONCTIONS_RAMADAN:
            litteraux = [
                (sous.lineno, sous.value)
                for sous in ast.walk(fonctions[nom])
                if isinstance(sous, ast.Constant)
                and isinstance(sous.value, (int, float))
                and not isinstance(sous.value, bool)
            ]
            self.assertEqual(litteraux, [], nom)

    def test_le_module_necrit_aucune_heure(self):
        for motif in MOTIFS_HEURE_ECRITE:
            self.assertIsNone(motif.search(self.source), motif.pattern)

    def test_le_ramadan_est_relu_dans_apps_ventes_ramadan(self):
        importes = {
            (noeud.module, alias.name)
            for noeud in ast.walk(self.arbre)
            if isinstance(noeud, ast.ImportFrom)
            for alias in noeud.names
        }
        self.assertIn(('apps.ventes', 'ramadan'), importes)


if __name__ == '__main__':
    unittest.main()
