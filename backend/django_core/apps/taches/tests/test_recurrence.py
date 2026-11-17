"""TCH10 — récurrence pure : les 25 cas datés B1-B25 de reference/regles.md §2
(unittest pur, sans base, sans horloge ; fériés injectés 18/11/2026 et 01/01/2027).
"""
import unittest
from datetime import date, datetime

from apps.taches.moteur.recurrence import (
    RegleRecurrencePure as Regle, est_routine, libelle_regle,
    n_ieme_jour_du_mois, premiere_occurrence, prochaine_occurrence)

FERIES = {date(2026, 11, 18), date(2027, 1, 1)}
LUN, MAR, MER, JEU, VEN, SAM, DIM = range(7)


def est_ouvre(d):
    """Lundi-vendredi hors fériés injectés."""
    return d.weekday() < 5 and d not in FERIES


def masque(*jours):
    return ''.join('1' if i in jours else '0' for i in range(7))


def suivante(regle, occurrence, fait):
    """Occurrence suivante quand `occurrence` est faite (ou sautée) le `fait`."""
    return prochaine_occurrence(
        regle, occurrence, fait, datetime(fait.year, fait.month, fait.day, 12, 0),
        est_ouvre)


class CasDatesCalendrierTests(unittest.TestCase):
    """B1-B13 et B18-B25 : mode calendrier."""

    def hebdo_lundi(self, **kw):
        return Regle('hebdo', date(2026, 11, 17), jours_semaine=masque(LUN), **kw)

    def test_B1_creation_hebdo_lundi(self):
        self.assertEqual(premiere_occurrence(self.hebdo_lundi()), date(2026, 11, 23))

    def test_B2_hebdo_fait_le_jour(self):
        self.assertEqual(
            suivante(self.hebdo_lundi(), date(2026, 11, 23), date(2026, 11, 23)),
            date(2026, 11, 30))

    def test_B3_hebdo_en_avance(self):
        self.assertEqual(
            suivante(self.hebdo_lundi(), date(2026, 11, 23), date(2026, 11, 21)),
            date(2026, 11, 30))

    def test_B4_hebdo_en_retard_sans_pile(self):
        self.assertEqual(
            suivante(self.hebdo_lundi(), date(2026, 11, 23), date(2026, 12, 2)),
            date(2026, 12, 7))

    def test_B5_hebdo_sautee(self):
        self.assertEqual(
            suivante(self.hebdo_lundi(), date(2026, 11, 23), date(2026, 11, 17)),
            date(2026, 11, 30))

    def test_B6_mensuel_31_creation(self):
        regle = Regle('mensuel', date(2026, 11, 17), jour_du_mois=31)
        self.assertEqual(premiere_occurrence(regle), date(2026, 11, 30))

    def test_B7_mensuel_31_janvier_vers_fevrier(self):
        regle = Regle('mensuel', date(2026, 11, 17), jour_du_mois=31)
        self.assertEqual(
            suivante(regle, date(2027, 1, 31), date(2027, 1, 31)), date(2027, 2, 28))

    def test_B8_mensuel_31_fevrier_vers_mars(self):
        regle = Regle('mensuel', date(2026, 11, 17), jour_du_mois=31)
        self.assertEqual(
            suivante(regle, date(2027, 2, 28), date(2027, 2, 28)), date(2027, 3, 31))

    def test_B9_chaque_fin_de_mois(self):
        regle = Regle('mensuel', date(2026, 11, 17), jour_du_mois=-1)
        self.assertEqual(
            suivante(regle, date(2026, 11, 30), date(2026, 11, 30)), date(2026, 12, 31))

    def test_B10_jours_ouvres_ferie_18_11(self):
        regle = Regle('jours_ouvres', date(2026, 11, 17))
        self.assertEqual(
            suivante(regle, date(2026, 11, 17), date(2026, 11, 17)), date(2026, 11, 19))

    def test_B11_jours_ouvres_vendredi_vers_lundi(self):
        regle = Regle('jours_ouvres', date(2026, 11, 17))
        self.assertEqual(
            suivante(regle, date(2026, 11, 20), date(2026, 11, 20)), date(2026, 11, 23))

    def test_B12_jours_ouvres_ferie_1_janvier(self):
        regle = Regle('jours_ouvres', date(2026, 11, 17))
        self.assertEqual(
            suivante(regle, date(2026, 12, 31), date(2026, 12, 31)), date(2027, 1, 4))

    def test_B13_quotidien_tous_les_2_jours(self):
        regle = Regle('quotidien', date(2026, 11, 17), intervalle=2)
        self.assertEqual(
            suivante(regle, date(2026, 11, 17), date(2026, 11, 18)), date(2026, 11, 19))

    def test_B18_hebdo_2_semaines_lun_jeu_creation(self):
        regle = Regle('hebdo', date(2026, 11, 17), intervalle=2,
                      jours_semaine=masque(LUN, JEU))
        self.assertEqual(premiere_occurrence(regle), date(2026, 11, 19))

    def test_B19_hebdo_2_semaines_jeudi_vers_lundi(self):
        regle = Regle('hebdo', date(2026, 11, 17), intervalle=2,
                      jours_semaine=masque(LUN, JEU))
        self.assertEqual(
            suivante(regle, date(2026, 11, 19), date(2026, 11, 19)), date(2026, 11, 30))

    def test_B20_hebdo_2_semaines_lundi_vers_jeudi(self):
        regle = Regle('hebdo', date(2026, 11, 17), intervalle=2,
                      jours_semaine=masque(LUN, JEU))
        self.assertEqual(
            suivante(regle, date(2026, 11, 30), date(2026, 11, 30)), date(2026, 12, 3))

    def test_B21_annuel_29_fevrier(self):
        regle = Regle('annuel', date(2028, 2, 29))
        self.assertEqual(
            suivante(regle, date(2028, 2, 29), date(2028, 2, 29)), date(2029, 2, 28))

    def test_B22_date_fin_serie_close(self):
        regle = self.hebdo_lundi(date_fin=date(2026, 11, 25))
        self.assertIsNone(suivante(regle, date(2026, 11, 23), date(2026, 11, 23)))

    def test_B23_premier_vendredi_du_mois_creation(self):
        regle = Regle('mensuel', date(2026, 11, 17), jours_semaine=masque(VEN),
                      rang_dans_mois=1)
        self.assertEqual(premiere_occurrence(regle), date(2026, 12, 4))

    def test_B24_premier_vendredi_ferie_ignore(self):
        regle = Regle('mensuel', date(2026, 11, 17), jours_semaine=masque(VEN),
                      rang_dans_mois=1)
        self.assertEqual(
            suivante(regle, date(2026, 12, 4), date(2026, 12, 4)), date(2027, 1, 1))

    def test_B25_dernier_vendredi_du_mois_creation(self):
        regle = Regle('mensuel', date(2026, 11, 17), jours_semaine=masque(VEN),
                      rang_dans_mois=-1)
        self.assertEqual(premiere_occurrence(regle), date(2026, 11, 27))


