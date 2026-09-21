# -*- coding: utf-8 -*-
"""CALX215 (crochet de phase 2) — LA DÉROGATION S'ÉCRIT DANS LE FIL.

Le noyau livrait déjà ``passer_outre`` (auteur, date AVISÉE, motif saisi, et
le refus d'un bloquant) — mais personne n'écrivait la trace : une alerte
passée outre ne laissait AUCUN souvenir relisible six mois plus tard.

Ces tests arment les trois promesses du crochet :

* la trace porte l'auteur, l'instant AVISÉ et le motif SAISI ;
* un BLOQUANT ne se passe jamais outre, et le refus NOMME son champ ;
* l'écriture emprunte la MÊME mécanique de fil que l'écart de longueur
  (CAL170) — un seul tampon borné, jamais un second.

Tests PURS : aucune base (``conception_du_calepinage`` est remplacé par une
doublure là où il est appelé, et la conception elle-même est un objet nu).
"""
from __future__ import annotations

import datetime
import unittest
from unittest import mock

from apps.calepinage.services import electrique
from core.electrique.types import (
    NATURE_FONCTIONNELLE, NATURE_MATERIELLE, STATUT_ALERTE, STATUT_BLOQUANT,
    VerdictElectrique,
)

ALERTE = VerdictElectrique(
    code='CH_VMP_FROID_AU_DESSUS_MPPT', nature=NATURE_FONCTIONNELLE,
    statut=STATUT_ALERTE,
    libelle="Vmp à froid 620 V > haut de plage MPPT 600 V",
    borne=600.0, valeur=620.0, source='fiche constructeur onduleur')

BLOQUANT = VerdictElectrique(
    code='CH_VOC_FROID_AU_DESSUS_V_MAX', nature=NATURE_MATERIELLE,
    statut=STATUT_BLOQUANT,
    libelle="Voc à froid 1120 V > tension maximale onduleur 1100 V",
    borne=1100.0, valeur=1120.0, source='fiche constructeur onduleur')


class _Resultat:
    """Le ``ResultatChaines`` réduit à ce que la dérogation lui demande."""

    def __init__(self, verdicts):
        self.verdicts = tuple(verdicts)


class _Conception:
    def __init__(self, verdicts=(ALERTE, BLOQUANT)):
        self.resultat = _Resultat(verdicts)


class _Utilisateur:
    def __init__(self, nom='', username=''):
        self._nom, self.username = nom, username

    def get_full_name(self):
        return self._nom


class _Calepinage:
    """Un calepinage NU : aucun ``pk``, donc aucune écriture en base."""

    pk = None
    company = None
    roof_layout = None

    def __init__(self, resultat=None):
        self.resultat = resultat


class TraceDeDerogationTest(unittest.TestCase):
    """Ce que la trace porte, et ce qu'elle refuse."""

    def test_une_alerte_passee_outre_porte_auteur_date_et_motif(self):
        traces = electrique._traces_de_derogation(
            _Conception(), [{'code': ALERTE.code, 'motif': 'toiture plein sud'}],
            user=_Utilisateur(nom='Meryem Alaoui'))
        self.assertEqual(len(traces), 1)
        trace = traces[0]
        self.assertEqual(trace['code'], ALERTE.code)
        self.assertEqual(trace['auteur'], 'Meryem Alaoui')
        self.assertEqual(trace['motif'], 'toiture plein sud')
        self.assertEqual(trace['libelle'], ALERTE.libelle)
        # L'instant est AVISÉ : relu depuis un autre fuseau, il désigne encore
        # le même moment (c'est ce qui rend la trace opposable).
        instant = datetime.datetime.fromisoformat(trace['horodatage'])
        self.assertIsNotNone(instant.tzinfo)
        self.assertIn('passée outre par Meryem Alaoui', trace['texte'])

    def test_un_bloquant_ne_se_passe_jamais_outre(self):
        with self.assertRaises(electrique.EntreeInvalide) as refus:
            electrique._traces_de_derogation(
                _Conception(), [{'code': BLOQUANT.code, 'motif': 'assumé'}],
                user=_Utilisateur(nom='Meryem Alaoui'))
        self.assertEqual(refus.exception.champ, 'derogations.1.code')
        self.assertIn('bloquant', str(refus.exception))

    def test_un_motif_vide_est_refuse_en_nommant_son_champ(self):
        with self.assertRaises(electrique.EntreeInvalide) as refus:
            electrique._traces_de_derogation(
                _Conception(), [{'code': ALERTE.code, 'motif': '  '}],
                user=_Utilisateur(nom='Meryem Alaoui'))
        self.assertEqual(refus.exception.champ, 'derogations.1.motif')

    def test_sans_utilisateur_la_derogation_est_refusee_sur_l_auteur(self):
        with self.assertRaises(electrique.EntreeInvalide) as refus:
            electrique._traces_de_derogation(
                _Conception(), [{'code': ALERTE.code, 'motif': 'assumé'}])
        self.assertEqual(refus.exception.champ, 'derogations.1.auteur')

    def test_un_code_absent_de_la_conception_est_refuse(self):
        with self.assertRaises(electrique.EntreeInvalide) as refus:
            electrique._traces_de_derogation(
                _Conception(), [{'code': 'CH_INVENTE', 'motif': 'assumé'}],
                user=_Utilisateur(nom='Meryem Alaoui'))
        self.assertEqual(refus.exception.champ, 'derogations.1.code')
        self.assertIn('CH_INVENTE', str(refus.exception))

    def test_un_verdict_se_lit_par_son_code_jamais_par_sa_position(self):
        conception = _Conception(verdicts=(BLOQUANT, ALERTE))
        self.assertIs(electrique._verdict_par_code(conception, ALERTE.code),
                      ALERTE)
        self.assertIsNone(
            electrique._verdict_par_code(conception, 'CH_INVENTE'))

    def test_deux_derogations_d_un_meme_geste_portent_le_meme_instant(self):
        conception = _Conception(verdicts=(
            ALERTE,
            VerdictElectrique(code='CH_VMP_CHAUD_SOUS_MPPT',
                              nature=NATURE_FONCTIONNELLE,
                              statut=STATUT_ALERTE, libelle='MPPT hors plage',
                              source='fiche constructeur onduleur')))
        traces = electrique._traces_de_derogation(
            conception,
            [{'code': ALERTE.code, 'motif': 'un'},
             {'code': 'CH_VMP_CHAUD_SOUS_MPPT', 'motif': 'deux'}],
            user=_Utilisateur(nom='Meryem Alaoui'))
        self.assertEqual(traces[0]['horodatage'], traces[1]['horodatage'])

    def test_une_saisie_qui_n_est_pas_une_liste_est_refusee(self):
        with self.assertRaises(electrique.EntreeInvalide) as refus:
            electrique._traces_de_derogation(_Conception(), {'code': 'x'},
                                             user=_Utilisateur(nom='M'))
        self.assertEqual(refus.exception.champ, 'derogations')


