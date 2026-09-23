"""CALX270 — la réserve de secours déduite des appareils réellement secourus.

Ce qui est tenu ici (le « Done » de la tâche) :

* 2 appareils de 0,5 kW continus / 1,5 kW de pointe pendant 4 h ⇒
  ``energie_kwh == 4.0``, ``puissance_continue_kw == 1.0``,
  ``puissance_pointe_kw == 3.0`` ;
* un appareil sans puissance de pointe ⇒ refus nommant
  ``appareils[0].puissance_pointe_kw`` (aucun facteur de pointe supposé) ;
* la réserve NUE d'aujourd'hui reste acceptée telle quelle ;
* ``part_effacable_pct`` / ``plafond_effacable_kw`` SAISIS bornent la part
  de la charge qu'un groupe peut servir (exemple chiffré d'OpenSolar : 33,33 %
  de 3 kWh ⇒ 1 kWh) ; non saisis ⇒ comportement d'aujourd'hui.

Tests PURS : aucune base, aucun réseau. Séries SYNTHÉTIQUES.
"""
from __future__ import annotations

import pathlib
import unittest

from apps.calepinage.services.batterie import (
    StrategieInvalide, reserve_depuis_appareils, simuler_batterie,
    simuler_groupes,
)

SOURCE = (pathlib.Path(__file__).resolve().parents[1] / 'services'
          / 'batterie.py')

CONSO = [1.0] * 24
PROD = [0.0] * 6 + [2.0] * 12 + [0.0] * 6
PARC = dict(capacite_utile_kwh=10.0, puissance_charge_kw=5.0,
            puissance_decharge_kw=5.0, rendement_ar_pct=100.0)

DEUX_APPAREILS = [
    {'nom': 'Réfrigérateur', 'puissance_continue_kw': 0.5,
     'puissance_pointe_kw': 1.5, 'quantite': 1},
    {'nom': 'Pompe de relevage', 'puissance_continue_kw': 0.5,
     'puissance_pointe_kw': 1.5, 'quantite': 1},
]


class ReserveDepuisAppareilsTest(unittest.TestCase):

    def test_deux_appareils_pendant_quatre_heures(self):
        reserve = reserve_depuis_appareils(DEUX_APPAREILS, duree_h=4)
        self.assertEqual(reserve['energie_kwh'], 4.0)
        self.assertEqual(reserve['puissance_continue_kw'], 1.0)
        self.assertEqual(reserve['puissance_pointe_kw'], 3.0)
        self.assertEqual(len(reserve['detail']), 2)
        self.assertEqual(reserve['detail'][0]['energie_kwh'], 2.0)

    def test_la_quantite_multiplie(self):
        reserve = reserve_depuis_appareils(
            [{'nom': 'Lampe', 'puissance_continue_kw': 0.5,
              'puissance_pointe_kw': 1.5, 'quantite': 2}], duree_h=4)
        self.assertEqual(reserve['energie_kwh'], 4.0)
        self.assertEqual(reserve['puissance_pointe_kw'], 3.0)

    def test_sans_puissance_de_pointe_l_appareil_est_nomme(self):
        sans = [dict(DEUX_APPAREILS[0])]
        sans[0].pop('puissance_pointe_kw')
        with self.assertRaises(StrategieInvalide) as refus:
            reserve_depuis_appareils(sans, duree_h=4)
        self.assertEqual(refus.exception.champ,
                         'appareils[0].puissance_pointe_kw')
        self.assertIn('Réfrigérateur', str(refus.exception))

    def test_une_pointe_sous_la_puissance_continue_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            reserve_depuis_appareils(
                [{'nom': 'X', 'puissance_continue_kw': 2.0,
                  'puissance_pointe_kw': 1.0, 'quantite': 1}], duree_h=4)
        self.assertEqual(refus.exception.champ,
                         'appareils[0].puissance_pointe_kw')

    def test_les_autres_grandeurs_absentes_sont_nommees(self):
        cas = {
            'puissance_continue_kw': 'appareils[1].puissance_continue_kw',
            'quantite': 'appareils[1].quantite',
        }
        for grandeur, champ in cas.items():
            with self.subTest(grandeur=grandeur):
                appareils = [dict(a) for a in DEUX_APPAREILS]
                appareils[1].pop(grandeur)
                with self.assertRaises(StrategieInvalide) as refus:
                    reserve_depuis_appareils(appareils, duree_h=4)
                self.assertEqual(refus.exception.champ, champ)

    def test_duree_et_liste_obligatoires(self):
        with self.assertRaises(StrategieInvalide) as refus:
            reserve_depuis_appareils(DEUX_APPAREILS, duree_h=None)
        self.assertEqual(refus.exception.champ, 'duree_h')
        with self.assertRaises(StrategieInvalide) as refus:
            reserve_depuis_appareils([], duree_h=4)
        self.assertEqual(refus.exception.champ, 'appareils')

    def test_aucun_facteur_de_pointe_n_est_relu_des_ventes(self):
        texte = SOURCE.read_text(encoding='utf-8')
        self.assertNotIn('solar_design._BATTERY_BACKUP_PEAK_FACTOR', texte)
        self.assertNotIn('import _BATTERY_BACKUP_PEAK_FACTOR', texte)


