"""CAL160 — hors-réseau : J jours d'autonomie, défaillance et mois critique.

Ce qui est tenu :

* J est SAISI — un J absent est refusé en nommant le champ (jamais un défaut) ;
* la DoD vient de la FICHE, et une DoD d'hypothèse est ANNONCÉE ;
* le taux de défaillance est CALCULÉ sur la série horaire ;
* le mois le plus défavorable est identifié.

Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.hors_reseau import (
    HorsReseauInvalide, banque_pour_autonomie, dimensionner_hors_reseau,
    simuler_hors_reseau,
)

#: Une journée de site isolé : consommation à plat, production diurne.
CONSO = [1.0] * 24
PROD = [0.0] * 6 + [2.0] * 12 + [0.0] * 6


def annee(courbe, jours=12):
    return courbe * jours


def mois_de(jours=12):
    """Un mois par JOURNÉE de 24 h — douze journées, une par mois."""
    return [mois for mois in range(1, jours + 1) for _ in range(24)]


class BanqueTest(unittest.TestCase):

    def test_la_banque_couvre_J_jours_de_consommation(self):
        banque = banque_pour_autonomie(consommation_journaliere_kwh=24.0,
                                       jours_autonomie=3, dod_pct=80.0,
                                       source_dod='fiche')
        self.assertEqual(banque['capacite_utile_kwh'], 72.0)
        # NOMINALE = utile ÷ DoD : c'est ce qu'il faut ACHETER.
        self.assertEqual(banque['capacite_nominale_kwh'], 90.0)

    def test_J_est_obligatoire_et_le_refus_le_nomme(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            banque_pour_autonomie(consommation_journaliere_kwh=24.0,
                                  dod_pct=80.0)
        self.assertEqual(refus.exception.champ, 'jours_autonomie')
        self.assertIn('SAISI', str(refus.exception))

    def test_la_dod_est_obligatoire(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            banque_pour_autonomie(consommation_journaliere_kwh=24.0,
                                  jours_autonomie=2)
        self.assertEqual(refus.exception.champ, 'dod_pct')
        self.assertIn('fiche', str(refus.exception))

    def test_une_dod_d_hypothese_est_ANNONCEE(self):
        banque = banque_pour_autonomie(consommation_journaliere_kwh=24.0,
                                       jours_autonomie=2, dod_pct=90.0,
                                       source_dod='hypothese')
        self.assertTrue(any('HYPOTHÈSE' in m for m in banque['mentions']))

    def test_le_rendement_publie_majore_la_banque(self):
        sans = banque_pour_autonomie(consommation_journaliere_kwh=24.0,
                                     jours_autonomie=2, dod_pct=80.0,
                                     source_dod='fiche')
        avec = banque_pour_autonomie(consommation_journaliere_kwh=24.0,
                                     jours_autonomie=2, dod_pct=80.0,
                                     source_dod='fiche',
                                     rendement_ar_pct=90.0)
        self.assertGreater(avec['capacite_utile_kwh'],
                           sans['capacite_utile_kwh'])

    def test_une_consommation_absente_est_refusee(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            banque_pour_autonomie(jours_autonomie=2, dod_pct=80.0)
        self.assertEqual(refus.exception.champ,
                         'consommation_journaliere_kwh')


class DefaillanceTest(unittest.TestCase):

    def test_une_banque_suffisante_ne_defaille_pas(self):
        resultat = simuler_hors_reseau(CONSO, PROD,
                                       capacite_utile_kwh=24.0)
        self.assertEqual(resultat['defaillance_kwh'], 0.0)
        self.assertEqual(resultat['taux_defaillance'], 0.0)
        self.assertEqual(resultat['heures_defaillantes'], 0)

    def test_une_banque_trop_petite_defaille_et_le_dit(self):
        """Banque vide au départ et minuscule : la nuit n'est pas tenue."""
        resultat = simuler_hors_reseau(CONSO, PROD, capacite_utile_kwh=1.0,
                                       etat_initial_kwh=0.0)
        self.assertGreater(resultat['defaillance_kwh'], 0.0)
        self.assertGreater(resultat['taux_defaillance'], 0.0)
        self.assertGreater(resultat['heures_defaillantes'], 0)

    def test_le_surplus_non_stockable_est_publie_comme_perdu(self):
        resultat = simuler_hors_reseau(CONSO, PROD, capacite_utile_kwh=2.0)
        self.assertGreater(resultat['surplus_perdu_kwh'], 0.0)

    def test_les_energies_se_referment(self):
        resultat = simuler_hors_reseau(CONSO, PROD, capacite_utile_kwh=5.0,
                                       etat_initial_kwh=0.0)
        self.assertAlmostEqual(
            resultat['servi_kwh'] + resultat['defaillance_kwh'],
            resultat['consommation_kwh'], places=3)

    def test_la_banque_pleine_par_defaut_est_ANNONCEE(self):
        resultat = simuler_hors_reseau(CONSO, PROD, capacite_utile_kwh=5.0)
        self.assertTrue(any('PLEINE' in m for m in resultat['mentions']))

    def test_sans_capacite_aucune_simulation(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            simuler_hors_reseau(CONSO, PROD, capacite_utile_kwh=None)
        self.assertEqual(refus.exception.champ, 'capacite_utile_kwh')

    def test_deux_periodes_differentes_sont_refusees(self):
        with self.assertRaises(HorsReseauInvalide):
            simuler_hors_reseau(CONSO, PROD * 2, capacite_utile_kwh=5.0)


class MoisLePlusDefavorableTest(unittest.TestCase):

    def setUp(self):
        # Douze « mois » d'une journée : le mois 7 reçoit deux fois moins de
        # soleil que les autres — c'est lui qui doit ressortir.
        self.production = []
        for mois in range(1, 13):
            journee = [valeur * (0.25 if mois == 7 else 1.0)
                       for valeur in PROD]
            self.production.extend(journee)
        self.charge = annee(CONSO)
        self.mois = mois_de()

    def test_le_mois_le_plus_defavorable_est_identifie(self):
        resultat = simuler_hors_reseau(
            self.charge, self.production, capacite_utile_kwh=6.0,
            etat_initial_kwh=0.0, mois_par_heure=self.mois)
        pire = resultat['mois_le_plus_defavorable']
        self.assertIsNotNone(pire)
        self.assertEqual(pire['mois'], 7)
        self.assertEqual(pire['libelle'], 'juillet')
        self.assertGreater(pire['taux_defaillance'], 0.0)

    def test_chaque_mois_porte_son_propre_taux(self):
        resultat = simuler_hors_reseau(
            self.charge, self.production, capacite_utile_kwh=6.0,
            etat_initial_kwh=0.0, mois_par_heure=self.mois)
        self.assertEqual(len(resultat['par_mois']), 12)
        for ligne in resultat['par_mois']:
            self.assertIn('taux_defaillance', ligne)

    def test_sans_calendrier_aucun_mois_n_est_devine(self):
        resultat = simuler_hors_reseau(CONSO, PROD, capacite_utile_kwh=5.0)
        self.assertIsNone(resultat['mois_le_plus_defavorable'])
        self.assertEqual(resultat['par_mois'], [])
        self.assertTrue(any('deviné' in m for m in resultat['mentions']))

    def test_un_calendrier_d_une_autre_longueur_est_refuse(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            simuler_hors_reseau(CONSO, PROD, capacite_utile_kwh=5.0,
                                mois_par_heure=[1, 2, 3])
        self.assertEqual(refus.exception.champ, 'mois_par_heure')


class DimensionnementCompletTest(unittest.TestCase):

    def test_la_banque_et_le_risque_sont_publies_ensemble(self):
        resultat = dimensionner_hors_reseau(
            annee(CONSO), annee(PROD), jours_autonomie=2,
            consommation_journaliere_kwh=24.0, dod_pct=80.0,
            source_dod='fiche', mois_par_heure=mois_de())
        self.assertEqual(resultat['banque']['capacite_utile_kwh'], 48.0)
        self.assertEqual(resultat['simulation']['taux_defaillance'], 0.0)

    def test_sans_J_le_dimensionnement_complet_est_refuse(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            dimensionner_hors_reseau(annee(CONSO), annee(PROD),
                                     consommation_journaliere_kwh=24.0,
                                     dod_pct=80.0, source_dod='fiche')
        self.assertEqual(refus.exception.champ, 'jours_autonomie')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
