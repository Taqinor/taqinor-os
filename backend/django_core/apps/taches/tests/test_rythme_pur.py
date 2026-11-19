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

    def test_une_seule_definition_de_arrondir(self):
        from apps.taches.moteur import classement, gabarits, nombres
        self.assertIs(rythme.arrondir, nombres.arrondir)
        self.assertIs(gabarits.arrondir, nombres.arrondir)
        self.assertIs(classement.arrondir, nombres.arrondir)

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

    def test_oui_repart_le_bloc_au_nouveau_palier(self):
        # Revue F2 tour 2 #8 : « Oui » six jours après la carte — les jours faits à 5 ne comptent pas contre 6
        # (§6.5 « 10 jours évalués au même palier ») ; le bloc repart le lendemain, comme un objectif dit.
        for decision, palier, attendu in (('monter', 5, 6), ('baisser', 6, 5)):
            with self.subTest(decision=decision):
                etat = EtatRythme(mode=ModeRythme.POUSSER, palier=palier, palier_source=SourceObjectif.ACCEPTE,
                                  bloc_debut=jour_n(0), comptes_bloc=(5,) * 6)
                neuf = rythme.mettre_a_jour(etat, **rythme.apres_decision(etat, jour_n(6), decision, 'oui'))
                self.assertEqual((neuf.palier, neuf.comptes_bloc, neuf.bloc_debut), (attendu, (), jour_n(7)))
        refus = EtatRythme(palier=5, bloc_debut=jour_n(0), comptes_bloc=(5,) * 6)
        neuf = rythme.mettre_a_jour(refus, **rythme.apres_decision(refus, jour_n(6), 'monter', 'pas_maintenant'))
        self.assertEqual((neuf.comptes_bloc, neuf.bloc_debut), ((5,) * 6, jour_n(0)))  # un refus ne repart pas
        # Jumeau : la carte `premier` acceptée (5 par défaut -> 3) repart aussi le bloc ; « Garder 5 » non.
        froid = EtatRythme(bloc_debut=jour_n(0), comptes_bloc=(5,) * 4)
        oui = rythme.repondre_premier(froid, 3, 'oui', jour_n(4))
        self.assertEqual((oui.palier, oui.comptes_bloc, oui.bloc_debut), (3, (), jour_n(5)))
        garder = rythme.repondre_premier(froid, 3, 'garder', jour_n(4))
        self.assertEqual((garder.palier, garder.comptes_bloc, garder.bloc_debut), (5, (5,) * 4, jour_n(0)))

    def test_carte_a_jour_seulement_depuis_le_palier_courant(self):
        # Revue F2 tour 2 #5 : une carte calculée d'un autre palier est périmée (jamais deux crans).
        a_jour = rythme.carte_a_jour
        self.assertTrue(a_jour(EtatRythme(palier=5), 'monter', {'N': 5, 'N1': 6}))
        self.assertTrue(a_jour(EtatRythme(), 'monter', {'N': 5, 'N1': 6}))  # froid : palier 5 par défaut
        self.assertFalse(a_jour(EtatRythme(palier=8), 'monter', {'N': 5, 'N1': 6}))
        self.assertFalse(a_jour(EtatRythme(palier=5), 'monter', {'N': 5, 'N1': 7}))
        self.assertTrue(a_jour(EtatRythme(palier=6), 'baisser', {'N': 6, 'N_1': 5}))
        self.assertFalse(a_jour(EtatRythme(palier=5), 'baisser', {'N': 6, 'N_1': 5}))
        self.assertTrue(a_jour(EtatRythme(), 'premier', {'type': 3}))
        self.assertFalse(a_jour(EtatRythme(palier=4), 'premier', {'type': 3}))
        self.assertTrue(a_jour(EtatRythme(palier=5), 'journee_type', {'type': 3, 'dit': 5}))
        self.assertFalse(a_jour(EtatRythme(palier=6), 'journee_type', {'type': 3, 'dit': 5}))


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

    def test_tenir_sous_un_par_jour_plancher(self):
        # Revue F2 tour 2 #9 : R 0,29 -> objectif 1 (jamais 0), zone 0 à 1 (jamais une borne négative).
        for reference in (0.29, 0.5, 0):
            with self.subTest(reference=reference):
                etat = EtatRythme(mode=ModeRythme.TENIR, tenir_reference=reference)
                self.assertEqual(rythme.objectif_affiche(etat), (1, SourceObjectif.CALCULE, (0, 1)))
        recents = (0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1)  # 4 tâches en 14 jours évalués
        tenir = rythme.basculer(EtatRythme(comptes_recents=recents), ModeRythme.TENIR, jour_n(0))
        self.assertEqual((tenir.objectif, rythme.objectif_affiche(tenir)[2]), (1, (0, 1)))
        self.assertEqual(rythme.objectif_tenir(0.14), 1)  # le `m` d'une dérive : plancher 1

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


