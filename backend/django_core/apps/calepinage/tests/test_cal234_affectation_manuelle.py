"""CAL234 (moitié backend) — l'affectation IMPOSÉE et son verdict serveur.

Ce que cette moitié doit garantir, et que l'atelier (moitié client) consomme :

* une affectation manuelle ÉCRASE l'automatique et chaque ligne touchée est
  MARQUÉE « affectation manuelle » dans la table CAL125 ;
* une proposition invalide est REFUSÉE avec le MOTIF SERVEUR, qui NOMME la
  contrainte, le pan et la chaîne (jamais un « non enregistré » générique) ;
* le verdict se rend SANS RIEN PERSISTER.

Tests PURS : la conception est une doublure portant exactement ce que le
noyau expose (``pans``, ``chaines``), donc ni base ni fiche produit.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.chaines import (
    SOURCE_AUTO,
    SOURCE_MANUELLE,
    AffectationInvalide,
    PanPose,
    affectation,
    normaliser_affectation_imposee,
    verdict_affectation,
)


class _Chaine:
    def __init__(self, pan, nb_modules, mppt, repere):
        self.pan = pan
        self.nb_modules = nb_modules
        self.mppt = mppt
        self.repere = repere


class _Resultat:
    def __init__(self, chaines):
        self.chaines = chaines
        self.repartitions = ()


class _Evaluation:
    nombre = 1
    bloquants = ()


class _Conception:
    """Une conception NUE : deux pans, deux chaînes de 2 modules."""

    def __init__(self):
        self.pans = (PanPose(label='PAN-A', modules=3),
                     PanPose(label='PAN-B', modules=2))
        self.resultat = _Resultat((
            _Chaine('PAN-A', 2, 1, 'CH1'),
            _Chaine('PAN-B', 2, 2, 'CH2'),
        ))
        self.entree = None

    @property
    def chaines(self):
        return self.resultat.chaines


def _conception(monkeypatch=None):
    return _Conception()


class TableAffectationTest(unittest.TestCase):

    def setUp(self):
        # ``affectation`` interroge le noyau pour compter les onduleurs ; on
        # neutralise cet appel, qui n'est pas le sujet de cette tâche.
        from apps.calepinage.services import chaines

        self._vrai = chaines.evaluer_onduleurs
        chaines.evaluer_onduleurs = lambda conception: _Evaluation()
        self.addCleanup(setattr, chaines, 'evaluer_onduleurs', self._vrai)

    def test_toutes_les_lignes_sont_automatiques_par_defaut(self):
        lignes = affectation(_conception())
        self.assertEqual(len(lignes), 5)
        for ligne in lignes:
            self.assertEqual(ligne['source'], SOURCE_AUTO, ligne['module'])
        self.assertEqual(lignes[0]['chaine'], 1)

    def test_l_affectation_manuelle_ecrase_l_automatique_et_se_voit(self):
        imposee = normaliser_affectation_imposee([
            {'module': 'PAN-A#1', 'chaine': 2, 'mppt': 2, 'onduleur': 1},
        ])
        lignes = {ligne['module']: ligne
                  for ligne in affectation(_conception(), imposee=imposee)}
        touchee = lignes['PAN-A#1']
        self.assertEqual(touchee['chaine'], 2)
        self.assertEqual(touchee['mppt'], 2)
        self.assertEqual(touchee['source'], SOURCE_MANUELLE)
        # Les autres lignes ne bougent pas et restent automatiques.
        self.assertEqual(lignes['PAN-A#2']['source'], SOURCE_AUTO)
        self.assertEqual(lignes['PAN-A#2']['chaine'], 1)

    def test_un_module_peut_etre_decable_a_la_main(self):
        imposee = normaliser_affectation_imposee([{'module': 'PAN-A#1'}])
        lignes = {ligne['module']: ligne
                  for ligne in affectation(_conception(), imposee=imposee)}
        self.assertIsNone(lignes['PAN-A#1']['chaine'])
        self.assertEqual(lignes['PAN-A#1']['source'], SOURCE_MANUELLE)


class NormalisationTest(unittest.TestCase):

    def test_liste_attendue(self):
        with self.assertRaises(AffectationInvalide):
            normaliser_affectation_imposee({'module': 'PAN-A#1'})

    def test_module_obligatoire(self):
        with self.assertRaises(AffectationInvalide) as capture:
            normaliser_affectation_imposee([{'chaine': 1}])
        self.assertIn('ne nomme aucun module', str(capture.exception))

    def test_module_affecte_deux_fois_refuse(self):
        with self.assertRaises(AffectationInvalide) as capture:
            normaliser_affectation_imposee([
                {'module': 'PAN-A#1', 'chaine': 1},
                {'module': 'PAN-A#1', 'chaine': 2}])
        self.assertIn("une seule chaîne", str(capture.exception))

    def test_cle_inconnue_refusee(self):
        with self.assertRaises(AffectationInvalide) as capture:
            normaliser_affectation_imposee([
                {'module': 'PAN-A#1', 'couleur': 'rouge'}])
        self.assertIn('couleur', str(capture.exception))

    def test_numero_non_entier_refuse(self):
        for mauvais in (0, -1, 1.5, 'deux'):
            with self.assertRaises(AffectationInvalide):
                normaliser_affectation_imposee([
                    {'module': 'PAN-A#1', 'chaine': mauvais}])

    def test_rien_a_imposer(self):
        self.assertEqual(normaliser_affectation_imposee(None), ())
        self.assertEqual(normaliser_affectation_imposee([]), ())


class VerdictTest(unittest.TestCase):

    def setUp(self):
        from apps.calepinage.services import chaines

        self._vrai = chaines.evaluer_onduleurs
        chaines.evaluer_onduleurs = lambda conception: _Evaluation()
        self.addCleanup(setattr, chaines, 'evaluer_onduleurs', self._vrai)

    def _verdict(self, lignes, specs=None):
        return verdict_affectation(
            _conception(), normaliser_affectation_imposee(lignes),
            specs_onduleur=specs)

    def test_proposition_valide_ne_produit_aucun_refus(self):
        self.assertEqual(self._verdict([
            {'module': 'PAN-A#1', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-A#2', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
        ]), ())

    def test_module_inconnu_du_document_refuse_en_le_nommant(self):
        refus = self._verdict([{'module': 'PAN-Z#9', 'chaine': 1}])
        self.assertEqual(len(refus), 1)
        self.assertIn('PAN-Z#9', refus[0])
        self.assertIn('inconnu', refus[0])

    def test_chaine_qui_traverse_deux_pans_refusee_en_les_nommant(self):
        refus = self._verdict([
            {'module': 'PAN-A#1', 'chaine': 5},
            {'module': 'PAN-B#1', 'chaine': 5},
        ])
        self.assertTrue(any('traverse' in message for message in refus))
        self.assertTrue(any('PAN-A' in message and 'PAN-B' in message
                            for message in refus))

    def test_chaine_trop_longue_refusee_en_nommant_la_contrainte(self):
        refus = self._verdict([
            {'module': 'PAN-A#1', 'chaine': 7},
            {'module': 'PAN-A#2', 'chaine': 7},
            {'module': 'PAN-A#3', 'chaine': 7},
        ])
        self.assertEqual(len(refus), 1)
        self.assertIn('Chaîne 7', refus[0])
        self.assertIn('PAN-A', refus[0])
        self.assertIn('tension à froid', refus[0])

    def test_trop_de_chaines_sur_une_entree_mppt(self):
        refus = self._verdict([
            {'module': 'PAN-A#1', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-A#2', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-B#1', 'chaine': 3, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-B#2', 'chaine': 3, 'mppt': 1, 'onduleur': 1},
        ], specs={'chaines_max_par_mppt': 1})
        self.assertTrue(any('Entrée MPPT' in message for message in refus))
        self.assertTrue(any('maximum 1' in message for message in refus))

    def test_fiche_muette_ne_produit_aucun_faux_rouge(self):
        # Sans ``chaines_max_par_mppt`` publié, on ne SUPPOSE pas une limite.
        refus = self._verdict([
            {'module': 'PAN-A#1', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-A#2', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-B#1', 'chaine': 3, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-B#2', 'chaine': 3, 'mppt': 1, 'onduleur': 1},
        ])
        self.assertEqual([m for m in refus if 'Entrée MPPT' in m], [])

    def test_aucune_proposition_aucun_verdict(self):
        self.assertEqual(verdict_affectation(_conception(), ()), ())
