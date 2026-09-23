"""CALX269 — la pointe AVANT et APRÈS effacement, publiée.

Ce qui est tenu ici (le « Done » de la tâche) :

* charge horaire de 10 kW pendant 3 h, seuil SAISI de 6 kW, batterie de
  12 kWh utiles ⇒ ``pointe_apres_kw == 6.0`` et
  ``depassements_residuels == []`` ;
* la même charge avec une batterie de 6 kWh ⇒ ``pointe_apres_kw > 6.0`` et
  au moins un dépassement listé ;
* une stratégie autre que ``peak_shaving`` ⇒ les quatre clés valent
  ``None`` ;
* aucune valeur monétaire n'entre (le module ne connaît aucun tarif).

Tests PURS : aucune base, aucun réseau. Séries SYNTHÉTIQUES.
"""
from __future__ import annotations

import json
import unittest

from apps.calepinage.services.batterie import simuler_batterie, simuler_groupes

#: 3 h de soutirage à 10 kW, aucune production.
CONSO = [10.0, 10.0, 10.0]
PROD = [0.0, 0.0, 0.0]

CLES_POINTE = ('pointe_avant_kw', 'pointe_apres_kw',
               'heures_au_dessus_du_seuil', 'depassements_residuels')


def effacement(capacite, **extra):
    """Une batterie PLEINE au départ, seuil SAISI de 6 kW."""
    parametres = dict(strategie='peak_shaving', seuil_effacement_kw=6.0,
                      capacite_utile_kwh=capacite, puissance_charge_kw=10.0,
                      puissance_decharge_kw=10.0, rendement_ar_pct=100.0,
                      etat_initial_kwh=capacite)
    parametres.update(extra)
    return simuler_batterie(CONSO, PROD, **parametres)


class PointeAvantApresTest(unittest.TestCase):

    def test_une_batterie_suffisante_ramene_la_pointe_au_seuil(self):
        resultat = effacement(12.0)
        self.assertEqual(resultat['pointe_apres_kw'], 6.0)
        self.assertEqual(resultat['depassements_residuels'], [])
        self.assertEqual(resultat['pointe_avant_kw'], 10.0)
        self.assertEqual(resultat['heures_au_dessus_du_seuil'], 3)

    def test_une_batterie_trop_petite_laisse_des_depassements(self):
        resultat = effacement(6.0)
        self.assertGreater(resultat['pointe_apres_kw'], 6.0)
        self.assertGreaterEqual(len(resultat['depassements_residuels']), 1)
        premier = resultat['depassements_residuels'][0]
        self.assertEqual(set(premier),
                         {'rang', 'heure', 'soutirage_kw', 'depassement_kw'})
        self.assertAlmostEqual(premier['depassement_kw'],
                               premier['soutirage_kw'] - 6.0, delta=0.001)

    def test_la_pointe_apres_est_la_serie_d_import_produite(self):
        # 6 kWh : 4 kWh effacés la 1re heure, 2 kWh la 2e, rien la 3e.
        resultat = effacement(6.0)
        self.assertEqual(resultat['pointe_apres_kw'], 10.0)
        rangs = [d['rang'] for d in resultat['depassements_residuels']]
        self.assertEqual(rangs, [1, 2])

    def test_le_pas_de_temps_convertit_l_energie_en_puissance(self):
        # Pas de 15 min : 2,5 kWh par pas = 10 kW.
        resultat = simuler_batterie(
            [2.5] * 4, [0.0] * 4, strategie='peak_shaving',
            seuil_effacement_kw=6.0, capacite_utile_kwh=12.0,
            puissance_charge_kw=10.0, puissance_decharge_kw=10.0,
            rendement_ar_pct=100.0, etat_initial_kwh=12.0, pas_heures=0.25)
        self.assertEqual(resultat['pointe_avant_kw'], 10.0)
        self.assertEqual(resultat['pointe_apres_kw'], 6.0)


class HorsEffacementTest(unittest.TestCase):

    def test_les_autres_strategies_publient_none(self):
        base = dict(capacite_utile_kwh=12.0, puissance_charge_kw=10.0,
                    puissance_decharge_kw=10.0, rendement_ar_pct=100.0)
        cas = {
            'autoconso': {},
            'backup': {'reserve_backup_kwh': 2.0},
            'decalage': {'heures_charge': [1], 'heures_decharge': [2]},
        }
        for strategie, extra in cas.items():
            with self.subTest(strategie=strategie):
                resultat = simuler_batterie(CONSO, PROD, strategie=strategie,
                                            **base, **extra)
                for cle in CLES_POINTE:
                    self.assertIn(cle, resultat)
                    self.assertIsNone(resultat[cle])


class AucunMontantTest(unittest.TestCase):

    def test_aucune_valeur_monetaire(self):
        texte = json.dumps(effacement(6.0)).lower()
        for interdit in ('prix', 'cout', 'marge', 'mad', 'tarif'):
            self.assertNotIn(interdit, texte)


class GroupesTest(unittest.TestCase):
    """L'agrégat de CALX267 publie la pointe AVANT tous, APRÈS tous."""

    def _groupe(self, nom, capacite):
        return dict(groupe=nom, couplage='ac', modele='PACK-X',
                    strategie='peak_shaving', seuil_effacement_kw=6.0,
                    capacite_utile_kwh=capacite, puissance_charge_kw=10.0,
                    puissance_decharge_kw=10.0, rendement_ar_pct=100.0,
                    etat_initial_kwh=capacite)

    def test_deux_groupes_de_6_kwh_ramenent_la_pointe_au_seuil(self):
        resultat = simuler_groupes(CONSO, PROD, [self._groupe('G1', 6.0),
                                                 self._groupe('G2', 6.0)])
        agregat = resultat['agregat']
        self.assertEqual(agregat['pointe_avant_kw'], 10.0)
        self.assertEqual(agregat['pointe_apres_kw'], 6.0)
        self.assertEqual(agregat['depassements_residuels'], [])
        self.assertEqual(agregat['heures_au_dessus_du_seuil'], 3)

    def test_un_seul_groupe_reste_le_resultat_d_aujourd_hui(self):
        resultat = simuler_groupes(CONSO, PROD, [self._groupe('G1', 6.0)])
        self.assertEqual(resultat['agregat'], effacement(6.0))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
