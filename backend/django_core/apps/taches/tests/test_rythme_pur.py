"""Le rythme pur (reference/regles.md §6) : une table de cas chiffrés, sans base."""
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from apps.taches.choix import ModeRythme, SourceObjectif, StatutJour, StatutTache
from apps.taches.moteur import rythme
from apps.taches.moteur.rythme import EtatRythme

J0 = date(2026, 1, 1)


def jour_n(n):
    """Le « jour n » des exemples : J0 + n jours."""
    return J0 + timedelta(days=n)


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


class PalierInitialTests(unittest.TestCase):
    """Démarrage à froid (§6.5 point 2)."""

    def test_ex10_rien_dit_type_cinq(self):
        # Ex. 10 : [5,4,6,5,3,7,5,6,4,5], rien dit -> (aucun, 5, aucune carte).
        self.assertEqual(rythme.palier_initial([5, 4, 6, 5, 3, 7, 5, 6, 4, 5], None), (None, 5, None))

    def test_ex11_rafales_propose_sans_imposer(self):
        # Ex. 11 : [9,10,9,1,2,1,2,9,10,9] -> (aucun, 6, carte `premier`).
        self.assertEqual(rythme.palier_initial([9, 10, 9, 1, 2, 1, 2, 9, 10, 9], None),
                         (None, 6, 'premier'))

    def test_ex12_objectif_dit_garde(self):
        # Ex. 12 : [3,3,2,4,3,3,2,3,4,3], dit 5 -> (5, 3, carte `journee_type`).
        self.assertEqual(rythme.palier_initial([3, 3, 2, 4, 3, 3, 2, 3, 4, 3], 5),
                         (5, 3, 'journee_type'))

    def test_plancher_un(self):
        self.assertEqual(rythme.palier_initial([0] * 10, None)[1], 1)

    def test_dit_egal_au_type_sans_carte(self):
        self.assertEqual(rythme.palier_initial([3] * 10, 3), (3, 3, None))


def etat_bloc(comptes, **champs):
    base = dict(palier=5, palier_source=SourceObjectif.CALCULE, comptes_bloc=tuple(comptes))
    base.update(champs)
    return EtatRythme(**base)