class ReferenceTenirTests(unittest.TestCase):
    """R, bande et dérive (§6.6)."""

    def test_ex21_quatorze_jours_somme_70(self):
        # Ex. 21 : 14 jours de somme 70 -> 5,0.
        self.assertAlmostEqual(rythme.reference_tenir([5] * 7 + [5] * 7), 5.0, places=2)
        self.assertAlmostEqual(rythme.reference_tenir([4, 6] * 7), 5.0, places=2)

    def test_ex22_treize_jours(self):
        # Ex. 22 : 13 jours -> None.
        self.assertIsNone(rythme.reference_tenir([5] * 13))

    def test_ex23_quatorze_fois_sept(self):
        # Ex. 23 : 14 × 7 -> 7,0.
        self.assertAlmostEqual(rythme.reference_tenir([7] * 14), 7.0, places=2)

    def test_garde_les_quatorze_derniers(self):
        self.assertAlmostEqual(rythme.reference_tenir([100] * 5 + [6] * 14), 6.0, places=2)

    def test_ex57_plafond_dans_la_reference(self):
        # Ex. 57 : 13 × 5 + 30 -> 5,43 (sans plafond : 6,79).
        self.assertAlmostEqual(rythme.reference_tenir([5] * 13 + [30]), 5.43, places=2)

    def test_ex24_bande_cinq(self):
        # Ex. 24 : 5 -> (4 ; 6).
        self.assertEqual(rythme.bande_tenir(5), (4, 6))

    def test_ex25_bande_huit(self):
        # Ex. 25 : 8 -> (6,4 ; 9,6).
        bas, haut = rythme.bande_tenir(8)
        self.assertAlmostEqual(bas, 6.4, places=2)
        self.assertAlmostEqual(haut, 9.6, places=2)

    def test_ex26_bande_deux(self):
        # Ex. 26 : 2 -> (1 ; 3).
        self.assertEqual(rythme.bande_tenir(2), (1, 3))

    def test_ex27_derive_sous(self):
        # Ex. 27 : R 5, 11 × 3 + 3 × 4 (moyenne 3,21) -> `sous`.
        self.assertEqual(rythme.derive_tenir(5, [3] * 11 + [4] * 3, jour_n(100), None), 'sous')

    def test_ex28_derive_au_dessus(self):
        # Ex. 28 : R 5, 13 × 7 + 6 (moyenne 6,93) -> `au_dessus`.
        self.assertEqual(rythme.derive_tenir(5, [7] * 13 + [6], jour_n(100), None), 'au_dessus')

    def test_ex29_silence(self):
        # Ex. 29 : silence jusqu'au j70, jour 50 -> None (même hors zone).
        self.assertIsNone(rythme.derive_tenir(5, [3] * 14, jour_n(50), jour_n(70)))
        self.assertEqual(rythme.derive_tenir(5, [3] * 14, jour_n(71), jour_n(70)), 'sous')

    def test_ex58_un_jour_a_trente_reste_dans_la_zone(self):
        # Ex. 58 : R 5, 13 × 5 + 30 -> None (dans la zone grâce au plafond).
        self.assertIsNone(rythme.derive_tenir(5, [5] * 13 + [30], jour_n(100), None))

    def test_pas_assez_de_jours_ou_pas_de_reference(self):
        self.assertIsNone(rythme.derive_tenir(5, [3] * 13, jour_n(100), None))
        self.assertIsNone(rythme.derive_tenir(None, [3] * 14, jour_n(100), None))

    def test_borne_stricte_de_la_zone(self):
        # Moyenne exactement sur la borne basse (4) : strictement hors zone seulement.
        self.assertIsNone(rythme.derive_tenir(5, [4] * 14, jour_n(100), None))


