"""CALX404 — un rendement aller-retour supposé parfait est REFUSÉ.

Ce qui est tenu ici (le « Done » de la tâche) :

* fiche muette (rendement absent ou non numérique) ⇒
  ``StrategieInvalide.champ == 'rendement_ar_pct'``, une phrase qui nomme la
  fiche à compléter, et AUCUNE série produite ;
* fiche à 90 % ⇒ l'énergie restituée vaut 0,90 fois l'énergie stockée à
  0,001 kWh près, chaque sens à √0,90 ;
* ``resultat['batterie']`` publie ``rendement_ar_pct`` avec sa ``source`` ;
* garde : aucun littéral de repli de rendement ne subsiste dans
  ``services/batterie.py``.

Tests PURS : aucune base, aucun réseau. Séries SYNTHÉTIQUES.
"""
from __future__ import annotations

import math
import pathlib
import re
import unittest

from apps.calepinage.services.batterie import (
    SOURCES_RENDEMENT, StrategieInvalide, simuler_batterie, simuler_groupes,
)

SOURCE = (pathlib.Path(__file__).resolve().parents[1] / 'services'
          / 'batterie.py')

#: 1 h de surplus (2 kWh stockés), puis 3 h de nuit qui vident la batterie.
CONSO = [1.0, 1.0, 1.0, 1.0]
PROD = [3.0, 0.0, 0.0, 0.0]

PARC = dict(strategie='autoconso', capacite_utile_kwh=10.0,
            puissance_charge_kw=5.0, puissance_decharge_kw=5.0)


class FicheMuetteTest(unittest.TestCase):

    def test_un_rendement_absent_est_refuse_sans_aucune_serie(self):
        trace = {}
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, rendement_ar_pct=None,
                             _trace=trace, **PARC)
        self.assertEqual(refus.exception.champ, 'rendement_ar_pct')
        self.assertIn('fiche', str(refus.exception))
        self.assertNotIn('etat', trace)

    def test_un_rendement_omis_est_refuse(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, **PARC)
        self.assertEqual(refus.exception.champ, 'rendement_ar_pct')

    def test_la_grandeur_muette_de_la_fiche_est_refusee(self):
        """La forme que publie ``specs_batterie`` pour une grandeur vide."""
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, rendement_ar_pct={
                'valeur': None, 'source': None,
                'mention': 'La fiche ne publie pas cette grandeur.'}, **PARC)
        self.assertEqual(refus.exception.champ, 'rendement_ar_pct')

    def test_un_rendement_non_numerique_est_refuse(self):
        for valeur in ('quatre-vingt-dix', '', True):
            with self.subTest(valeur=valeur):
                with self.assertRaises(StrategieInvalide) as refus:
                    simuler_batterie(CONSO, PROD, rendement_ar_pct=valeur,
                                     **PARC)
                self.assertEqual(refus.exception.champ, 'rendement_ar_pct')

    def test_un_rendement_hors_bornes_est_refuse(self):
        for valeur in (0, -5, 120):
            with self.subTest(valeur=valeur):
                with self.assertRaises(StrategieInvalide) as refus:
                    simuler_batterie(CONSO, PROD, rendement_ar_pct=valeur,
                                     **PARC)
                self.assertEqual(refus.exception.champ, 'rendement_ar_pct')

    def test_un_groupe_sans_rendement_est_nomme(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD, [dict(PARC, groupe='G1',
                                               couplage='ac')])
        self.assertEqual(refus.exception.champ, 'groupes[0].rendement_ar_pct')


class FicheA90Test(unittest.TestCase):

    def setUp(self):
        self.resultat = simuler_batterie(CONSO, PROD, rendement_ar_pct={
            'valeur': 90.0, 'source': 'fiche',
            'mention': 'Lu sur la fiche produit.'}, **PARC)

    def test_l_energie_restituee_vaut_90_pourcent_de_l_energie_stockee(self):
        stockee = self.resultat['charge_batterie_kwh']
        restituee = self.resultat['decharge_batterie_kwh']
        self.assertAlmostEqual(stockee, 2.0, delta=0.001)
        # La batterie finit vide : tout ce qui est entré est ressorti.
        self.assertAlmostEqual(self.resultat['etat_de_charge_kwh'][-1], 0.0,
                               delta=0.001)
        self.assertAlmostEqual(restituee, 0.90 * stockee, delta=0.001)

    def test_chaque_sens_vaut_la_racine_du_rendement(self):
        un_sens = self.resultat['batterie']['rendement_un_sens']
        self.assertAlmostEqual(un_sens, math.sqrt(0.90), delta=1e-6)
        self.assertAlmostEqual(un_sens * un_sens, 0.90, delta=1e-5)
        # 2 kWh entrés ⇒ 2 × √0,90 kWh stockés dans la batterie.
        self.assertAlmostEqual(self.resultat['etat_de_charge_kwh'][0],
                               2.0 * math.sqrt(0.90), delta=0.001)

    def test_le_rendement_est_publie_avec_sa_source(self):
        self.assertEqual(self.resultat['batterie']['rendement_ar_pct'], 90.0)
        self.assertEqual(self.resultat['batterie']['source'], 'fiche')
        self.assertEqual(self.resultat['parametres']['rendement_ar_pct'],
                         90.0)

    def test_un_nombre_nu_est_publie_comme_une_saisie(self):
        resultat = simuler_batterie(CONSO, PROD, rendement_ar_pct=90.0,
                                    **PARC)
        self.assertEqual(resultat['batterie']['source'], 'saisie')
        self.assertEqual(resultat['decharge_batterie_kwh'],
                         self.resultat['decharge_batterie_kwh'])

    def test_une_hypothese_nommee_reste_nommee(self):
        resultat = simuler_batterie(CONSO, PROD, rendement_ar_pct={
            'valeur': 90.0, 'source': 'hypothese'}, **PARC)
        self.assertEqual(resultat['batterie']['source'], 'hypothese')

    def test_une_provenance_inconnue_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, rendement_ar_pct={
                'valeur': 90.0, 'source': 'rumeur'}, **PARC)
        self.assertEqual(refus.exception.champ, 'rendement_ar_pct')
        self.assertEqual(SOURCES_RENDEMENT, ('fiche', 'hypothese', 'saisie'))


class GardeLitteralTest(unittest.TestCase):
    """Aucun repli de rendement ne subsiste dans ``services/batterie.py``."""

    MOTIFS = (
        r'rendement\w*\s+or\s+[\d.]+',          # « rendement or 100.0 »
        r'else\s+100(\.0*)?\b',                  # « … else 100.0 »
        r'rendement_ar_pct\s*=\s*[\d.]+',       # défaut numérique
        r'\beta\s*=\s*1(\.0*)?\b',               # « eta = 1.0 »
        r'min\(\s*1\.0\s*,\s*\(?\s*rendement',  # l'ancien bornage muet
    )

    def test_aucun_litteral_de_repli(self):
        texte = SOURCE.read_text(encoding='utf-8')
        for motif in self.MOTIFS:
            with self.subTest(motif=motif):
                self.assertIsNone(re.search(motif, texte),
                                  f'repli de rendement trouvé : {motif}')

    def test_la_garde_rougit_sur_l_ancien_code(self):
        ancien = ('eta = math.sqrt(max(0.0, min(1.0, (rendement or 100.0) '
                  '/ 100.0)))')
        self.assertTrue(any(re.search(motif, ancien)
                            for motif in self.MOTIFS))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