class SimulationDeSecoursTest(unittest.TestCase):

    def test_les_appareils_remplacent_la_reserve_nue(self):
        par_appareils = simuler_batterie(
            CONSO, PROD, strategie='backup', appareils=DEUX_APPAREILS,
            duree_secours_h=4, etat_initial_kwh=10.0, **PARC)
        nue = simuler_batterie(
            CONSO, PROD, strategie='backup', reserve_backup_kwh=4.0,
            etat_initial_kwh=10.0, **PARC)
        for cle in ('etat_de_charge_kwh', 'decharge_batterie_kwh',
                    'import_reseau_kwh'):
            self.assertEqual(par_appareils[cle], nue[cle])
        self.assertEqual(par_appareils['parametres']['reserve_backup_kwh'],
                         4.0)
        detail = par_appareils['parametres']['reserve_appareils']
        self.assertEqual(detail['puissance_pointe_kw'], 3.0)
        self.assertTrue(all(etat >= 4.0 - 1e-6 for etat in
                            par_appareils['etat_de_charge_kwh']))

    def test_la_reserve_nue_d_aujourd_hui_reste_acceptee(self):
        resultat = simuler_batterie(
            CONSO, PROD, strategie='backup', reserve_backup_kwh=6.0,
            etat_initial_kwh=10.0, **PARC)
        self.assertEqual(resultat['parametres']['reserve_backup_kwh'], 6.0)
        self.assertIsNone(resultat['parametres']['reserve_appareils'])

    def test_un_appareil_sans_pointe_refuse_la_simulation(self):
        sans = [dict(DEUX_APPAREILS[0])]
        sans[0]['puissance_pointe_kw'] = None
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='backup', appareils=sans,
                             duree_secours_h=4, **PARC)
        self.assertEqual(refus.exception.champ,
                         'appareils[0].puissance_pointe_kw')

    def test_la_duree_de_secours_est_nommee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='backup',
                             appareils=DEUX_APPAREILS, **PARC)
        self.assertEqual(refus.exception.champ, 'duree_secours_h')

    def test_reserve_nue_et_appareils_a_la_fois(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='backup',
                             reserve_backup_kwh=2.0, appareils=DEUX_APPAREILS,
                             duree_secours_h=4, **PARC)
        self.assertEqual(refus.exception.champ, 'reserve_backup_kwh')

    def test_des_appareils_hors_secours(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='autoconso',
                             appareils=DEUX_APPAREILS, duree_secours_h=4,
                             **PARC)
        self.assertEqual(refus.exception.champ, 'appareils')


class PartEffacableTest(unittest.TestCase):
    """« Load Offsettable (%) » et « Load Offsettable Cap (kW) »."""

    def test_l_exemple_d_opensolar_33_pourcent_de_3_kwh(self):
        resultat = simuler_batterie(
            [3.0], [0.0], strategie='autoconso', etat_initial_kwh=10.0,
            part_effacable_pct=100.0 / 3.0, **PARC)
        self.assertAlmostEqual(resultat['decharge_batterie_kwh'], 1.0,
                               delta=0.001)
        self.assertAlmostEqual(resultat['import_reseau_kwh'], 2.0,
                               delta=0.001)

    def test_le_plafond_borne_la_puissance_servie(self):
        resultat = simuler_batterie(
            [3.0], [0.0], strategie='autoconso', etat_initial_kwh=10.0,
            plafond_effacable_kw=0.5, **PARC)
        self.assertAlmostEqual(resultat['decharge_batterie_kwh'], 0.5,
                               delta=0.001)

    def test_non_saisis_aucune_borne(self):
        sans = simuler_batterie(CONSO, PROD, strategie='autoconso', **PARC)
        avec_none = simuler_batterie(CONSO, PROD, strategie='autoconso',
                                     part_effacable_pct=None,
                                     plafond_effacable_kw=None, **PARC)
        self.assertEqual(sans, avec_none)
        self.assertIsNone(sans['parametres']['part_effacable_pct'])
        self.assertIsNone(sans['parametres']['plafond_effacable_kw'])

    def test_des_bornes_invalides_sont_nommees(self):
        cas = {'part_effacable_pct': 0, 'plafond_effacable_kw': -1}
        for champ, valeur in cas.items():
            with self.subTest(champ=champ):
                with self.assertRaises(StrategieInvalide) as refus:
                    simuler_batterie(CONSO, PROD, strategie='autoconso',
                                     **{champ: valeur}, **PARC)
                self.assertEqual(refus.exception.champ, champ)

    def test_chaque_groupe_porte_sa_propre_part(self):
        resultat = simuler_groupes([3.0], [0.0], [
            dict(PARC, groupe='SECOURS', couplage='ac', modele='PACK-X',
                 strategie='autoconso', etat_initial_kwh=10.0,
                 part_effacable_pct=100.0 / 3.0),
            dict(PARC, groupe='MAISON', couplage='ac', modele='PACK-X',
                 strategie='autoconso', etat_initial_kwh=10.0),
        ])
        premier, second = (ligne['resultat'] for ligne in resultat['groupes'])
        self.assertAlmostEqual(premier['decharge_batterie_kwh'], 1.0,
                               delta=0.001)
        self.assertAlmostEqual(second['decharge_batterie_kwh'], 2.0,
                               delta=0.001)
        self.assertAlmostEqual(resultat['agregat']['import_reseau_kwh'], 0.0,
                               delta=0.001)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