class BasculerTests(unittest.TestCase):
    """Bascules entre les trois modes (§6.7)."""

    def _tenir(self, reference):
        return EtatRythme(mode=ModeRythme.TENIR, tenir_reference=reference, meilleur_tenu=6,
                          echec_niveau=7, echec_n=2, refus_montee=2, blocs_a_sauter=2, essai_restant=True)

    def test_ex33_tenir_cinq_six(self):
        # Ex. 33 : TENIR R 5,6 -> POUSSER : palier 6.
        self.assertEqual(rythme.basculer(self._tenir(5.6), ModeRythme.POUSSER, jour_n(0)).palier, 6)

    def test_ex34_tenir_cinq_cinq(self):
        # Ex. 34 : TENIR R 5,5 -> POUSSER : palier 5.
        self.assertEqual(rythme.basculer(self._tenir(5.5), ModeRythme.POUSSER, jour_n(0)).palier, 5)

    def test_ex35_tenir_quatre_cinq(self):
        # Ex. 35 : TENIR R 4,5 -> POUSSER : palier 4.
        self.assertEqual(rythme.basculer(self._tenir(4.5), ModeRythme.POUSSER, jour_n(0)).palier, 4)

    def test_ex36_tenir_cinq_cinquante_et_un(self):
        # Ex. 36 : TENIR R 5,51 -> POUSSER : palier 6.
        self.assertEqual(rythme.basculer(self._tenir(5.51), ModeRythme.POUSSER, jour_n(0)).palier, 6)

    def test_tenir_vers_pousser_plancher_un(self):
        self.assertEqual(rythme.basculer(self._tenir(0.4), ModeRythme.POUSSER, jour_n(0)).palier, 1)

    def test_ex37_pousser_vers_tenir(self):
        # Ex. 37 : POUSSER -> TENIR, 14 derniers = 13 × 5 + 8 (73) -> R 5,21.
        etat = EtatRythme(palier=5, comptes_recents=tuple([5] * 13 + [8]))
        neuf = rythme.basculer(etat, ModeRythme.TENIR, jour_n(0))
        self.assertAlmostEqual(float(neuf.tenir_reference), 5.21, places=2)
        self.assertEqual((neuf.mode, neuf.tenir_fixee_le), (ModeRythme.TENIR, jour_n(0)))

    def test_pousser_vers_tenir_provisoire(self):
        # Moins de 14 jours : R provisoire = palier courant (ou 5), non fixée.
        neuf = rythme.basculer(EtatRythme(palier=4, comptes_recents=(4,) * 5), ModeRythme.TENIR, jour_n(0))
        self.assertEqual((neuf.tenir_reference, neuf.tenir_fixee_le), (4, None))
        froid = rythme.basculer(EtatRythme(), ModeRythme.TENIR, jour_n(0))
        self.assertEqual(froid.tenir_reference, 5)

    def test_vers_libre_objectif_nul(self):
        neuf = rythme.basculer(EtatRythme(palier=6), ModeRythme.LIBRE, jour_n(0))
        self.assertEqual((neuf.mode, neuf.objectif), (ModeRythme.LIBRE, None))

    def test_libre_vers_pousser_journee_type(self):
        # LIBRE -> POUSSER : journée type des 10 derniers jours évalués.
        etat = EtatRythme(mode=ModeRythme.LIBRE, comptes_recents=tuple([2] * 4 + [3] * 10))
        neuf = rythme.basculer(etat, ModeRythme.POUSSER, jour_n(0))
        self.assertEqual((neuf.palier, neuf.bloc_debut), (3, jour_n(1)))

    def test_libre_vers_pousser_sans_historique_demarrage_a_froid(self):
        etat = EtatRythme(mode=ModeRythme.LIBRE, comptes_recents=(3,) * 4)
        neuf = rythme.basculer(etat, ModeRythme.POUSSER, jour_n(0))
        self.assertEqual((neuf.palier, neuf.bloc_debut, neuf.objectif), (None, None, 5))

    def test_r2_122_libre_vers_pousser_rend_le_dernier_palier(self):
        # C-7 : « Sans objectif » ne perd pas l'objectif d'avant ; revenir à « En faire plus » le rend, même
        # avec moins de 10 jours évalués (aucun démarrage à froid) et même avec 10 jours d'une autre allure.
        for comptes in ((3,) * 4, (2,) * 10):
            with self.subTest(jours=len(comptes)):
                etat = EtatRythme(mode=ModeRythme.LIBRE, comptes_recents=comptes, palier=6,
                                  palier_source=SourceObjectif.DIT)
                neuf = rythme.basculer(etat, ModeRythme.POUSSER, jour_n(0))
                self.assertEqual((neuf.palier, neuf.palier_source, neuf.objectif), (6, SourceObjectif.DIT, 6))
                self.assertEqual(neuf.bloc_debut, jour_n(1))

    def test_r2_122_aller_retour_des_modes_garde_l_objectif(self):
        # F2 n°5 : Plus (6) -> Garder ce rythme -> Sans objectif -> En faire plus : « 6 », pas la valeur par défaut.
        etat = EtatRythme(palier=6, palier_source=SourceObjectif.DIT, comptes_recents=(5,) * 6)
        for mode in (ModeRythme.TENIR, ModeRythme.LIBRE, ModeRythme.POUSSER):
            etat = rythme.basculer(etat, mode, jour_n(0))
        self.assertEqual((etat.mode, etat.objectif, etat.palier_source), (ModeRythme.POUSSER, 6, SourceObjectif.DIT))

    def test_remet_a_zero_et_garde_les_echecs(self):
        neuf = rythme.basculer(self._tenir(5), ModeRythme.POUSSER, jour_n(0))
        self.assertEqual((neuf.refus_montee, neuf.blocs_a_sauter, neuf.essai_restant, neuf.baisse_refusee),
                         (0, 0, False, False))
        self.assertEqual((neuf.meilleur_tenu, neuf.echec_niveau, neuf.echec_n), (6, 7, 2))

    def test_meme_mode_ne_change_rien(self):
        etat = EtatRythme(palier=6)
        self.assertIs(rythme.basculer(etat, ModeRythme.POUSSER, jour_n(0)), etat)


