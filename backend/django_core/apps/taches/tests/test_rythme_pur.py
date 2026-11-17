"""Le rythme pur (reference/regles.md §6) : une table de cas chiffrés, sans base."""
import unittest
from types import SimpleNamespace
from unittest import mock

from apps.taches.choix import StatutJour, StatutTache
from apps.taches.moteur import rythme


def tache(minutes=30, statut=StatutTache.FAIT, parent_id=None, routine=False):
    return SimpleNamespace(statut=statut, estimation_minutes=minutes,
                           parent_id=parent_id, routine=routine)


class CompteDuJourTests(unittest.TestCase):
    """« Ce qui compte comme fait » (§6.1)."""

    def test_ex01_v1_micro_taches_comptees(self):
        # Ex. 1 / variante v1 n° 66 : 4 tâches de 30 min + 3 de 5 min -> 7.
        taches = [tache(30)] * 4 + [tache(5)] * 3
        compte, detail = rythme.compte_du_jour(taches, [])
        self.assertEqual(compte, 7)
        self.assertEqual(detail['micro_non_comptees'], 0)

    def test_ex01_plafond_micro_allume(self):
        # Ex. 1 (règle complète, éteinte en v1) : plafond de 2 micro -> 6.
        taches = [tache(30)] * 4 + [tache(5)] * 3
        with mock.patch.object(rythme, 'PLAFOND_MICRO_ACTIF', True):
            compte, detail = rythme.compte_du_jour(taches, [])
        self.assertEqual(compte, 6)
        self.assertEqual(detail['micro_non_comptees'], 1)

    def test_ex02_sous_taches_et_parent(self):
        # Ex. 2 : 3 sous-tâches + leur parent -> 1.
        taches = [tache(parent_id=1)] * 3 + [tache()]
        compte, detail = rythme.compte_du_jour(taches, [])
        self.assertEqual(compte, 1)
        self.assertEqual(detail['etapes'], 3)

    def test_ex03_routine_tache_et_activites(self):
        # Ex. 3 : 1 routine + 1 tâche + 2 activités closes -> 3.
        compte, detail = rythme.compte_du_jour([tache(routine=True), tache()], ['a', 'b'])
        self.assertEqual(compte, 3)
        self.assertEqual(detail['routines'], 1)
        self.assertEqual(detail['activites_closes'], 2)

    def test_rouverte_et_abandonnee_ne_comptent_pas(self):
        # §6.1 : rouverte = retirée ; abandonnée = 0.
        taches = [tache(statut=StatutTache.A_FAIRE), tache(statut=StatutTache.ANNULE)]
        self.assertEqual(rythme.compte_du_jour(taches, [])[0], 0)

    def test_sans_estimation_compte_un(self):
        # §6.1 : sans estimation = 1.
        self.assertEqual(rythme.compte_du_jour([tache(minutes=None)], [])[0], 1)


class StatutJourTests(unittest.TestCase):
    """« La journée évaluée » (§6.2)."""

    def test_ex04_sans_donnees(self):
        # Ex. 4.
        self.assertEqual(rythme.statut_jour(True, False, 0, False, False), StatutJour.SANS_DONNEES)

    def test_ex05_samedi_non_ouvre(self):
        # Ex. 5 : samedi non travaillé, 2 faites.
        self.assertEqual(rythme.statut_jour(False, False, 2, False, False), StatutJour.NON_OUVRE)

    def test_ex06_evalue(self):
        # Ex. 6 : travaillé, 0 compté, plan validé, app ouverte.
        self.assertEqual(rythme.statut_jour(True, False, 0, True, True), StatutJour.EVALUE)

    def test_conge_prime(self):
        self.assertEqual(rythme.statut_jour(True, True, 3, True, True), StatutJour.CONGE)


class JourneeReussieTests(unittest.TestCase):
    """« Journée réussie et les quatre faits » (§6.4)."""

    def test_ex07_essentiel_fait(self):
        # Ex. 7 : (6, 5, 1 choisi, 1 fait) -> vrai.
        self.assertIs(rythme.journee_reussie(6, 5, 1, 1), True)

    def test_ex08_essentiel_non_fait(self):
        # Ex. 8 : (6, 5, 2 choisis, 0 fait) -> faux.
        self.assertIs(rythme.journee_reussie(6, 5, 2, 0), False)

    def test_ex09_sous_objectif(self):
        # Ex. 9 : (4, 5, 0, 0) -> faux.
        self.assertIs(rythme.journee_reussie(4, 5, 0, 0), False)

    def test_sans_objectif_none(self):
        self.assertIsNone(rythme.journee_reussie(4, None, 0, 0))


class ArrondiEtPlafondTests(unittest.TestCase):
    def test_arrondir_demie_vers_le_bas(self):
        # §0 : ceil(x - 0,5).
        cas = {5.5: 5, 5.51: 6, 4.5: 4, 5.6: 6, 5.49: 5, 1.0: 1, 6.5: 6}
        for entree, attendu in cas.items():
            with self.subTest(x=entree):
                self.assertEqual(rythme.arrondir(entree), attendu)

    def test_ex56_plafonner_jours(self):
        # Ex. 56 : 13 × 5 + 30 -> le 30 devient 11.
        sortie = rythme.plafonner_jours([5] * 13 + [30])
        self.assertEqual(sortie, [5] * 13 + [11])

    def test_plafonner_vide(self):
        self.assertEqual(rythme.plafonner_jours([]), [])


if __name__ == '__main__':
    unittest.main()