class EvaluerBlocTests(unittest.TestCase):
    """Verdict d'un bloc (§6.5 points 3-5, 7)."""

    def test_ex13_sept_sur_dix_monter(self):
        # Ex. 13 : N 5, (5,6,5,4,7,5,3,6,5,4) : 7/10 -> monter.
        etat = etat_bloc([5, 6, 5, 4, 7, 5, 3, 6, 5, 4])
        self.assertEqual(rythme.evaluer_bloc(etat, jour_n(0)), 'monter')

    def test_ex14_deux_sur_dix_baisser(self):
        # Ex. 14 : N 6, (5,4,6,5,3,5,6,4,5,4) : 2/10 -> baisser.
        etat = etat_bloc([5, 4, 6, 5, 3, 5, 6, 4, 5, 4], palier=6)
        self.assertEqual(rythme.evaluer_bloc(etat, jour_n(0)), 'baisser')

    def test_ex15_v1_taille_ignoree(self):
        # Ex. 15 / variante v1 n° 67 : 7/10, médiane 20 vs référence 40 -> monter (garde éteinte).
        etat = etat_bloc([5, 6, 5, 4, 7, 5, 3, 6, 5, 4], taille_mediane_bloc=20, ref_taille_min=40)
        self.assertEqual(rythme.evaluer_bloc(etat, jour_n(0)), 'monter')

    def test_ex15_garde_de_taille_allumee(self):
        # Ex. 15 (règle complète, éteinte en v1) -> `taille`.
        etat = etat_bloc([5, 6, 5, 4, 7, 5, 3, 6, 5, 4], taille_mediane_bloc=20, ref_taille_min=40)
        with mock.patch.object(rythme, 'GARDE_TAILLE_ACTIVE', True):
            self.assertEqual(rythme.evaluer_bloc(etat, jour_n(0)), 'taille')

    def _etat_echec(self):
        return etat_bloc([7, 7, 7, 7, 7, 1, 1, 1, 1, 1], palier=6, echec_niveau=7, echec_le=jour_n(60),
                         echec_n=1, meilleur_tenu=6)

    def test_ex18_v1_echec_non_lu(self):
        # Ex. 18 / variante v1 n° 69 : N 6, 7/10, échec (7, 60, 1), j90 -> monter (mémoire éteinte).
        self.assertEqual(rythme.evaluer_bloc(self._etat_echec(), jour_n(90)), 'monter')

    def test_ex18_memoire_echec_allumee(self):
        # Ex. 18 (règle complète) : rien.
        with mock.patch.object(rythme, 'MEMOIRE_ECHEC_ACTIVE', True):
            self.assertIsNone(rythme.evaluer_bloc(self._etat_echec(), jour_n(90)))

    def test_ex19_et_ex20_bornes_des_42_jours(self):
        # Ex. 19 : j101 -> rien (v1 n° 70 : monter) ; Ex. 20 : j102 -> monter.
        etat = self._etat_echec()
        self.assertEqual(rythme.evaluer_bloc(etat, jour_n(101)), 'monter')  # v1
        with mock.patch.object(rythme, 'MEMOIRE_ECHEC_ACTIVE', True):
            self.assertIsNone(rythme.evaluer_bloc(etat, jour_n(101)))
            self.assertEqual(rythme.evaluer_bloc(etat, jour_n(102)), 'monter')

    def test_ex50_cinq_sur_dix_monter(self):
        # Ex. 50 : N 5, (5,5,5,5,5,4,4,4,4,4) : 5/10 -> monter (seuil A2).
        self.assertEqual(rythme.evaluer_bloc(etat_bloc([5] * 5 + [4] * 5), jour_n(0)), 'monter')

    def test_ex51_quatre_sur_dix_rien(self):
        # Ex. 51 : N 5, 4/10 -> rien.
        self.assertIsNone(rythme.evaluer_bloc(etat_bloc([5] * 4 + [4] * 6), jour_n(0)))

    def test_ex52_trois_sur_dix_baisser(self):
        # Ex. 52 : N 5, 3/10 -> baisser.
        self.assertEqual(rythme.evaluer_bloc(etat_bloc([5] * 3 + [4] * 7), jour_n(0)), 'baisser')

    def test_ex53_bloc_essai_deux_jours_rien(self):
        # Ex. 53 : bloc d'essai, 2 jours tenus -> rien.
        etat = etat_bloc([5] * 2 + [4] * 8, essai_restant=True)
        self.assertIsNone(rythme.evaluer_bloc(etat, jour_n(0)))

    def test_ex54_bloc_essai_un_jour_baisser(self):
        # Ex. 54 : bloc d'essai, 1 jour tenu -> baisser.
        etat = etat_bloc([5] * 1 + [4] * 9, essai_restant=True)
        self.assertEqual(rythme.evaluer_bloc(etat, jour_n(0)), 'baisser')

    def test_garde_fous(self):
        # Plafond 12, plancher 1, bloc incomplet, baisse refusée, blocs à sauter.
        self.assertIsNone(rythme.evaluer_bloc(etat_bloc([12] * 10, palier=12), jour_n(0)))
        self.assertIsNone(rythme.evaluer_bloc(etat_bloc([0] * 10, palier=1), jour_n(0)))
        self.assertIsNone(rythme.evaluer_bloc(etat_bloc([5] * 9), jour_n(0)))
        self.assertIsNone(rythme.evaluer_bloc(etat_bloc([1] * 10, baisse_refusee=True), jour_n(0)))
        self.assertIsNone(rythme.evaluer_bloc(etat_bloc([5] * 10, blocs_a_sauter=1), jour_n(0)))


