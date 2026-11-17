"""TCH29 — sollicitations pures (regles.md §7) : unittest pur, sans base ni horloge vivante."""
import unittest
from dataclasses import replace
from datetime import date, datetime, time

from apps.taches.moteur.sollicitations import (
    Fenetre, PrefsSollicitation, choisir_relance, departager, due,
    etat_decroissance, plafond_atteint, raison_saut, variante)

FENETRE = Fenetre(time(8, 30), time(19, 0))
PREFS = PrefsSollicitation(nb_jour_et_propose=3, nb_faites=2, motif_relance='echeance')


def le(h, m=0, jour=17):
    """Mardi 17/11/2026 par défaut."""
    return datetime(2026, 11, jour, h, m)


class VarianteTests(unittest.TestCase):
    def test_rotation_des_ordinaux_de_la_reference(self):
        self.assertEqual(variante(739572), 0)
        self.assertEqual(variante(739573), 1)
        self.assertEqual(variante(739574), 2)

    def test_17_novembre_2026_donne_2(self):
        self.assertEqual(variante(date(2026, 11, 17).toordinal()), 2)


class ChoisirRelanceTests(unittest.TestCase):
    def test_neglige_et_echeance_donne_echeance(self):  # ligne 38
        self.assertEqual(choisir_relance({'neglige', 'echeance'}), 'echeance')

    def test_neglige_et_derive_donne_derive(self):  # ligne 39
        self.assertEqual(choisir_relance({'neglige', 'derive'}), 'derive')

    def test_vide_donne_none(self):  # ligne 40
        self.assertIsNone(choisir_relance(set()))

    def test_echeance_avant_derive(self):
        self.assertEqual(choisir_relance(['derive', 'echeance']), 'echeance')

    def test_neglige_seul(self):
        self.assertEqual(choisir_relance(['neglige']), 'neglige')

    def test_motif_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            choisir_relance({'inconnu'})


class DecroissanceTests(unittest.TestCase):
    def test_14_ignorees_de_suite_donne_pause(self):  # ligne 41
        self.assertEqual(etat_decroissance([True] * 14), 'pause')

    def test_13_ignorees_donne_normal(self):  # ligne 42
        self.assertEqual(etat_decroissance([True] * 13), 'normal')

    def test_20_puis_une_ouverte_donne_normal(self):  # ligne 43
        self.assertEqual(etat_decroissance([True] * 20 + [False]), 'normal')

    def test_une_ouverture_remet_la_serie_a_zero(self):
        suite = [True] * 10 + [False] + [True] * 13
        self.assertEqual(etat_decroissance(suite), 'normal')
        self.assertEqual(etat_decroissance(suite + [True]), 'pause')

    def test_vide_donne_normal(self):
        self.assertEqual(etat_decroissance([]), 'normal')


class PlafondTests(unittest.TestCase):
    def test_trois_envois_atteignent_le_plafond(self):
        self.assertTrue(plafond_atteint(['plan_matin', 'relance', 'bilan_soir']))

    def test_matin_soir_et_revue_comptent(self):
        self.assertTrue(plafond_atteint(['plan_matin', 'relance', 'revue_semaine']))

    def test_deux_envois_ne_l_atteignent_pas(self):
        self.assertFalse(plafond_atteint(['plan_matin', 'relance']))

    def test_rappels_et_test_hors_plafond(self):
        journal = ['rappel', 'rappel', 'rappel', 'test', 'plan_matin']
        self.assertFalse(plafond_atteint(journal))

    def test_vide(self):
        self.assertFalse(plafond_atteint([]))


class DueTests(unittest.TestCase):
    def test_pile_a_l_heure(self):
        self.assertTrue(due('plan_matin', le(8, 30), replace(PREFS), FENETRE))

    def test_dans_le_tick_de_15_minutes(self):
        self.assertTrue(due('plan_matin', le(8, 44), PREFS, FENETRE))

    def test_apres_le_tick_rien_n_est_rattrape(self):
        self.assertFalse(due('plan_matin', le(8, 45), PREFS, FENETRE))
        self.assertFalse(due('plan_matin', le(11, 0), PREFS, FENETRE))

    def test_avant_l_heure(self):
        self.assertFalse(due('plan_matin', le(8, 29), PREFS, FENETRE))

    def test_relance_a_15_h_avec_motif(self):
        self.assertTrue(due('relance', le(15, 5), PREFS, FENETRE))

    def test_relance_sans_motif(self):
        prefs = replace(PREFS, motif_relance=None)
        self.assertFalse(due('relance', le(15, 0), prefs, FENETRE))
        self.assertEqual(raison_saut('relance', le(15, 0), prefs, FENETRE), 'condition')

    def test_bilan_a_18_h_si_une_faite(self):
        self.assertTrue(due('bilan_soir', le(18, 0), PREFS, FENETRE))

    def test_bilan_sans_plan_ni_faite(self):
        prefs = replace(PREFS, nb_faites=0, plan_valide=False)
        self.assertFalse(due('bilan_soir', le(18, 0), prefs, FENETRE))

    def test_bilan_si_plan_valide_meme_sans_faite(self):
        prefs = replace(PREFS, nb_faites=0, plan_valide=True)
        self.assertTrue(due('bilan_soir', le(18, 0), prefs, FENETRE))

    def test_matin_saute_si_plan_deja_valide(self):
        prefs = replace(PREFS, plan_valide=True)
        self.assertFalse(due('plan_matin', le(8, 30), prefs, FENETRE))

    def test_matin_saute_sans_tache_du_jour_ni_propose(self):
        prefs = replace(PREFS, nb_jour_et_propose=0)
        self.assertFalse(due('plan_matin', le(8, 30), prefs, FENETRE))

    def test_type_off(self):
        prefs = replace(PREFS, heure_matin=None)
        self.assertEqual(raison_saut('plan_matin', le(8, 30), prefs, FENETRE), 'off')
        self.assertFalse(due('plan_matin', le(8, 30), prefs, FENETRE))

    def test_type_inconnu(self):
        with self.assertRaises(ValueError):
            due('rappel', le(8, 30), PREFS, FENETRE)