class FilUniqueTest(unittest.TestCase):
    """UNE mécanique de fil pour les deux historiques du module."""

    def test_le_fil_est_borne_et_garde_les_plus_recentes(self):
        resultat = {}
        for rang in range(electrique.JOURNAL_ECARTS_MAX + 5):
            electrique._ajouter_au_fil(resultat, electrique.CLE_FIL_ECARTS,
                                       [{'ecart': rang}])
        fil = resultat[electrique.CLE_FIL_ECARTS]
        self.assertEqual(len(fil), electrique.JOURNAL_ECARTS_MAX)
        self.assertEqual(fil[-1]['ecart'],
                         electrique.JOURNAL_ECARTS_MAX + 4)

    def test_les_deux_fils_ont_des_clefs_distinctes(self):
        self.assertNotEqual(electrique.CLE_FIL_ECARTS,
                            electrique.CLE_FIL_DEROGATIONS)

    def test_un_fil_illisible_ne_fait_pas_perdre_le_geste(self):
        resultat = {electrique.CLE_FIL_DEROGATIONS: 'pas une liste'}
        fil = electrique._ajouter_au_fil(
            resultat, electrique.CLE_FIL_DEROGATIONS, [{'code': 'A'}])
        self.assertEqual(fil, [{'code': 'A'}])


class EnregistrerEntreeTest(unittest.TestCase):
    """Le geste complet — sans base : ``pk`` est ``None``, rien n'est sauvé."""

    def _avec_conception(self, conception=None):
        return mock.patch.object(
            electrique, 'conception_du_calepinage',
            return_value=(conception or _Conception(), {}, {}, None))

    def test_la_derogation_part_dans_le_fil_et_pas_dans_l_entree(self):
        calepinage = _Calepinage()
        with self._avec_conception():
            entree = electrique.enregistrer_entree(
                calepinage,
                {'phases': 1,
                 'derogations': [{'code': ALERTE.code, 'motif': 'assumé'}]},
                user=_Utilisateur(nom='Meryem Alaoui'))
        self.assertEqual(entree, {'phases': 1})
        self.assertNotIn(electrique.CLE_DEROGATIONS, entree)
        fil = calepinage.resultat[electrique.CLE_FIL_DEROGATIONS]
        self.assertEqual([trace['code'] for trace in fil], [ALERTE.code])

    def test_un_refus_laisse_le_calepinage_intact(self):
        calepinage = _Calepinage(resultat={'entree_electrique': {'phases': 3}})
        with self._avec_conception():
            with self.assertRaises(electrique.EntreeInvalide):
                electrique.enregistrer_entree(
                    calepinage,
                    {'phases': 1,
                     'derogations': [{'code': BLOQUANT.code, 'motif': 'x'}]},
                    user=_Utilisateur(nom='Meryem Alaoui'))
        self.assertEqual(calepinage.resultat,
                         {'entree_electrique': {'phases': 3}})

    def test_sans_derogation_la_conception_n_est_meme_pas_calculee(self):
        calepinage = _Calepinage()
        with self._avec_conception() as doublure:
            electrique.enregistrer_entree(calepinage, {'phases': 1})
        doublure.assert_not_called()
        self.assertNotIn(electrique.CLE_FIL_DEROGATIONS, calepinage.resultat)

    def test_le_champ_derogations_est_admis_par_l_entree(self):
        self.assertIn(electrique.CLE_DEROGATIONS, electrique.CHAMPS_ENTREE)


if __name__ == '__main__':      # pragma: no cover
    unittest.main()
