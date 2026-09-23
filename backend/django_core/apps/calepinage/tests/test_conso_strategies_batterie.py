"""CAL152 — les quatre stratégies de batterie, en dispatch horaire.

Un test PAR STRATÉGIE, comme l'exige la tâche, plus les refus :

* la stratégie retenue est affichée AVEC son objectif dimensionnant ;
* le seuil d'effacement et les heures de décalage sont TOUJOURS saisis —
  aucun tarif, aucun seuil deviné.

Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.batterie import (
    STRATEGIES, StrategieInvalide, simuler_batterie, tranches_horaires,
)

#: Une journée : consommation à plat, production diurne excédentaire.
CONSO = [1.0] * 24
PROD = [0.0] * 6 + [2.0] * 12 + [0.0] * 6

PARC = dict(capacite_utile_kwh=10.0, puissance_charge_kw=5.0,
            puissance_decharge_kw=5.0, rendement_ar_pct=100.0)


class AutoconsoTest(unittest.TestCase):

    def test_le_surplus_du_jour_couvre_la_nuit(self):
        resultat = simuler_batterie(CONSO, PROD, strategie='autoconso',
                                    **PARC)
        self.assertGreater(resultat['charge_batterie_kwh'], 0.0)
        self.assertGreater(resultat['decharge_batterie_kwh'], 0.0)
        # Sans batterie, la nuit (12 h × 1 kWh) serait entièrement importée.
        self.assertLess(resultat['import_reseau_kwh'], 12.0)

    def test_l_objectif_dimensionnant_est_affiche(self):
        resultat = simuler_batterie(CONSO, PROD, strategie='autoconso',
                                    **PARC)
        self.assertIn('autoconsommée', resultat['objectif_dimensionnant'])

    def test_le_rendement_aller_retour_coute_de_l_energie(self):
        # Parc volontairement JUSTE (5 kWh utiles) : c'est là que le
        # rendement se voit, un parc surdimensionné masquerait la perte.
        serre = dict(PARC, capacite_utile_kwh=5.0)
        parfait = simuler_batterie(CONSO, PROD, strategie='autoconso',
                                   **dict(serre, rendement_ar_pct=100.0))
        mediocre = simuler_batterie(CONSO, PROD, strategie='autoconso',
                                    **dict(serre, rendement_ar_pct=80.0))
        self.assertGreater(mediocre['import_reseau_kwh'],
                           parfait['import_reseau_kwh'])


class PeakShavingTest(unittest.TestCase):

    def test_le_soutirage_est_efface_au_dessus_du_seuil_saisi(self):
        # Consommation nocturne forte, aucune production : seul le dépassement
        # du seuil est effacé.
        conso = [3.0] * 24
        prod = [0.0] * 24
        resultat = simuler_batterie(
            conso, prod, strategie='peak_shaving',
            seuil_effacement_kw=2.0,
            **dict(PARC, etat_initial_kwh=10.0))
        self.assertEqual(resultat['energie_effacee_kwh'], 10.0)
        # 72 kWh consommés, 10 kWh effacés par la batterie.
        self.assertEqual(resultat['import_reseau_kwh'], 62.0)

    def test_sous_le_seuil_la_batterie_ne_bouge_pas(self):
        resultat = simuler_batterie(
            [1.0] * 24, [0.0] * 24, strategie='peak_shaving',
            seuil_effacement_kw=5.0, **dict(PARC, etat_initial_kwh=10.0))
        self.assertEqual(resultat['decharge_batterie_kwh'], 0.0)
        self.assertEqual(resultat['energie_effacee_kwh'], 0.0)

    def test_sans_seuil_saisi_la_strategie_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='peak_shaving', **PARC)
        self.assertEqual(refus.exception.champ, 'seuil_effacement_kw')
        self.assertIn('tarif', str(refus.exception))


class BackupTest(unittest.TestCase):

    def test_la_reserve_saisie_n_est_jamais_entamee(self):
        """Parc PLEIN au départ : l'état ne descend jamais sous la réserve."""
        resultat = simuler_batterie(
            CONSO, PROD, strategie='backup', reserve_backup_kwh=6.0,
            **dict(PARC, etat_initial_kwh=10.0))
        self.assertTrue(all(etat >= 6.0 - 1e-6
                            for etat in resultat['etat_de_charge_kwh']),
                        resultat['etat_de_charge_kwh'])
        self.assertIn('coupure', resultat['objectif_dimensionnant'])

    def test_sans_reserve_saisie_la_strategie_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='backup', **PARC)
        self.assertEqual(refus.exception.champ, 'reserve_backup_kwh')

    def test_la_reserve_reduit_l_energie_restituee(self):
        sans = simuler_batterie(CONSO, PROD, strategie='backup',
                                reserve_backup_kwh=0.0, **PARC)
        avec = simuler_batterie(CONSO, PROD, strategie='backup',
                                reserve_backup_kwh=8.0, **PARC)
        self.assertLess(avec['decharge_batterie_kwh'],
                        sans['decharge_batterie_kwh'])