class SemaineCourteTests(unittest.TestCase):
    """Semaine courte (§6.9, A16-N9)."""

    def test_ex64_deux_evalues_trois_sans_donnees(self):
        # Ex. 64 : 2 `evalue` + 3 `sans_donnees` -> vrai (revue sans chiffres).
        statuts = [StatutJour.EVALUE] * 2 + [StatutJour.SANS_DONNEES] * 3
        self.assertTrue(rythme.semaine_courte(statuts))

    def test_ex65_trois_evalues_deux_sans_donnees(self):
        # Ex. 65 : 3 `evalue` + 2 `sans_donnees` -> faux.
        statuts = [StatutJour.EVALUE] * 3 + [StatutJour.SANS_DONNEES] * 2
        self.assertFalse(rythme.semaine_courte(statuts))


class ReperePtests(unittest.TestCase):
    """Repère P60 (§6.5 point 8) : 3 exemples d'`integ2/propose.py`."""

    def test_repere_neuf_jours_croissants(self):
        # [3,4,5,5,5,6,6,7,8] -> 5,8.
        self.assertEqual(rythme.repere_p60([3, 4, 5, 5, 5, 6, 6, 7, 8]), 5.8)

    def test_repere_neuf_fois_cinq(self):
        # 9 × 5 -> 5,0.
        self.assertEqual(rythme.repere_p60([5] * 9), 5.0)

    def test_repere_deux_a_dix(self):
        # [2…10] -> 6,8.
        self.assertEqual(rythme.repere_p60(list(range(2, 11))), 6.8)

    def test_repere_moins_de_neuf_jours(self):
        self.assertIsNone(rythme.repere_p60([5] * 8))


