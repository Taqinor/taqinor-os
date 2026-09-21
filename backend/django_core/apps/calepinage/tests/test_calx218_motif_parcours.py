# -*- coding: utf-8 -*-
"""CALX218 — LE MOTIF DE PARCOURS D'UNE CHAÎNE, ET SA LONGUEUR DE CÂBLE.

LE CONSTAT
----------
``services/cables.py::_course_du_pan`` ne mesurait QUE la distance
euclidienne du module le plus éloigné au point de collecte : le trajet réel
le long des modules d'une chaîne (aller simple, ou aller-retour qui revient
au point de départ) n'était jamais parcouru, et le câble de chaîne était donc
systématiquement SOUS-MÉTRÉ.

PARITÉ CITÉE
------------
HelioScope offre un routage « along- vs. up/down-array »
(https://help-center.helioscope.com/hc/en-us/articles/
4419953067411-4-Electrical-Design).

CE QUE CES TESTS ARMENT
-----------------------
* une rangée de DIX modules compare les trois valeurs (motif absent / le long
  de la rangée / aller-retour) et les trouve CROISSANTES ;
* le détail de la longueur cite le motif retenu, et DIT quand aucun n'est
  saisi (le trajet n'a pas été parcouru) ;
* un motif hors énumération est REFUSÉ en nommant son champ — jamais
  interprété au mieux.

Tests PURS : ni base, ni réseau.
"""
from __future__ import annotations

import math
import unittest

from apps.calepinage.services.cables import (
    DETAIL_SANS_MOTIF, MOTIF_ALLER_RETOUR, MOTIF_LE_LONG_DE_LA_RANGEE,
    MOTIFS_PARCOURS, MotifDeParcoursInvalide, ORIGINE_PLAN, course_de_chaine,
    longueur_dc,
)

#: Dix modules en ligne, pas de 1,10 m (largeur d'un module posé en portrait
#: plus son jeu) — la rangée du plan, pas une distance choisie ici.
PAS_M = 1.10
RANGEE = [{'cx': rang * PAS_M, 'cy': 0.0} for rang in range(10)]

#: Le point de collecte SAISI, deux mètres avant le premier module : c'est là
#: que le poseur a mis son coffret.
COLLECTE = {'cx': -2.0, 'cy': 0.0}


def _longueur(motif=None, panneaux=None, chaine=None, collecte=COLLECTE):
    return course_de_chaine(chaine, panneaux if panneaux is not None
                            else RANGEE, motif, point_collecte=collecte)


class TroisValeursCroissantesTest(unittest.TestCase):
    """Une rangée de DIX modules, trois motifs, trois longueurs croissantes."""

    def test_les_trois_valeurs_sont_croissantes(self):
        absent = _longueur().valeur_m
        le_long = _longueur(MOTIF_LE_LONG_DE_LA_RANGEE).valeur_m
        aller_retour = _longueur(MOTIF_ALLER_RETOUR).valeur_m
        self.assertLess(absent, le_long)
        self.assertLess(le_long, aller_retour)

    def test_le_motif_absent_mesure_le_module_le_plus_eloigne(self):
        # 9 pas de rangée + les 2 m qui séparent le coffret du premier module.
        self.assertAlmostEqual(_longueur().valeur_m, 9 * PAS_M + 2.0,
                               places=6)

    def test_le_long_de_la_rangee_parcourt_les_modules(self):
        # 9 segments entre centres, puis le dernier module → coffret.
        attendu = 9 * PAS_M + (9 * PAS_M + 2.0)
        self.assertAlmostEqual(_longueur(MOTIF_LE_LONG_DE_LA_RANGEE).valeur_m,
                               attendu, places=6)

    def test_l_aller_retour_revient_au_point_de_collecte(self):
        attendu = 9 * PAS_M + (9 * PAS_M + 2.0) + 2.0
        self.assertAlmostEqual(_longueur(MOTIF_ALLER_RETOUR).valeur_m,
                               attendu, places=6)

    def test_la_somme_des_composantes_fait_la_longueur(self):
        for motif in (None,) + MOTIFS_PARCOURS:
            with self.subTest(motif=motif):
                longueur = _longueur(motif)
                self.assertAlmostEqual(
                    sum(valeur for _poste, valeur, _origine
                        in longueur.composantes),
                    longueur.valeur_m, places=6)


class OrigineEtDetailTest(unittest.TestCase):
    """L'origine de la longueur CITE le motif retenu."""

    def test_sans_motif_le_detail_dit_que_le_trajet_n_est_pas_parcouru(self):
        longueur = _longueur()
        self.assertEqual(longueur.detail, DETAIL_SANS_MOTIF)
        self.assertIn("n'est pas parcouru", longueur.detail)

    def test_chaque_motif_est_cite_dans_le_detail(self):
        self.assertIn('le long de la rangée',
                      _longueur(MOTIF_LE_LONG_DE_LA_RANGEE).detail)
        self.assertIn('aller-retour', _longueur(MOTIF_ALLER_RETOUR).detail)

    def test_l_origine_reste_le_plan(self):
        # Tous les centres sont MESURÉS sur le plan ; le motif est une règle
        # de parcours, pas une source de mesure.
        for motif in (None,) + MOTIFS_PARCOURS:
            with self.subTest(motif=motif):
                longueur = _longueur(motif)
                self.assertEqual(longueur.origine, ORIGINE_PLAN)
                for _poste, _valeur, origine in longueur.composantes:
                    self.assertEqual(origine, ORIGINE_PLAN)

    def test_la_chaine_nommee_apparait_dans_ses_composantes(self):
        longueur = _longueur(MOTIF_LE_LONG_DE_LA_RANGEE,
                             chaine={'repere': 'CH3'})
        postes = [poste for poste, _valeur, _origine in longueur.composantes]
        self.assertTrue(any('CH3' in poste for poste in postes), postes)