class CloreBlocTests(unittest.TestCase):
    """Clôture d'un bloc et réponses (§6.5 points 3, 6)."""

    def test_ex16_montee_refusee_premier_refus(self):
        # Ex. 16 : montée refusée (1er refus) -> 1 bloc sauté.
        neuf = rythme.clore_bloc(etat_bloc([5] * 7 + [4] * 3), jour_n(10), 'monter', 'pas_maintenant')
        self.assertEqual((neuf.blocs_a_sauter, neuf.refus_montee, neuf.palier), (1, 1, 5))

    def test_refus_suivants_sautent_deux_puis_quatre(self):
        etat = etat_bloc([5] * 7 + [4] * 3, refus_montee=1)
        etat = rythme.clore_bloc(etat, jour_n(10), 'monter', 'pas_maintenant')
        self.assertEqual(etat.blocs_a_sauter, 2)
        etat = rythme.clore_bloc(replace_bloc(etat), jour_n(20), 'monter', 'pas_maintenant')
        self.assertEqual(etat.blocs_a_sauter, 4)
        etat = rythme.clore_bloc(replace_bloc(etat), jour_n(30), 'monter', 'pas_maintenant')
        self.assertEqual(etat.blocs_a_sauter, 4)

    def test_montee_acceptee_ouvre_un_essai(self):
        neuf = rythme.clore_bloc(etat_bloc([5] * 7 + [4] * 3), jour_n(10), 'monter', 'oui')
        self.assertEqual((neuf.palier, neuf.palier_source, neuf.essai_restant, neuf.objectif),
                         (6, SourceObjectif.ACCEPTE, True, 6))
        self.assertEqual((neuf.comptes_bloc, neuf.bloc_debut), ((), jour_n(11)))

    def test_ex17_baisse_acceptee_memorise_l_echec(self):
        # Ex. 17 : baisse 7 -> 6 acceptée au j60 -> palier 6, échec (7, j60, 1).
        etat = etat_bloc([7, 1, 1, 1, 1, 1, 1, 1, 1, 1], palier=7, meilleur_tenu=6)
        neuf = rythme.clore_bloc(etat, jour_n(60), 'baisser', 'oui')
        self.assertEqual(neuf.palier, 6)
        self.assertEqual((neuf.echec_niveau, neuf.echec_le, neuf.echec_n), (7, jour_n(60), 1))

    def test_ex17_v1_palier_six_seulement(self):
        # Variante v1 n° 68 : l'échec n'est pas lu -> seul le palier 6 compte (évaluer_bloc l'ignore).
        etat = etat_bloc([7, 1, 1, 1, 1, 1, 1, 1, 1, 1], palier=7, meilleur_tenu=6)
        neuf = rythme.clore_bloc(etat, jour_n(60), 'baisser', 'oui')
        self.assertEqual(neuf.palier, 6)

    def test_baisse_sous_le_meilleur_tenu_sans_echec(self):
        etat = etat_bloc([5] + [1] * 9, palier=5, meilleur_tenu=6)
        neuf = rythme.clore_bloc(etat, jour_n(5), 'baisser', 'oui')
        self.assertEqual((neuf.palier, neuf.echec_niveau), (4, None))

    def test_baisse_gardee_pas_de_baisse_au_bloc_suivant(self):
        neuf = rythme.clore_bloc(etat_bloc([1] * 10), jour_n(5), 'baisser', 'garder')
        self.assertEqual((neuf.palier, neuf.baisse_refusee), (5, True))

    def test_ex55_meilleur_tenu(self):
        # Ex. 55 : N 6, 5/10, aucune décision -> meilleur_tenu 6.
        etat = etat_bloc([6] * 5 + [4] * 5, palier=6)
        self.assertEqual(rythme.clore_bloc(etat, jour_n(5), None, None).meilleur_tenu, 6)

    def test_bloc_saute_decremente(self):
        etat = etat_bloc([5] * 10, blocs_a_sauter=2)
        self.assertEqual(rythme.clore_bloc(etat, jour_n(5), None, None).blocs_a_sauter, 1)


def replace_bloc(etat):
    """Un bloc plein de plus (le précédent a été remis à zéro)."""
    return etat_bloc([5] * 7 + [4] * 3, palier=etat.palier, refus_montee=etat.refus_montee,
                     blocs_a_sauter=0)