J_C = date(2026, 11, 17)


def il_y_a(n):
    return J_C - timedelta(days=n)


def donnees(**champs):
    return rythme.DonneesConstats(jour=J_C, **champs)


def codes(d):
    return [c.code for c in rythme.constats(d)]


class ConstatsTests(unittest.TestCase):
    """Constats C1-C8 (§6.9) : chacun au minimum exact, juste en dessous, et ses nombres."""

    def test_rien_sans_donnees(self):
        self.assertEqual(rythme.constats(donnees()), [])

    def test_c1_creneaux(self):
        # C1 : écart >= 25 points entre créneaux, 30 lignes minimum par créneau.
        lignes = ([rythme.LigneConstat(il_y_a(1), 'matin', i < 24) for i in range(30)]
                  + [rythme.LigneConstat(il_y_a(2), 'apres_midi', i < 12) for i in range(30)])
        self.assertEqual(codes(donnees(lignes=tuple(lignes))), [])  # hors première livraison (#7)
        with mock.patch.object(rythme, 'CONSTAT_C1_ACTIF', True):
            constat = rythme.constats(donnees(lignes=tuple(lignes)))[0]
        self.assertEqual((constat.code, constat.action, constat.donnees['meilleur']),
                         ('C1', 'essentiel_le_matin', 'matin'))

    @mock.patch.object(rythme, 'CONSTAT_C1_ACTIF', True)
    def test_c1_minimum_et_ecart(self):
        court = ([rythme.LigneConstat(il_y_a(1), 'matin', True)] * 29
                 + [rythme.LigneConstat(il_y_a(1), 'apres_midi', False)] * 30)
        self.assertNotIn('C1', codes(donnees(lignes=tuple(court))))
        proche = ([rythme.LigneConstat(il_y_a(1), 'matin', i < 18) for i in range(30)]
                  + [rythme.LigneConstat(il_y_a(1), 'apres_midi', i < 12) for i in range(30)])
        self.assertNotIn('C1', codes(donnees(lignes=tuple(proche))))  # 60 % vs 40 % = 20 points

    @mock.patch.object(rythme, 'CONSTAT_C1_ACTIF', True)
    def test_c1_hors_fenetre(self):
        vieux = ([rythme.LigneConstat(il_y_a(40), 'matin', i < 24) for i in range(30)]
                 + [rythme.LigneConstat(il_y_a(40), 'apres_midi', i < 12) for i in range(30)])
        self.assertNotIn('C1', codes(donnees(lignes=tuple(vieux))))

    def _lignes_c2(self, jours_en_tete, jours_ailleurs):
        """Un essentiel en tête (rang 1, fait 4 jours sur 5) et un ailleurs (rang 2, fait 1 sur 3)."""
        lignes = []
        for i in range(jours_en_tete):
            lignes.append(rythme.LigneConstat(il_y_a(i), '', i % 5 != 0, True, 1))
        for i in range(jours_ailleurs):
            lignes.append(rythme.LigneConstat(il_y_a(i), '', True, False, 1))
            lignes.append(rythme.LigneConstat(il_y_a(i), '', i % 3 == 0, True, 2))
        return tuple(lignes)

    def test_c2_essentiel_en_tete(self):
        # C2 : essentiel fait en tête vs ailleurs, écart >= 30 points, 15 jours chacun.
        self.assertEqual(codes(donnees(lignes=self._lignes_c2(15, 15))), [])  # hors première livraison (#7)
        with mock.patch.object(rythme, 'CONSTAT_C2_ACTIF', True):
            constat = rythme.constats(donnees(lignes=self._lignes_c2(15, 15)))[0]
        self.assertEqual((constat.code, round(constat.donnees['premier']), round(constat.donnees['ailleurs'])),
                         ('C2', 80, 33))

    @mock.patch.object(rythme, 'CONSTAT_C2_ACTIF', True)
    def test_c2_quatorze_jours_ne_suffisent_pas(self):
        self.assertNotIn('C2', codes(donnees(lignes=self._lignes_c2(14, 15))))
        self.assertNotIn('C2', codes(donnees(lignes=self._lignes_c2(15, 14))))

    def _jours_c3(self, lundis):
        jours = []
        for i in range(56):
            jour = il_y_a(i)
            compte = 1 if jour.weekday() == 0 else 6
            jours.append(rythme.JourCompte(jour, compte=compte))
        garde = [j for j in jours if j.jour.weekday() != 0]
        return tuple(garde + [j for j in jours if j.jour.weekday() == 0][:lundis])

    def test_c3_jour_faible(self):
        # C3 : un lundi à 1 pour une moyenne générale ~5,3, 8 lundis -> jours_courts.
        constat = rythme.constats(donnees(jours=self._jours_c3(8)))[0]
        self.assertEqual((constat.code, constat.action, constat.donnees['jour_semaine']),
                         ('C3', 'jours_courts', 0))

    def test_c3_sept_lundis_ne_suffisent_pas(self):
        self.assertNotIn('C3', codes(donnees(jours=self._jours_c3(7))))

    def _jours_c4(self, trop):
        jours = []
        for i in range(10):
            faites = 2 if i < trop else 5
            jours.append(rythme.JourCompte(il_y_a(i + 1), plan_prevues=5, plan_faites=faites))
        return tuple(jours)

    def test_c4_trop_garde(self):
        # C4 : gardées - faites >= 2 sur >= 60 % de 10 plans -> limite médiane faite + 1.
        self.assertNotIn('C4', codes(donnees(jours=self._jours_c4(6))))  # hors première livraison (#7)
        with mock.patch.object(rythme, 'CONSTAT_C4_ACTIF', True):
            constat = rythme.constats(donnees(jours=self._jours_c4(6)))[0]
        self.assertEqual((constat.code, constat.donnees['limite']), ('C4', 3))

    @mock.patch.object(rythme, 'CONSTAT_C4_ACTIF', True)
    def test_c4_cinq_sur_dix_ne_suffit_pas(self):
        self.assertNotIn('C4', codes(donnees(jours=self._jours_c4(5))))

    @mock.patch.object(rythme, 'CONSTAT_C4_ACTIF', True)
    def test_c4_neuf_plans_ne_suffisent_pas(self):
        self.assertNotIn('C4', codes(donnees(jours=self._jours_c4(10)[:9])))

    def test_c5_tranches_de_deux_heures(self):
        # C5 : part des tâches finies par tranche de 2 h, 30 tâches minimum, aucune action.
        heures = tuple((il_y_a(1), 9) for _ in range(20)) + tuple((il_y_a(2), 15) for _ in range(10))
        constat = rythme.constats(donnees(heures_faits=heures))[0]
        self.assertEqual((constat.code, constat.action), ('C5', None))
        self.assertAlmostEqual(constat.donnees['tranches'][8], 66.67, places=1)
        self.assertAlmostEqual(constat.donnees['tranches'][14], 33.33, places=1)
        self.assertNotIn('C5', codes(donnees(heures_faits=heures[:29])))

    def _mesurees(self, reel):
        return tuple((3, 30, reel) for _ in range(5))

    def test_c6_eteint_en_v1(self):
        # C6 hors de la première livraison (critique m6).
        self.assertNotIn('C6', codes(donnees(taches_mesurees=self._mesurees(60))))

    def test_c6_allume(self):
        with mock.patch.object(rythme, 'CONSTAT_C6_ACTIF', True):
            constat = rythme.constats(donnees(taches_mesurees=self._mesurees(60)))[0]
            self.assertEqual((constat.code, constat.donnees['projet_id'], constat.donnees['ratio']),
                             ('C6', 3, 2.0))
            self.assertEqual(rythme.constats(donnees(taches_mesurees=self._mesurees(30))), [])
            self.assertEqual(rythme.constats(donnees(taches_mesurees=self._mesurees(60)[:4])), [])

    def test_c7_reportees(self):
        # C7 : tâches reportées 3 fois ou plus (ouvertes), minimum 1 -> À revoir.
        constat = rythme.constats(donnees(reportees_3=2))[0]
        self.assertEqual((constat.code, constat.donnees['nb'], constat.action), ('C7', 2, 'a_revoir'))
        self.assertNotIn('C7', codes(donnees(reportees_3=0)))

    def test_c8_projet_neglige(self):
        # C8 : `neglige()` non vide -> une de ses tâches dans Proposé de demain.
        self.assertEqual(codes(donnees(projet_neglige_id=5)), [])  # hors première livraison (#7)
        with mock.patch.object(rythme, 'CONSTAT_C8_ACTIF', True):
            constat = rythme.constats(donnees(projet_neglige_id=5))[0]
        self.assertEqual((constat.code, constat.donnees['projet_id']), ('C8', 5))
        self.assertNotIn('C8', codes(donnees()))

    @mock.patch.object(rythme, 'CONSTAT_C8_ACTIF', True)
    def test_refus_se_tait_vingt_huit_jours(self):
        base = dict(reportees_3=1, projet_neglige_id=5)
        self.assertEqual(codes(donnees(refus={'C7': il_y_a(27)}, **base)), ['C8'])
        self.assertEqual(codes(donnees(refus={'C7': il_y_a(28)}, **base)), ['C7', 'C8'])

    def test_comprendre_mon_rythme_coupe_tout(self):
        self.assertEqual(rythme.constats(donnees(reportees_3=3, comprendre_mon_rythme=False)), [])

    @mock.patch.object(rythme, 'CONSTAT_C8_ACTIF', True)
    def test_ordre_par_numero_et_huit_au_plus(self):
        sortie = codes(donnees(reportees_3=1, projet_neglige_id=5))
        self.assertEqual(sortie, ['C7', 'C8'])
        self.assertLessEqual(len(sortie), rythme.CONSTATS_MAX)