class SelectionDesModulesTest(unittest.TestCase):
    """Une chaîne qui DÉCLARE ses modules ne mesure qu'eux."""

    def test_les_modules_declares_sont_les_seuls_parcourus(self):
        entiere = _longueur(MOTIF_LE_LONG_DE_LA_RANGEE).valeur_m
        moitie = _longueur(MOTIF_LE_LONG_DE_LA_RANGEE,
                           chaine={'repere': 'CH1',
                                   'modules': [1, 2, 3, 4, 5]}).valeur_m
        self.assertLess(moitie, entiere)
        # 4 segments + le 5e module → coffret (4 pas + 2 m).
        self.assertAlmostEqual(moitie, 4 * PAS_M + (4 * PAS_M + 2.0),
                               places=6)

    def test_un_rang_hors_du_plan_est_ignore_sans_rien_inventer(self):
        longueur = _longueur(MOTIF_LE_LONG_DE_LA_RANGEE,
                             chaine={'modules': [1, 2, 99]})
        self.assertAlmostEqual(longueur.valeur_m,
                               1 * PAS_M + (1 * PAS_M + 2.0), places=6)


class RefusEtOmissionsTest(unittest.TestCase):
    """Rien n'est deviné : ni un motif, ni une longueur partielle."""

    def test_un_motif_inconnu_est_refuse_en_nommant_son_champ(self):
        with self.assertRaises(MotifDeParcoursInvalide) as refus:
            _longueur('en_serpentin')
        self.assertEqual(refus.exception.champ, 'motif_parcours')
        self.assertIn('en_serpentin', str(refus.exception))
        for motif in MOTIFS_PARCOURS:
            self.assertIn(motif, str(refus.exception))

    def test_sans_point_de_collecte_aucune_longueur(self):
        self.assertIsNone(_longueur(MOTIF_ALLER_RETOUR, collecte=None))
        self.assertIsNone(_longueur(collecte={'cx': 0.0}))

    def test_sans_centre_exploitable_aucune_longueur(self):
        self.assertIsNone(_longueur(panneaux=[]))
        self.assertIsNone(_longueur(panneaux=[{'cx': None, 'cy': 1.0}]))

    def test_un_seul_module_ne_produit_aucun_segment(self):
        longueur = _longueur(MOTIF_LE_LONG_DE_LA_RANGEE,
                             panneaux=[{'cx': 3.0, 'cy': 4.0}])
        self.assertAlmostEqual(longueur.valeur_m,
                               math.hypot(3.0 + 2.0, 4.0), places=6)


class LongueurDcTest(unittest.TestCase):
    """Le motif SAISI atteint la longueur DC publiée."""

    LAYOUT = {'zones': [{'label': 'PAN-A',
                         'geometry': {'panels': RANGEE}}]}

    def _cheminement(self, motif=None):
        pan = {'point_collecte': COLLECTE}
        if motif is not None:
            pan['motif_parcours'] = motif
        return {'pans': {'PAN-A': pan}, 'descente_m': 4.0,
                'coffret_vers_onduleur_m': 6.0,
                'onduleur_vers_tgbt_m': 12.0}

    def test_le_motif_saisi_allonge_la_liaison_dc(self):
        sans, _ = longueur_dc(self.LAYOUT, self._cheminement())
        avec, _ = longueur_dc(self.LAYOUT,
                              self._cheminement(MOTIF_ALLER_RETOUR))
        self.assertGreater(avec.valeur_m, sans.valeur_m)

    def test_le_detail_publie_cite_le_motif(self):
        longueur, manques = longueur_dc(
            self.LAYOUT, self._cheminement(MOTIF_LE_LONG_DE_LA_RANGEE))
        self.assertEqual(manques, ())
        self.assertIn('le long de la rangée', longueur.detail)

    def test_sans_motif_le_detail_le_dit(self):
        longueur, _ = longueur_dc(self.LAYOUT, self._cheminement())
        self.assertIn("n'est pas parcouru", longueur.detail)

    def test_un_motif_inconnu_devient_un_manque_nomme(self):
        longueur, manques = longueur_dc(self.LAYOUT,
                                        self._cheminement('en_serpentin'))
        self.assertIsNone(longueur)
        self.assertTrue(any('PAN-A' in manque and 'en_serpentin' in manque
                            for manque in manques), manques)


class RefusALaSaisieTest(unittest.TestCase):
    """Un motif fautif est refusé À LA SAISIE, pas au calcul."""

    class _Calepinage:
        pk = None
        company = None
        resultat = None
        roof_layout = {'zones': [{'label': 'PAN-A',
                                  'geometry': {'panels': RANGEE}}]}

    def _enregistrer(self, motif):
        from apps.calepinage.services.electrique import enregistrer_entree

        return enregistrer_entree(self._Calepinage(), {'cheminement': {
            'pans': {'PAN-A': {'point_collecte': COLLECTE,
                               'motif_parcours': motif}}}})

    def test_un_motif_inconnu_est_refuse_en_nommant_le_pan(self):
        from apps.calepinage.services.electrique import EntreeInvalide

        with self.assertRaises(EntreeInvalide) as refus:
            self._enregistrer('en_serpentin')
        self.assertEqual(refus.exception.champ,
                         'cheminement.pans.PAN-A.motif_parcours')
        self.assertIn('PAN-A', str(refus.exception))

    def test_un_motif_admis_passe(self):
        entree = self._enregistrer(MOTIF_ALLER_RETOUR)
        self.assertEqual(
            entree['cheminement']['pans']['PAN-A']['motif_parcours'],
            MOTIF_ALLER_RETOUR)


if __name__ == '__main__':      # pragma: no cover
    unittest.main()