class ObjectifTests(unittest.TestCase):
    """Objectif dit et objectif affiché (§6.5 point 1)."""

    def test_ex30_froid(self):
        # Ex. 30 : démarrage à froid -> (5, `defaut`).
        self.assertEqual(rythme.objectif_affiche(EtatRythme()), (5, SourceObjectif.DEFAUT, None))

    def test_ex31_dit(self):
        # Ex. 31 : dit 4 -> (4, `dit`).
        etat = EtatRythme(palier=4, palier_source=SourceObjectif.DIT)
        self.assertEqual(rythme.objectif_affiche(etat), (4, SourceObjectif.DIT, None))

    def test_ex32_libre(self):
        # Ex. 32 : LIBRE -> (None, `libre`).
        etat = EtatRythme(mode=ModeRythme.LIBRE)
        self.assertEqual(rythme.objectif_affiche(etat), (None, SourceObjectif.LIBRE, None))

    def test_zone_en_tenir(self):
        # §6.6 : « environ arrondir(R) », zone arrondir(R - b) à arrondir(R + b).
        etat = EtatRythme(mode=ModeRythme.TENIR, tenir_reference=8)
        self.assertEqual(rythme.objectif_affiche(etat), (8, SourceObjectif.CALCULE, (6, 10)))

    def test_tenir_reference_provisoire_palier(self):
        etat = EtatRythme(mode=ModeRythme.TENIR, palier=4)
        self.assertEqual(rythme.objectif_affiche(etat)[0], 4)

    def test_ex59_dit_sept(self):
        # Ex. 59 : palier 5, dit 7 -> palier 7, source `dit`, objectif en vigueur aujourd'hui.
        neuf = rythme.objectif_dit(EtatRythme(palier=5), 7)
        self.assertEqual((neuf.palier, neuf.palier_source, neuf.objectif, neuf.mode),
                         (7, SourceObjectif.DIT, 7, ModeRythme.POUSSER))

    def test_ex60_plus_et_moins(self):
        # Ex. 60 : « plus » sur 5 -> 6 ; « moins » sur 1 -> 1 (plancher).
        self.assertEqual(rythme.objectif_dit(EtatRythme(palier=5), sens='plus').palier, 6)
        self.assertEqual(rythme.objectif_dit(EtatRythme(palier=1), sens='moins').palier, 1)

    def test_plus_sur_froid_part_de_cinq_et_plafond(self):
        self.assertEqual(rythme.objectif_dit(EtatRythme(), sens='plus').palier, 6)
        self.assertEqual(rythme.objectif_dit(EtatRythme(palier=12), sens='plus').palier, 12)

    def test_ex61_quinze_refuse(self):
        # Ex. 61 : dit 15 -> 400 {"objectif": ["Entre 1 et 12."]}.
        with self.assertRaises(rythme.ObjectifInvalide) as ctx:
            rythme.objectif_dit(EtatRythme(palier=5), 15)
        self.assertEqual(ctx.exception.erreurs, {'objectif': ['Entre 1 et 12.']})
        with self.assertRaises(rythme.ObjectifInvalide):
            rythme.objectif_dit(EtatRythme(palier=5), 0)

    def test_objectif_dit_remet_les_refus_a_zero(self):
        etat = EtatRythme(palier=5, refus_montee=2, blocs_a_sauter=2, baisse_refusee=True,
                          essai_restant=True, bloc_debut=jour_n(3), comptes_bloc=(5, 5))
        neuf = rythme.objectif_dit(etat, 8, jour=jour_n(10))
        self.assertEqual((neuf.refus_montee, neuf.blocs_a_sauter, neuf.baisse_refusee, neuf.essai_restant),
                         (0, 0, False, False))
        self.assertEqual((neuf.bloc_debut, neuf.comptes_bloc), (jour_n(11), ()))

    def test_objectif_dit_a_froid_garde_bloc_debut_nul(self):
        self.assertIsNone(rythme.objectif_dit(EtatRythme(), 8, jour=jour_n(10)).bloc_debut)

    def test_ex62_premier_oui(self):
        # Ex. 62 : type 3, [Oui, 3] -> palier 3, `accepte`.
        neuf = rythme.repondre_premier(EtatRythme(), 3, 'oui')
        self.assertEqual((neuf.palier, neuf.palier_source), (3, SourceObjectif.ACCEPTE))

    def test_ex63_premier_garder_cinq(self):
        # Ex. 63 : type 3, [Garder 5] -> palier 5, `accepte`.
        neuf = rythme.repondre_premier(EtatRythme(), 3, 'garder')
        self.assertEqual((neuf.palier, neuf.palier_source), (5, SourceObjectif.ACCEPTE))


if __name__ == '__main__':
    unittest.main()