class RevueTests(unittest.TestCase):
    def test_revue_auto_le_dernier_jour_travaille(self):
        prefs = replace(PREFS, dernier_jour_travaille_semaine=True)
        self.assertTrue(due('revue_semaine', le(18, 0), prefs, FENETRE))

    def test_revue_a_la_place_du_bilan_jamais_en_plus(self):
        prefs = replace(PREFS, dernier_jour_travaille_semaine=True)
        self.assertFalse(due('bilan_soir', le(18, 0), prefs, FENETRE))

    def test_hors_jour_de_revue_pas_de_revue(self):
        self.assertFalse(due('revue_semaine', le(18, 0), PREFS, FENETRE))

    def test_revue_un_jour_nomme(self):
        prefs = replace(PREFS, revue_semaine=1)  # mardi
        self.assertTrue(due('revue_semaine', le(18, 0), prefs, FENETRE))
        self.assertFalse(due('bilan_soir', le(18, 0), prefs, FENETRE))
        prefs = replace(PREFS, revue_semaine=4)
        self.assertFalse(due('revue_semaine', le(18, 0), prefs, FENETRE))
        self.assertTrue(due('bilan_soir', le(18, 0), prefs, FENETRE))

    def test_revue_off_garde_le_bilan(self):
        prefs = replace(PREFS, revue_semaine='off', dernier_jour_travaille_semaine=True)
        self.assertFalse(due('revue_semaine', le(18, 0), prefs, FENETRE))
        self.assertTrue(due('bilan_soir', le(18, 0), prefs, FENETRE))


class SautTests(unittest.TestCase):
    """« Sauté, jamais différé » : chaque cas de regles.md §7."""

    def verifier(self, raison, **champs):
        prefs = replace(PREFS, **champs)
        self.assertEqual(raison_saut('plan_matin', le(8, 30), prefs, FENETRE), raison)
        self.assertFalse(due('plan_matin', le(8, 30), prefs, FENETRE))

    def test_cas_de_base_part(self):
        self.assertIsNone(raison_saut('plan_matin', le(8, 30), PREFS, FENETRE))

    def test_fenetre_de_la_societe_fermee(self):
        prefs = replace(PREFS, heure_matin=time(7, 0))
        self.assertEqual(raison_saut('plan_matin', le(7, 0), prefs, FENETRE), 'fenetre_fermee')
        self.assertFalse(due('plan_matin', le(7, 0), prefs, FENETRE))

    def test_apres_l_heure_limite(self):
        prefs = replace(PREFS, heure_soir=time(20, 0))
        fenetre = Fenetre(time(8, 0), time(21, 0))
        self.assertEqual(raison_saut('bilan_soir', le(20, 0), prefs, fenetre), 'heure_limite')
        self.assertFalse(due('bilan_soir', le(20, 0), prefs, fenetre))

    def test_jour_non_travaille(self):
        self.verifier('jour_non_travaille', jour_travaille=False)

    def test_conge(self):
        self.verifier('conge', en_conge=True)

    def test_type_en_pause(self):
        self.verifier('pause', pauses=('plan_matin',))

    def test_autre_type_en_pause_ne_gene_pas(self):
        prefs = replace(PREFS, pauses=('relance',))
        self.assertTrue(due('plan_matin', le(8, 30), prefs, FENETRE))

    def test_compte_inactif(self):
        self.verifier('compte', compte_actif=False)

    def test_compte_non_interne(self):
        self.verifier('compte', compte_interne=False)

    def test_module_eteint(self):
        self.verifier('module_eteint', module_actif=False)

    def test_compte_sans_reglages_rythme(self):
        self.verifier('sans_reglages', a_reglages_rythme=False)

    def test_plafond_atteint(self):
        self.verifier('plafond', plafond_atteint=True)

    def test_coupe_circuit(self):
        self.verifier('coupe_circuit', balayage_actif=False)

    def test_saute_jamais_differe(self):
        prefs = replace(PREFS, en_conge=True)
        ticks = [le(8, m) for m in (30, 40, 50)] + [le(9, 0), le(12, 0)]
        self.assertFalse(any(due('plan_matin', t, prefs, FENETRE) for t in ticks))
        # Le conge levé plus tard ne rattrape pas le matin manqué.
        libre = replace(PREFS, en_conge=False)
        self.assertFalse(due('plan_matin', le(9, 0), libre, FENETRE))


class PrioriteTests(unittest.TestCase):
    def test_matin_avant_relance_avant_bilan(self):
        self.assertEqual(departager(['bilan_soir', 'relance', 'plan_matin']),
                         ('plan_matin', ('relance', 'bilan_soir')))

    def test_relance_avant_bilan(self):
        self.assertEqual(departager(['bilan_soir', 'relance']), ('relance', ('bilan_soir',)))

    def test_rien(self):
        self.assertEqual(departager([]), (None, ()))

    def test_un_seul(self):
        self.assertEqual(departager(['revue_semaine']), ('revue_semaine', ()))


if __name__ == '__main__':
    unittest.main()
