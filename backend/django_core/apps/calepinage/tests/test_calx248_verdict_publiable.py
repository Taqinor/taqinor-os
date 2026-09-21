# -*- coding: utf-8 -*-
"""CALX248 — UN VERDICT PUBLIABLE UNIQUE, ENTRÉE PAR ENTRÉE SOURCÉE.

LE CONSTAT
----------
``garde_publication`` ne regardait que DEUX choses — les bloquants d'onduleur
et la garde de terre — alors que le résultat portait déjà des omissions de
norme, de câble et de protection. Un dossier dont TOUTES les sections sont
OMISES faute de norme passait donc la garde.

PARITÉ CITÉE
------------
Aurora vend un rapport de validation comme livrable NOMMÉ
(https://aurorasolar.com/design-mode/) ; PV*SOL bloque la simulation sur ses
violations les plus graves
(https://help.valentin-software.com/pvsol/en/pages/inverters/
configuration-check/).

CE QUE CES TESTS ARMENT
-----------------------
Les CINQ sources de refus, une par une (conception, raccordement,
équilibrage, terre, tronçons) — plus un cas ENTIÈREMENT omis mais motivé qui
reste publiable, et la non-régression de la garde existante.

Tests PURS : le calepinage d'essai est un objet nu (ni ``pk``, ni société),
le matériel est résolu par une doublure du sélecteur du stock.
"""
from __future__ import annotations

import unittest
from unittest import mock

from apps.calepinage.services import electrique
from apps.calepinage.services.electrique import (
    PublicationBloquee, STATUT_MOTIF_OMIS, STATUT_MOTIF_SANS_SOURCE,
    garde_publication, verdict_publiable,
)
from core.electrique.types import (
    NATURE_FONCTIONNELLE, NATURE_MATERIELLE, STATUT_ALERTE, STATUT_BLOQUANT,
    STATUT_NON_VERIFIABLE, STATUT_OK, VerdictElectrique,
)

MODULE = {
    'vmp_v': 41.4, 'voc_v': 49.3, 'isc_a': 18.59, 'imp_a': 17.59,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}
MATERIEL = {
    'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': None,
    'designations': {'module': 'Module d essai',
                     'onduleur': 'Onduleur d essai', 'optimiseur': ''},
    'absents': (),
}
#: Le matériel de l'incident DEV-202608-0016 : la fiche PUBLIE un courant de
#: court-circuit admissible (17 A) plus bas que l'Isc d'UNE chaîne (18,59 A)
#: — configuration HORS SPÉCIFICATION, donc bloquante.
ONDULEUR_HORS_SPEC = dict(
    MATERIEL, onduleur=dict(ONDULEUR, isc_max_mppt_a=17.0))

