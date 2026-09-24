"""CALX272 — les seuils de protection de la batterie hors-réseau, SAISIS.

Ce qui est tenu ici (le « Done » de la tâche) :

* seuils 30/20/10 % sur une série qui, sans eux, fait descendre la banque à
  5 % ⇒ heures d'ARRÊT non vides et état de charge JAMAIS publié sous
  ``arret_pct`` ;
* ordre incohérent (``veille_pct < arret_pct``) ⇒ refus nommant
  ``seuils.veille_pct`` ;
* sans seuils, la sortie est TERME À TERME celle d'aujourd'hui (instantané
  relevé sur le code d'avant CALX272), et le bilan le DIT ;
* aucune règle de dimensionnement étrangère n'est importée : le « 4,8 kWh
  par kWc » de PV*SOL n'est pas un défaut du module.

Tests PURS : aucune base, aucun réseau. Séries SYNTHÉTIQUES.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

from django.test import SimpleTestCase

from apps.calepinage.services.hors_reseau import (
    ETATS_PROTECTION, HorsReseauInvalide, dimensionner_hors_reseau,
    simuler_hors_reseau,
)

SOURCE = (pathlib.Path(__file__).resolve().parents[1] / 'services'
          / 'hors_reseau.py')

SEUILS = {'veille_pct': 30, 'entretien_pct': 20, 'arret_pct': 10}

#: Banque de 10 kWh utiles, PLEINE : 9,5 kWh appelés la première heure la
#: font descendre à 5 % sans protection. Du soleil revient à la 4e heure.
CONSO_CHUTE = [9.5, 1.0, 1.0, 1.0]
PROD_CHUTE = [0.0, 0.0, 0.0, 3.0]
BANQUE = dict(capacite_utile_kwh=10.0, rendement_ar_pct=100.0,
              etat_initial_kwh=10.0)


class DescenteA5PourcentTest(unittest.TestCase):

    def test_sans_seuils_la_banque_descend_a_5_pourcent(self):
        resultat = simuler_hors_reseau(CONSO_CHUTE, PROD_CHUTE, **BANQUE)
        self.assertAlmostEqual(resultat['etat_de_charge_kwh'][0], 0.5,
                               delta=1e-6)

    def test_les_seuils_arretent_la_banque_sans_jamais_passer_sous_10(self):
        resultat = simuler_hors_reseau(CONSO_CHUTE, PROD_CHUTE,
                                       seuils=SEUILS, **BANQUE)
        protection = resultat['protection']
        self.assertTrue(protection['plages_par_etat']['arret'])
        self.assertGreater(protection['heures_par_etat']['arret'], 0)
        plancher = 10.0 * SEUILS['arret_pct'] / 100.0
        for etat in resultat['etat_de_charge_kwh']:
            self.assertGreaterEqual(etat, plancher - 1e-9)
        self.assertEqual(protection['arret_au_pas'], 1)
        self.assertEqual(protection['plages_par_etat']['arret'], [[1, 3]])

    def test_une_banque_coupee_ne_se_recharge_plus(self):
        resultat = simuler_hors_reseau(CONSO_CHUTE, PROD_CHUTE,
                                       seuils=SEUILS, **BANQUE)
        # Le soleil de la 4e heure n'entre pas : la banque est COUPÉE.
        self.assertAlmostEqual(resultat['etat_de_charge_kwh'][3], 1.0,
                               delta=1e-6)
        self.assertAlmostEqual(resultat['surplus_perdu_kwh'], 2.0, delta=1e-6)
        self.assertTrue(any('Arrêt complet' in texte
                            for texte in resultat['mentions']))

    def test_les_heures_par_etat_couvrent_toute_la_serie(self):
        resultat = simuler_hors_reseau(CONSO_CHUTE, PROD_CHUTE,
                                       seuils=SEUILS, **BANQUE)
        heures = resultat['protection']['heures_par_etat']
        self.assertEqual(set(heures), set(ETATS_PROTECTION))
        self.assertEqual(sum(heures.values()), resultat['heures'])


class VeilleEtEntretienTest(unittest.TestCase):

    def test_sous_la_veille_l_onduleur_ne_decharge_plus(self):
        # 2,5 kWh par heure : 100 → 75 → 50 → 25 % ; à 25 % (veille) plus
        # rien ne sort, jusqu'au soleil de la 6e heure.
        conso = [2.5] * 8
        prod = [0.0] * 5 + [5.0] + [0.0] * 2
        resultat = simuler_hors_reseau(conso, prod, seuils=SEUILS, **BANQUE)
        etats = resultat['etat_de_charge_kwh']
        self.assertAlmostEqual(etats[2], 2.5, delta=1e-6)
        self.assertAlmostEqual(etats[3], 2.5, delta=1e-6)
        self.assertAlmostEqual(etats[4], 2.5, delta=1e-6)
        # Le soleil recharge au-dessus de la veille : le service reprend.
        self.assertAlmostEqual(etats[5], 5.0, delta=1e-6)
        self.assertAlmostEqual(etats[6], 2.5, delta=1e-6)
        # Veille aux pas 3, 4 et 5 (le soleil recharge PENDANT le pas 5),
        # service normal au pas 6, de nouveau la veille au pas 7.
        heures = resultat['protection']['heures_par_etat']
        self.assertEqual(heures['veille'], 4)
        self.assertEqual(resultat['protection']['plages_par_etat']['veille'],
                         [[3, 5], [7, 7]])
        self.assertEqual(heures['arret'], 0)
        self.assertIsNone(resultat['protection']['arret_au_pas'])

    def test_l_entretien_est_compte_et_sa_source_ac_absente_est_dite(self):
        # 35 % puis 2 kWh appelés : 15 %, dans la zone d'entretien.
        resultat = simuler_hors_reseau(
            [2.0, 1.0, 1.0], [0.0, 0.0, 0.0], seuils=SEUILS,
            capacite_utile_kwh=10.0, rendement_ar_pct=100.0,
            etat_initial_kwh=3.5)
        heures = resultat['protection']['heures_par_etat']
        self.assertEqual(heures['normal'], 1)
        self.assertEqual(heures['entretien'], 2)
        self.assertAlmostEqual(resultat['etat_de_charge_kwh'][-1], 1.5,
                               delta=1e-6)
        self.assertTrue(any('recharge d’entretien' in texte
                            and 'groupe électrogène' in texte
                            for texte in resultat['mentions']))


class RefusTest(unittest.TestCase):

    def _simuler(self, seuils):
        return simuler_hors_reseau(CONSO_CHUTE, PROD_CHUTE, seuils=seuils,
                                   **BANQUE)

    def test_une_veille_sous_l_arret_est_refusee_en_la_nommant(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            self._simuler({'veille_pct': 5, 'entretien_pct': 8,
                           'arret_pct': 10})
        self.assertEqual(refus.exception.champ, 'seuils.veille_pct')

    def test_un_entretien_hors_de_la_fourchette_est_nomme(self):
        for entretien in (40, 5):
            with self.subTest(entretien=entretien):
                with self.assertRaises(HorsReseauInvalide) as refus:
                    self._simuler({'veille_pct': 30,
                                   'entretien_pct': entretien,
                                   'arret_pct': 10})
                self.assertEqual(refus.exception.champ,
                                 'seuils.entretien_pct')

    def test_un_seuil_manquant_ou_hors_bornes_est_nomme(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            self._simuler({'veille_pct': 30, 'entretien_pct': 20})
        self.assertEqual(refus.exception.champ, 'seuils.arret_pct')
        with self.assertRaises(HorsReseauInvalide) as refus:
            self._simuler({'veille_pct': 130, 'entretien_pct': 20,
                           'arret_pct': 10})
        self.assertEqual(refus.exception.champ, 'seuils.veille_pct')

    def test_des_seuils_illisibles_sont_refuses(self):
        with self.assertRaises(HorsReseauInvalide) as refus:
            self._simuler([30, 20, 10])
        self.assertEqual(refus.exception.champ, 'seuils')


class SansSeuilsTest(unittest.TestCase):
    """Sans seuils : la sortie d'AUJOURD'HUI, terme à terme, et c'est DIT."""

    CONSO = [1.0, 1.0, 2.0, 2.0, 1.0, 0.5, 0.5, 1.5, 1.0, 1.0, 3.0, 1.0]
    PROD = [0.0, 0.0, 0.0, 1.0, 3.0, 4.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    ENTREE = dict(capacite_utile_kwh=4.0, rendement_ar_pct=90.0,
                  mois_par_heure=[1] * 6 + [2] * 6, puissance_charge_kw=2.0,
                  puissance_decharge_kw=2.5)

    #: Instantané relevé sur le code d'AVANT CALX272 (même entrée).
    AVANT = {
        'heures': 12, 'consommation_kwh': 15.5, 'production_kwh': 12.0,
        'servi_kwh': 11.589, 'defaillance_kwh': 3.911,
        'heures_defaillantes': 4, 'taux_defaillance': 0.2523,
        'surplus_perdu_kwh': 3.784,
        'etat_de_charge_kwh': [2.9459, 1.8918, 0.0, 0.0, 1.8974, 3.7947,
                               4.0, 3.473, 2.4189, 1.3648, 0.0, 0.0],
        'par_mois': [
            {'mois': 1, 'libelle': 'janvier', 'consommation_kwh': 7.5,
             'defaillance_kwh': 1.205, 'heures_defaillantes': 2,
             'taux_defaillance': 0.1607},
            {'mois': 2, 'libelle': 'février', 'consommation_kwh': 8.0,
             'defaillance_kwh': 2.705, 'heures_defaillantes': 2,
             'taux_defaillance': 0.3382}],
        'mois_le_plus_defavorable': {
            'mois': 2, 'libelle': 'février', 'consommation_kwh': 8.0,
            'defaillance_kwh': 2.705, 'heures_defaillantes': 2,
            'taux_defaillance': 0.3382},
        'mentions': ['Banque supposée PLEINE au premier pas : c’est '
                     'l’hypothèse la plus favorable, et elle est annoncée.'],
    }

    def test_la_sortie_est_terme_a_terme_celle_d_aujourd_hui(self):
        resultat = simuler_hors_reseau(self.CONSO, self.PROD, **self.ENTREE)
        for cle, valeur in self.AVANT.items():
            with self.subTest(cle=cle):
                self.assertEqual(resultat[cle], valeur)

    def test_le_bilan_dit_qu_aucun_seuil_n_est_saisi(self):
        resultat = simuler_hors_reseau(self.CONSO, self.PROD, **self.ENTREE)
        protection = resultat['protection']
        self.assertIn('Aucun seuil de protection', protection['motif'])
        for cle in ('seuils', 'heures_par_etat', 'plages_par_etat',
                    'arret_au_pas'):
            self.assertIsNone(protection[cle])

    def test_le_dimensionnement_transmet_les_seuils(self):
        rendu = dimensionner_hors_reseau(
            CONSO_CHUTE, PROD_CHUTE, jours_autonomie=1,
            consommation_journaliere_kwh=10.0, dod_pct=100.0,
            rendement_ar_pct=100.0, etat_initial_kwh=10.0, seuils=SEUILS)
        self.assertEqual(rendu['simulation']['protection']['seuils'],
                         {'veille_pct': 30.0, 'entretien_pct': 20.0,
                          'arret_pct': 10.0})


class ChaineDeSimulationTest(SimpleTestCase):
    """Le document déclare ``hors_reseau.seuils`` : la chaîne les applique."""

    def _bloc(self, **hors):
        from apps.calepinage.services.etapes import hors_reseau as bloc
        from apps.calepinage.tests.test_calx191_hors_reseau import (
            contexte_de_test, serie_de_test,
        )

        contexte = contexte_de_test(heures=720, jours=0.25)
        contexte[bloc.CLE_CONTEXTE].update(hors)
        return bloc.bloc_hors_reseau(serie_de_test(heures=720), contexte)

    def test_les_seuils_declares_atteignent_la_simulation(self):
        _suite, sans = self._bloc()
        _suite, avec = self._bloc(seuils=SEUILS)
        self.assertEqual(avec['motif_absence'], '')
        self.assertTrue(any('Seuils de protection SAISIS' in texte
                            for texte in avec['mentions']))
        self.assertFalse(any('Seuils de protection SAISIS' in texte
                             for texte in sans['mentions']))
        self.assertGreaterEqual(avec['soc_minimal_pct'],
                                SEUILS['arret_pct'] - 0.01)

    def test_un_ordre_incoherent_omet_le_bloc_en_le_nommant(self):
        _suite, resultat = self._bloc(seuils={'veille_pct': 5,
                                              'entretien_pct': 8,
                                              'arret_pct': 10})
        self.assertIsNone(resultat['taux_defaillance'])
        self.assertIn('seuils.veille_pct', resultat['motif_absence'])


class AucuneRegleEtrangereTest(unittest.TestCase):
    """Le « 4,8 kWh par kWc » de PV*SOL n'est PAS un défaut du module."""

    def test_aucun_litteral_4_8_dans_le_code(self):
        arbre = ast.parse(SOURCE.read_text(encoding='utf-8'))
        litteraux = [noeud.value for noeud in ast.walk(arbre)
                     if isinstance(noeud, ast.Constant)
                     and isinstance(noeud.value, (int, float))
                     and not isinstance(noeud.value, bool)]
        self.assertNotIn(4.8, litteraux)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
