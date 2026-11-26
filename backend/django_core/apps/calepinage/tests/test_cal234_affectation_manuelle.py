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

from core.electrique.chaines import fenetre_admissible
from core.electrique.types import SpecModule, SpecOnduleur

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


#: La fenêtre de tension que le NOYAU calcule pour ces fiches d'essai : 400 V
#: de Voc par module sous 1 000 V ⇒ 2 modules au plus (borne Voc), 3 au plus
#: sous le haut de plage MPPT ; aucune borne basse au-delà d'un module.
_MODULE = SpecModule(vmp_v=300.0, voc_v=400.0, isc_a=10.0, imp_a=9.0,
                     pmax_wc=400.0)
_ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=100.0, mppt_v_max=1000.0,
                         v_max_abs=1000.0, i_max_mppt_a=20.0, ac_kw=5.0)


class _Resultat:
    def __init__(self, chaines):
        self.chaines = chaines
        self.repartitions = ()
        self.fenetre = fenetre_admissible(_MODULE, _ONDULEUR, 25.0, 25.0)


class _Entree:
    onduleur = _ONDULEUR


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
        self.entree = _Entree()

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

    def test_le_drapeau_optimiseur_par_module_est_conserve(self):  # ACAL733
        imposee = normaliser_affectation_imposee([
            {'module': 'PAN-A#1', 'chaine': 1, 'mppt': 1, 'onduleur': 1,
             'optimiseur': True},
            {'module': 'PAN-A#2', 'chaine': 1, 'mppt': 1, 'onduleur': 1,
             'optimiseur': False},
            {'module': 'PAN-A#3', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
        ])
        lignes = {ligne['module']: ligne
                  for ligne in affectation(_conception(), imposee=imposee)}
        self.assertIs(lignes['PAN-A#1']['optimiseur'], True)
        self.assertIs(lignes['PAN-A#2']['optimiseur'], False)
        self.assertNotIn('optimiseur', lignes['PAN-A#3'])
        self.assertEqual(len(lignes), 5)  # les autres lignes : aucune clé
        for module in set(lignes) - {'PAN-A#1', 'PAN-A#2'}:
            self.assertNotIn('optimiseur', lignes[module])

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

    def test_optimiseur_non_booleen_refuse_en_nommant_module_et_champ(self):
        with self.assertRaises(AffectationInvalide) as capture:
            normaliser_affectation_imposee([
                {'module': 'PAN-A#1', 'chaine': 1, 'optimiseur': 'oui'}])
        self.assertIn('PAN-A#1', str(capture.exception))
        self.assertEqual(capture.exception.champ, 'optimiseur')

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
        # La borne VRAIE : celle que le noyau calcule (Voc 400 V par module,
        # 1 000 V au plus), jamais la longueur retenue par l'automatique.
        self.assertIn('3 modules, maximum 2', refus[0])
        self.assertIn("tension maximale 1000,0 V de l'onduleur", refus[0])
        self.assertIn('(2 modules au plus)', refus[0])

    def test_une_chaine_plus_longue_que_l_automatique_mais_dans_la_fenetre(self):
        conception = _conception()
        conception.resultat.chaines = (_Chaine('PAN-A', 1, 1, 'CH1'),
                                       _Chaine('PAN-B', 1, 2, 'CH2'))
        self.assertEqual(verdict_affectation(
            conception, normaliser_affectation_imposee([
                {'module': 'PAN-A#1', 'chaine': 1, 'mppt': 1},
                {'module': 'PAN-A#2', 'chaine': 1, 'mppt': 1}])), ())

    def test_trop_de_chaines_sur_une_entree_mppt(self):
        refus = self._verdict([
            {'module': 'PAN-A#1', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-A#2', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-B#1', 'chaine': 3, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-B#2', 'chaine': 3, 'mppt': 1, 'onduleur': 1},
        ], specs={'chaines_max_par_mppt': 1})
        self.assertTrue(any('Entrée MPPT' in message for message in refus))
        self.assertTrue(any('maximum 1' in message for message in refus))

    def test_chaines_inegales_en_parallele_sur_une_entree_refusees(self):
        refus = self._verdict([
            {'module': 'PAN-A#1', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-A#2', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-B#1', 'chaine': 3, 'mppt': 1, 'onduleur': 1},
        ])
        self.assertIn(
            "Entrée MPPT 1 : chaînes 1, 3 en parallèle de 2 et 1 modules — des "
            "chaînes en parallèle sur une même entrée doivent avoir la même "
            "longueur (des entrées différentes peuvent différer).", refus)

    def test_longueurs_differentes_sur_des_entrees_differentes_admises(self):
        refus = self._verdict([
            {'module': 'PAN-A#1', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-A#2', 'chaine': 1, 'mppt': 1, 'onduleur': 1},
            {'module': 'PAN-B#1', 'chaine': 3, 'mppt': 2, 'onduleur': 1},
        ])
        self.assertEqual([m for m in refus if 'en parallèle' in m], [])

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


class ImportCsvTest(unittest.TestCase):
    """ACAL630 — chaque refus nomme SA ligne de fichier (en-tête = 1)."""

    def _lire(self, texte):
        from apps.calepinage.services.import_affectation import (
            _lire_csv_affectation,
        )
        return _lire_csv_affectation(texte)

    def test_ligne_4_fausse_refusee_avec_son_numero(self):
        lignes, refus = self._lire(
            'module;chaine;mppt;onduleur\nPAN-A#1;1;1;1\nPAN-A#2;1;1;1\n'
            'PAN-A#3;abc;1;1')
        self.assertEqual(refus, [{
            'ligne': 4, 'colonne': 'chaine',
            'message': 'La chaîne doit être un entier strictement positif '
                       '(reçu : abc)'}])
        self.assertEqual([ligne['module'] for ligne in lignes],
                         ['PAN-A#1', 'PAN-A#2'])

    def test_csv_valide_normalise_et_verdicte(self):
        from apps.calepinage.services import chaines

        vrai = chaines.evaluer_onduleurs
        chaines.evaluer_onduleurs = lambda conception: _Evaluation()
        self.addCleanup(setattr, chaines, 'evaluer_onduleurs', vrai)
        lignes, refus = self._lire(
            'module;chaine;mppt;onduleur\nPAN-A#1;1;1;1\nPAN-A#2;1;1;1')
        self.assertEqual(refus, [])
        self.assertEqual(verdict_affectation(
            _conception(), normaliser_affectation_imposee(lignes)), ())

    def test_entete_absent_ou_colonne_inconnue_ligne_1(self):
        for texte in ('PAN-A#1;1;1;1', 'module;chaine;mppt;inverter\nx;1;1;1',
                      ''):
            with self.subTest(texte=texte):
                lignes, refus = self._lire(texte)
                self.assertEqual(lignes, [])
                self.assertEqual([r['ligne'] for r in refus], [1])

    def test_un_module_inconnu_d_un_csv_nomme_sa_ligne(self):
        """ACAL1542 — le refus « module absent » nomme SA ligne du fichier et
        renvoie au fichier, pas à l'onglet (mutant : sans numéro ⇒ échec)."""
        from unittest import mock

        from apps.calepinage.services import chaines
        from apps.calepinage.services.import_affectation import (
            importer_affectation,
        )

        vrai = chaines.evaluer_onduleurs
        chaines.evaluer_onduleurs = lambda conception: _Evaluation()
        self.addCleanup(setattr, chaines, 'evaluer_onduleurs', vrai)
        conception = _conception()
        conception.fiche_incomplete = False
        texte = ('module;chaine;mppt;onduleur\nPAN-A#1;1;1;1\nPAN-A#2;1;1;1\n'
                 'PAN-A#3;abc;1;1\nPAN-B#1;3;2;1\narea-1#99;3;2;1')
        with mock.patch(
                'apps.calepinage.services.electrique.conception_du_calepinage',
                return_value=(conception, {}, {}, {})):
            rendu = importer_affectation(object(), texte)
        self.assertEqual([r['ligne'] for r in rendu['refus']], [4])
        self.assertIn('Ligne 6 : module « area-1#99 » absent du document — '
                      'corrigez le fichier.', rendu['bloquants'])
        self.assertFalse(any('onglet Affectation' in b
                             for b in rendu['bloquants']))

    def test_module_en_double_refuse_sur_la_seconde_ligne(self):
        _lignes, refus = self._lire(
            'module;chaine;mppt;onduleur\nPAN-A#1;1;1;1\nPAN-A#1;2;1;1')
        self.assertEqual([(r['ligne'], r['colonne']) for r in refus],
                         [(3, 'module')])
