# -*- coding: utf-8 -*-
"""CALX212 — combien d'optimiseurs, et lequel porte quel module.

``modules_par_optimiseur`` était publié par le sélecteur du stock depuis
CAL116 et AUCUN service ne le consommait : il n'existait ni quantité
d'optimiseurs, ni carte module → optimiseur.

Quatre garanties :

1. **le ratio vient de la fiche, et de nulle part ailleurs** — 2 modules par
   optimiseur sur 7 modules donnent 4 optimiseurs, le dernier n'en portant
   qu'un ;
2. **fiche muette ⇒ ``quantite: null``** et un motif qui nomme le champ —
   jamais un 1:1 supposé ;
3. **l'affectation ne repartitionne rien** : elle suit l'ordre des modules
   que ``services/chaines.py::affectation`` produit déjà (CAL125) ;
4. **nous ne prétendons pas avoir recoupé le ratio** : la mention « ratio
   publié par la fiche, non recoupé » voyage avec lui, et les grandeurs
   d'entrée réellement publiées sont listées — OpenSolar, lui, le calcule des
   trois (tension, courant, puissance), nous le LISONS.

La fonction est PRIVÉE au module (garde CALX57 : un service public sans
appelant extérieur est rouge) ; sa surface publique est le bloc
``resultat['electrique']['optimiseurs']``, testé ici aussi.

``SimpleTestCase`` : aucune base.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx212_optimiseurs_carte -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import affectation, concevoir_par_pan
from apps.calepinage.services.electrique import (
    CLE_OPTIMISEURS, MENTION_RATIO_NON_RECOUPE, REFERENCE_OPENSOLAR_RATIO,
    _optimiseurs_du_calepinage, resultat_calepinage, temperatures_site,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}

#: Une fiche qui publie le ratio ET les trois grandeurs d'entrée.
OPTIMISEUR_COMPLET = {
    'pmax_in_w': 800.0, 'v_in_min': 12.0, 'v_in_max': 60.0,
    'i_in_max_a': 20.0, 'modules_par_optimiseur': 2,
}

#: Une fiche qui publie le ratio et RIEN de ce qui le justifierait.
OPTIMISEUR_RATIO_SEUL = {'modules_par_optimiseur': 2}

#: Une fiche muette sur le ratio.
OPTIMISEUR_MUET = {'pmax_in_w': 800.0, 'v_in_max': 60.0, 'i_in_max_a': 20.0}

#: Sept modules : le dernier optimiseur n'en portera qu'un.
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-SUD', 'geometry': {'count': 7, 'azimuthDeg': 180.0,
                                      'tiltDeg': 15.0}}]}


class _Calepinage:
    pk = 212
    statut = 'brouillon'

    def __init__(self):
        self.roof_layout = LAYOUT
        self.resultat = {'entree_electrique': {
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0}}
        self.company = None


def _materiel(optimiseur=None):
    return {
        'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': optimiseur,
        'designations': {'module': 'Module d essai',
                         'onduleur': 'Onduleur d essai',
                         'optimiseur': 'Optimiseur d essai'
                         if optimiseur else ''},
        'absents': (),
    }


def _conception():
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation='Onduleur d essai')


class RatioDeFicheTest(SimpleTestCase):
    """2 modules par optimiseur sur 7 modules = 4 optimiseurs."""

    def test_quatre_optimiseurs_et_le_dernier_n_en_porte_qu_un(self):
        bloc = _optimiseurs_du_calepinage(_conception(), OPTIMISEUR_COMPLET,
                                          'Optimiseur d essai')

        self.assertEqual(bloc['ratio'], 2)
        self.assertEqual(bloc['quantite'], 4)
        portes = {}
        for ligne in bloc['affectation']:
            portes.setdefault(ligne['optimiseur'], []).append(ligne['module'])
        self.assertEqual([len(portes[n]) for n in sorted(portes)],
                         [2, 2, 2, 1])

    def test_l_affectation_suit_l_ordre_des_modules_de_cal125(self):
        conception = _conception()
        bloc = _optimiseurs_du_calepinage(conception, OPTIMISEUR_COMPLET)

        attendus = [ligne['module'] for ligne in affectation(conception)]
        self.assertEqual([ligne['module'] for ligne in bloc['affectation']],
                         attendus)

    def test_aucun_module_n_est_oublie(self):
        bloc = _optimiseurs_du_calepinage(_conception(), OPTIMISEUR_COMPLET)

        self.assertEqual(len(bloc['affectation']), 7)


class FicheMuetteTest(SimpleTestCase):
    """Sans ratio publié, rien n'est déduit — et le motif nomme le champ."""

    def test_la_quantite_vaut_null_et_le_motif_nomme_le_champ(self):
        bloc = _optimiseurs_du_calepinage(_conception(), OPTIMISEUR_MUET,
                                          'Optimiseur d essai')

        self.assertIsNone(bloc['ratio'])
        self.assertIsNone(bloc['quantite'])
        self.assertEqual(bloc['affectation'], [])
        self.assertIn('opt_modules_par_optimiseur', bloc['motif'])
        self.assertIn('Optimiseur d essai', bloc['motif'])

    def test_aucun_un_pour_un_n_est_suppose(self):
        bloc = _optimiseurs_du_calepinage(_conception(), OPTIMISEUR_MUET)

        self.assertIn("aucun 1:1 n'est supposé", bloc['motif'])

    def test_sans_optimiseur_declare_aucun_bloc(self):
        self.assertIsNone(_optimiseurs_du_calepinage(_conception(), None))