class RetourAbsenceTests(unittest.TestCase):
    """Retour d'absence (§4.8)."""

    def _jours(self, *statuts):
        return [rythme.JourCompte(il_y_a(len(statuts) - i), statut_jour=s) for i, s in enumerate(statuts)]

    def test_trois_jours_travailles_apres_la_derniere_ouverture(self):
        jours = self._jours(StatutJour.EVALUE, StatutJour.SANS_DONNEES, StatutJour.SANS_DONNEES,
                            StatutJour.NON_OUVRE, StatutJour.SANS_DONNEES)
        self.assertEqual(rythme.retour_absence(jours, [1, 2]), {'jours': 5, 'taches': [1, 2]})

    def test_deux_jours_ne_suffisent_pas(self):
        jours = self._jours(StatutJour.EVALUE, StatutJour.SANS_DONNEES, StatutJour.NON_OUVRE,
                            StatutJour.SANS_DONNEES)
        self.assertIsNone(rythme.retour_absence(jours, [1]))

    def test_la_derniere_ouverture_ne_compte_pas(self):
        jours = self._jours(StatutJour.EVALUE, StatutJour.EVALUE, StatutJour.EVALUE, StatutJour.NON_OUVRE)
        self.assertIsNone(rythme.retour_absence(jours, []))

    def test_fin_de_conge(self):
        jours = self._jours(StatutJour.EVALUE, StatutJour.CONGE, StatutJour.CONGE)
        self.assertEqual(rythme.retour_absence(jours, [7])['jours'], 3)

    def test_jour_explicite_et_vide(self):
        jours = self._jours(StatutJour.EVALUE, StatutJour.CONGE)
        self.assertEqual(rythme.retour_absence(jours, [], jour=J_C + timedelta(days=2))['jours'], 4)
        self.assertIsNone(rythme.retour_absence([], [1]))


if __name__ == '__main__':
    unittest.main()