class DecalageTest(unittest.TestCase):

    def test_la_batterie_ne_charge_et_ne_decharge_qu_aux_heures_saisies(self):
        resultat = simuler_batterie(
            CONSO, PROD, strategie='decalage',
            heures_charge=[10, 11, 12], heures_decharge=[19, 20, 21],
            **PARC)
        # 3 h de charge à 1 kWh de surplus par heure (2 − 1).
        self.assertEqual(resultat['charge_batterie_kwh'], 3.0)
        self.assertEqual(resultat['decharge_batterie_kwh'], 3.0)
        self.assertEqual(resultat['parametres']['heures_charge'],
                         [10, 11, 12])

    def test_sans_heures_saisies_la_strategie_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='decalage', **PARC)
        self.assertEqual(refus.exception.champ, 'heures_charge')

    def test_une_heure_en_charge_ET_en_decharge_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='decalage',
                             heures_charge=[12], heures_decharge=[12], **PARC)
        self.assertEqual(refus.exception.champ, 'heures_decharge')

    def test_les_tranches_de_reference_sont_OFFERTES_pas_appliquees(self):
        """Elles servent à PROPOSER des heures, jamais à en choisir."""
        tranches = tranches_horaires()
        self.assertEqual(len(tranches), 24)
        self.assertIn('pointe', tranches)
        # …et elles ne dispensent PAS de saisir les heures :
        with self.assertRaises(StrategieInvalide):
            simuler_batterie(CONSO, PROD, strategie='decalage', **PARC)


class RefusCommunsTest(unittest.TestCase):

    def test_toutes_les_strategies_sont_nommees(self):
        # CALX63 ajoute ``plafond_injection`` et ``heures_tarif``.
        self.assertEqual(set(STRATEGIES),
                         {'autoconso', 'peak_shaving', 'backup', 'decalage',
                          'plafond_injection', 'heures_tarif'})

    def test_une_strategie_inconnue_est_refusee_en_la_nommant(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='magique', **PARC)
        self.assertEqual(refus.exception.champ, 'strategie')

    def test_sans_capacite_connue_aucune_simulation(self):
        parc = dict(PARC, capacite_utile_kwh=None)
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='autoconso', **parc)
        self.assertEqual(refus.exception.champ, 'capacite_utile_kwh')

    def test_sans_puissance_connue_aucune_simulation(self):
        parc = dict(PARC, puissance_charge_kw=None)
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD, strategie='autoconso', **parc)
        self.assertEqual(refus.exception.champ, 'puissance_charge_kw')

    def test_deux_periodes_differentes_sont_refusees(self):
        with self.assertRaises(StrategieInvalide):
            simuler_batterie(CONSO, PROD * 2, strategie='autoconso', **PARC)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