class RatioNonRecoupeTest(SimpleTestCase):
    """Nous ne prétendons pas avoir recoupé ce que nous avons seulement lu."""

    def test_une_fiche_sans_aucune_des_trois_grandeurs_le_dit(self):
        bloc = _optimiseurs_du_calepinage(_conception(),
                                          OPTIMISEUR_RATIO_SEUL)

        self.assertEqual(bloc['ratio'], 2)
        self.assertEqual(bloc['recoupement']['grandeurs_publiees'], [])
        self.assertEqual(bloc['recoupement']['mention'],
                         MENTION_RATIO_NON_RECOUPE)

    def test_les_grandeurs_publiees_sont_listees_quand_elles_existent(self):
        bloc = _optimiseurs_du_calepinage(_conception(), OPTIMISEUR_COMPLET)

        self.assertEqual(bloc['recoupement']['grandeurs_publiees'],
                         ["tension d'entrée maximale",
                          "courant d'entrée maximal",
                          "puissance d'entrée maximale"])

    def test_la_mention_reste_la_meme_fiche_complete_ou_non(self):
        complet = _optimiseurs_du_calepinage(_conception(),
                                             OPTIMISEUR_COMPLET)
        partiel = _optimiseurs_du_calepinage(_conception(),
                                             OPTIMISEUR_RATIO_SEUL)

        self.assertEqual(complet['recoupement']['mention'],
                         partiel['recoupement']['mention'])
        self.assertIn('support.opensolar.com', REFERENCE_OPENSOLAR_RATIO)


class BlocPublieTest(SimpleTestCase):
    """La table sort dans ``resultat['electrique']``."""

    def test_la_table_est_publiee_avec_le_resultat(self):
        resultat = resultat_calepinage(
            _Calepinage(), materiel=_materiel(OPTIMISEUR_COMPLET))

        bloc = resultat['electrique'][CLE_OPTIMISEURS]
        self.assertEqual(bloc['quantite'], 4)
        self.assertEqual(len(bloc['affectation']), 7)

    def test_aucune_cle_sans_optimiseur_declare(self):
        resultat = resultat_calepinage(_Calepinage(), materiel=_materiel())

        self.assertNotIn(CLE_OPTIMISEURS, resultat['electrique'])

    def test_le_motif_de_fiche_muette_remonte_aux_avertissements(self):
        resultat = resultat_calepinage(
            _Calepinage(), materiel=_materiel(OPTIMISEUR_MUET))

        self.assertTrue(any('ratio module/optimiseur non publié' in message
                            for message in resultat['avertissements']))