LAYOUT = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [
        {'id': 'a', 'label': 'PAN-A',
         'geometry': {'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}},
    ],
}


class _Calepinage:
    """Un pivot NU : aucune société, aucun ``pk``, donc aucune base."""

    pk = None
    company = None

    def __init__(self, resultat=None, layout=None):
        self.roof_layout = LAYOUT if layout is None else layout
        self.resultat = resultat


def _avec_materiel(materiel=None):
    """Le matériel résolu SANS catalogue — la doublure du sélecteur."""
    return mock.patch.object(electrique, 'resoudre_materiel',
                             return_value=materiel or MATERIEL)


def _verdict(calepinage=None, **patches):
    with _avec_materiel(patches.pop('materiel', None)):
        with mock.patch.multiple(electrique, **patches) if patches \
                else _rien():
            return verdict_publiable(calepinage or _Calepinage())


class _rien:
    """Un gestionnaire de contexte neutre — évite un ``if`` dans le test."""

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def _codes(rapport):
    return {motif['code'] for motif in rapport['motifs']}


def _par_code(rapport, code):
    return next(motif for motif in rapport['motifs']
                if motif['code'] == code)


class FormeDuRapportTest(unittest.TestCase):
    """Deux clés, et quatre champs par motif — jamais plus."""

    def test_les_deux_cles_sont_toujours_presentes(self):
        rapport = _verdict()
        self.assertEqual(sorted(rapport), ['motifs', 'publiable'])
        self.assertIsInstance(rapport['publiable'], bool)

    def test_chaque_motif_porte_les_quatre_champs(self):
        for motif in _verdict()['motifs']:
            self.assertEqual(sorted(motif),
                             ['code', 'libelle', 'source', 'statut'])


class CinqSourcesDeRefusTest(unittest.TestCase):
    """Les cinq sources de refus, une par une."""

    def test_1_un_bloquant_de_conception_refuse(self):
        # Incident DEV-202608-0016 : l'Isc cumulé dépasse le courant de
        # court-circuit admissible PUBLIÉ par la fiche — une seule chaîne
        # sort déjà de la borne. La conception prononce un BLOQUANT
        # (CALX215) et il refuse la publication.
        rapport = _verdict(materiel=ONDULEUR_HORS_SPEC)
        self.assertFalse(rapport['publiable'])
        self.assertTrue(any(motif['statut'] == STATUT_BLOQUANT
                            for motif in rapport['motifs']),
                        rapport['motifs'])

    def test_2_le_raccordement_entre_dans_le_rapport(self):
        # Les trois contrôles de CALX242 sont TOUJOURS prononcés (omis et
        # motivés tant que rien n'est saisi) : ils entrent donc au rapport.
        rapport = _verdict(_Calepinage(resultat={'entree_electrique': {}}))
        self.assertLessEqual(
            {'puissance_souscrite', 'regime_phases', 'tension_nominale'},
            _codes(rapport), sorted(_codes(rapport)))

    def test_2bis_un_cos_phi_sans_source_est_un_motif_sans_source(self):
        from apps.calepinage.services.raccordement import RaccordementInvalide

        with mock.patch(
                'apps.calepinage.services.raccordement.verdicts_raccordement',
                side_effect=RaccordementInvalide(
                    'source_cos_phi : un cos φ imposé sans source est refusé',
                    champ='source_cos_phi')):
            motifs = electrique._motifs_du_raccordement(None, {}, {})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_MOTIF_SANS_SOURCE])
        self.assertEqual(motifs[0]['code'], 'RACCORDEMENT_REFUSE')

    def test_3_l_equilibrage_omis_ne_refuse_pas(self):
        # CALX243 sans seuil réglé rend un verdict NON VÉRIFIABLE motivé :
        # c'est une omission ASSUMÉE, elle ne refuse pas la publication.
        motifs = electrique._motifs_du_raccordement(
            _conception(), {'phases': 3}, {})
        desequilibre = [motif for motif in motifs
                        if motif['code'] == 'desequilibre_phases']
        self.assertTrue(desequilibre)
        self.assertEqual(desequilibre[0]['statut'], STATUT_NON_VERIFIABLE)

    def test_4_la_terre_non_justifiee_refuse(self):
        motifs = electrique._motifs_de_la_terre({
            'justification_requise': True, 'justification_fournie': False,
            'omissions': []})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_BLOQUANT])
        self.assertEqual(motifs[0]['code'], 'TERRE_JUSTIFICATION_MANQUANTE')
        self.assertIn('NF C 15-100', motifs[0]['source'])

    def test_4bis_la_terre_omise_ne_refuse_pas(self):
        motifs = electrique._motifs_de_la_terre({
            'justification_requise': False, 'justification_fournie': False,
            'omissions': ['aucune norme électrique sélectionnée']})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_MOTIF_OMIS])

    def test_5_un_cumul_de_chute_bloquant_refuse(self):
        motifs = electrique._motifs_des_troncons({
            'omissions': [],
            'verdicts': [{'code': 'chute_cumulee_dc', 'conforme': False,
                          'bloquant': True,
                          'libelle': 'Chute de tension cumulée DC',
                          'detail': 'chute cumulée de 4,20 % au-dessus du '
                                    'maximum de 3,0 %',
                          'source': 'norme'}]})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_BLOQUANT])

    def test_5bis_un_troncon_non_calculable_ne_refuse_pas(self):
        motifs = electrique._motifs_des_troncons({
            'omissions': [{'troncon': 'ch5', 'champ': 'section_mm2',
                           'motif': "aucune norme n'est choisie"}],
            'verdicts': []})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_MOTIF_OMIS])
        self.assertIn('ch5', motifs[0]['libelle'])
        self.assertIn('section_mm2', motifs[0]['libelle'])