class CasDatesApresFaitTests(unittest.TestCase):
    """B14-B17 : mode après avoir fait."""

    def apres_fait(self, frequence, intervalle, **kw):
        return Regle(frequence, date(2026, 11, 17), intervalle=intervalle,
                     mode='apres_fait', **kw)

    def test_B14_quotidien_3_jours(self):
        regle = self.apres_fait('quotidien', 3)
        self.assertEqual(
            suivante(regle, None, date(2026, 11, 20)), date(2026, 11, 23))

    def test_B15_mensuel_3_mois(self):
        regle = self.apres_fait('mensuel', 3)
        self.assertEqual(
            suivante(regle, None, date(2027, 1, 20)), date(2027, 4, 20))

    def test_B16_mensuel_1_mois_borne_a_fin_de_mois(self):
        regle = self.apres_fait('mensuel', 1)
        self.assertEqual(
            suivante(regle, None, date(2027, 1, 31)), date(2027, 2, 28))

    def test_B17_2_jours_ouvres(self):
        regle = self.apres_fait('jours_ouvres', 2)
        self.assertEqual(
            suivante(regle, None, date(2026, 11, 17)), date(2026, 11, 20))


class ComplementsTests(unittest.TestCase):
    """Garde-fous hors table : le moteur reste pur et déterministe."""

    def test_le_decalage_mensuel_apres_fait_s_enchaine(self):
        regle = Regle('mensuel', date(2026, 11, 17), intervalle=1, mode='apres_fait')
        premier = suivante(regle, None, date(2027, 1, 31))
        self.assertEqual(premier, date(2027, 2, 28))
        self.assertEqual(suivante(regle, None, premier), date(2027, 3, 28))

    def test_premiere_occurrence_apres_fait_est_la_date_de_debut(self):
        regle = Regle('mensuel', date(2026, 11, 17), intervalle=3, mode='apres_fait')
        self.assertEqual(premiere_occurrence(regle), date(2026, 11, 17))

    def test_regle_arretee_ne_donne_plus_rien(self):
        regle = Regle('quotidien', date(2026, 11, 17), actif=False)
        self.assertIsNone(suivante(regle, date(2026, 11, 17), date(2026, 11, 17)))

    def test_hebdo_apres_fait_masque_a_partir_de_fait_plus_7n_moins_6(self):
        regle = Regle('hebdo', date(2026, 11, 17), jours_semaine=masque(LUN),
                      mode='apres_fait')
        # fait mar 17/11 : premier lundi >= 18/11 = 23/11
        self.assertEqual(
            suivante(regle, None, date(2026, 11, 17)), date(2026, 11, 23))

    def test_n_ieme_jour_du_mois(self):
        self.assertEqual(n_ieme_jour_du_mois(2026, 11, VEN, 1), date(2026, 11, 6))
        self.assertEqual(n_ieme_jour_du_mois(2026, 11, VEN, 4), date(2026, 11, 27))
        self.assertEqual(n_ieme_jour_du_mois(2026, 11, VEN, -1), date(2026, 11, 27))
        self.assertEqual(n_ieme_jour_du_mois(2026, 11, LUN, -1), date(2026, 11, 30))

    def test_annuel_retour_au_29_fevrier_en_annee_bissextile(self):
        regle = Regle('annuel', date(2028, 2, 29))
        self.assertEqual(
            suivante(regle, date(2031, 2, 28), date(2031, 2, 28)), date(2032, 2, 29))

    def test_est_routine(self):
        self.assertTrue(est_routine(Regle('quotidien', date(2026, 11, 17))))
        self.assertTrue(est_routine(Regle('jours_ouvres', date(2026, 11, 17))))
        self.assertFalse(est_routine(Regle('quotidien', date(2026, 11, 17), intervalle=2)))
        self.assertFalse(est_routine(Regle('hebdo', date(2026, 11, 17))))

    def test_libelles(self):
        d = date(2026, 11, 17)
        cas = [
            (Regle('quotidien', d), 'chaque jour'),
            (Regle('quotidien', d, intervalle=2), 'tous les 2 jours'),
            (Regle('jours_ouvres', d), 'chaque jour travaillé'),
            (Regle('hebdo', d, jours_semaine=masque(LUN)), 'chaque lundi'),
            (Regle('hebdo', d, jours_semaine=masque(LUN, JEU)), 'chaque lundi et jeudi'),
            (Regle('hebdo', d, intervalle=2, jours_semaine=masque(LUN)),
             'toutes les 2 semaines le lundi'),
            (Regle('mensuel', d, jour_du_mois=5), 'chaque mois le 5'),
            (Regle('mensuel', d, jour_du_mois=-1), 'chaque fin de mois'),
            (Regle('mensuel', d, jours_semaine=masque(VEN), rang_dans_mois=1),
             'chaque premier vendredi du mois'),
            (Regle('mensuel', d, jours_semaine=masque(VEN), rang_dans_mois=-1),
             'chaque dernier vendredi du mois'),
            (Regle('mensuel', d, intervalle=3), 'tous les 3 mois'),
            (Regle('annuel', date(2026, 3, 5)), 'chaque année le 05/03'),
            (Regle('quotidien', d, intervalle=3, mode='apres_fait'),
             'tous les 3 jours après fait'),
            (Regle('hebdo', d, jours_semaine=masque(LUN), date_fin=date(2026, 12, 31)),
             "chaque lundi jusqu'au 31/12/2026"),
        ]
        for regle, attendu in cas:
            with self.subTest(attendu=attendu):
                self.assertEqual(libelle_regle(regle), attendu)


if __name__ == '__main__':
    unittest.main()