class OmisMaisMotiveResteePubliableTest(unittest.TestCase):
    """Le cas du plan : TOUT omis, mais chaque omission est motivée."""

    def test_sans_norme_le_dossier_reste_publiable(self):
        rapport = _verdict()
        norme = _par_code(rapport, 'NORME_NON_APPLICABLE')
        self.assertEqual(norme['statut'], STATUT_MOTIF_OMIS)
        self.assertTrue(norme['libelle'])
        self.assertTrue(rapport['publiable'],
                        [motif for motif in rapport['motifs']
                         if motif['statut'] in (STATUT_BLOQUANT,
                                                STATUT_MOTIF_SANS_SOURCE)])

    def test_aucun_motif_n_est_muet(self):
        for motif in _verdict()['motifs']:
            self.assertTrue(motif['libelle'].strip(), motif)


class ProvenanceTest(unittest.TestCase):
    """Un statut CONCLUSIF sans source devient ``sans_source``."""

    def test_une_valeur_qui_juge_sans_source_refuse(self):
        motif = electrique._motif_du_verdict(VerdictElectrique(
            code='CH_TEST', nature=NATURE_MATERIELLE, statut=STATUT_ALERTE,
            libelle='une alerte sans provenance', borne=1.0, valeur=2.0,
            source=''))
        self.assertEqual(motif['statut'], STATUT_MOTIF_SANS_SOURCE)

    def test_une_abstention_sans_source_ne_refuse_pas(self):
        motif = electrique._motif_du_verdict(VerdictElectrique(
            code='CH_TEST', nature=NATURE_FONCTIONNELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle='le seuil n est pas réglé', valeur=12.0, source=''))
        self.assertEqual(motif['statut'], STATUT_NON_VERIFIABLE)

    def test_un_verdict_conclusif_sourcé_garde_son_statut(self):
        motif = electrique._motif_du_verdict(VerdictElectrique(
            code='CH_TEST', nature=NATURE_MATERIELLE, statut=STATUT_ALERTE,
            libelle='une alerte sourcée', borne=1.0, valeur=2.0,
            source='fiche constructeur onduleur'))
        self.assertEqual(motif['statut'], STATUT_ALERTE)

    def test_un_verdict_ok_n_est_pas_un_motif(self):
        class _Resultat:
            verdicts = (VerdictElectrique(
                code='CH_OK', nature=NATURE_MATERIELLE, statut=STATUT_OK,
                libelle='tout va bien', source='fiche'),)

        class _Conception:
            resultat = _Resultat()

        self.assertEqual(electrique._motifs_de_la_conception(_Conception()),
                         [])


class NonRegressionDeLaGardeTest(unittest.TestCase):
    """La garde existante refuse EXACTEMENT ce qu'elle refusait."""

    def test_la_garde_laisse_passer_ce_qu_elle_laissait_passer(self):
        calepinage = _Calepinage()
        with _avec_materiel():
            evaluation = garde_publication(calepinage)
        self.assertTrue(evaluation['publiable'])
        self.assertEqual(evaluation['bloquants'], [])

    def test_la_garde_refuse_toujours_un_bloquant_d_onduleur(self):
        with _avec_materiel(ONDULEUR_HORS_SPEC):
            with self.assertRaises(PublicationBloquee):
                garde_publication(_Calepinage())

    def test_la_garde_refuse_toujours_une_fiche_incomplete(self):
        vide = {'module': {}, 'onduleur': {}, 'optimiseur': None,
                'designations': {'module': '', 'onduleur': '',
                                 'optimiseur': ''},
                'absents': ('module PV non désigné',)}
        with _avec_materiel(vide):
            with self.assertRaises(PublicationBloquee) as refus:
                garde_publication(_Calepinage())
        self.assertIn('module PV non désigné', str(refus.exception))

    def test_la_garde_ne_lit_pas_le_verdict_publiable(self):
        # Le rapport est plus SÉVÈRE que la garde (il voit la norme, les
        # tronçons, le raccordement) : s'il la pilotait, un dossier
        # publiable hier cesserait de l'être aujourd'hui.
        import inspect

        source = inspect.getsource(garde_publication)
        self.assertNotIn('verdict_publiable', source)


def _conception():
    from apps.calepinage.services.chaines import concevoir_par_pan
    from apps.calepinage.services.electrique import temperatures_site

    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        module_designation='Module d essai',
        onduleur_designation='Onduleur d essai')


if __name__ == '__main__':      # pragma: no cover
    unittest.main()
