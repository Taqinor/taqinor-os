# -*- coding: utf-8 -*-
"""CALX206 — deux pans en PARALLÈLE sur une entrée MPPT, jamais en série.

Trois garanties, et la troisième est celle qui protège l'existant :

1. deux pans d'azimuts différents montés sur la MÊME entrée MPPT voient leurs
   Isc (et leurs Imp) S'ADDITIONNER sur cette entrée — c'est exactement le
   cumul de l'incident DEV-202608-0016, prononcé par le noyau ;
2. un groupe qui demanderait la mise en SÉRIE de deux orientations est
   REFUSÉ en citant ``REGLE_UNE_ORIENTATION_PAR_CHAINE`` ;
3. sans saisie de groupe, la répartition d'aujourd'hui est INCHANGÉE — mêmes
   chaînes, mêmes entrées, et aucune clé de plus dans le résultat publié.

``SimpleTestCase`` : aucune base, le matériel est injecté (``materiel=``).

Run :
    python manage.py test apps.calepinage.tests.test_calx206_polystring -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import (
    REGLE_UNE_ORIENTATION_PAR_CHAINE, concevoir_par_pan,
)
from apps.calepinage.services.electrique import (
    CLE_POLYSTRING, evaluation_electrique, resultat_calepinage,
    temperatures_site,
)
from apps.calepinage.services.polystring import (
    MOTIF_SANS_SAISIE, PolystringRefuse, grouper_polystring,
)

MODULE = {
    'vmp_v': 34.0, 'voc_v': 41.0, 'isc_a': 13.8, 'imp_a': 13.0,
    'pmax_wc': 550.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 120.0, 'mppt_v_max': 850.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 1,
}

#: Deux versants opposés, le cas est/ouest résidentiel que CALX206 ouvre.
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-EST', 'geometry': {'count': 8, 'azimuthDeg': 90.0,
                                      'tiltDeg': 20.0}},
    {'label': 'PAN-OUEST', 'geometry': {'count': 8, 'azimuthDeg': 270.0,
                                        'tiltDeg': 20.0}},
]}

GROUPE_EST_OUEST = [{'mppt': 1, 'pans': ['PAN-EST', 'PAN-OUEST']}]


class _Calepinage:
    """Le strict minimum lu par le service — aucun ORM, aucune base."""

    pk = 206
    statut = 'brouillon'

    def __init__(self, entree=None):
        self.roof_layout = LAYOUT
        saisie = {'temperature_min_c': -5.0, 'temperature_max_c': 70.0}
        saisie.update(entree or {})
        self.resultat = {'entree_electrique': saisie}
        self.company = None


def _materiel(**onduleur):
    return {
        'module': MODULE, 'onduleur': dict(ONDULEUR, **onduleur),
        'optimiseur': None,
        'designations': {'module': 'Module d essai',
                         'onduleur': 'Onduleur d essai', 'optimiseur': ''},
        'absents': (),
    }


def _conception(**onduleur):
    materiel = _materiel(**onduleur)
    return concevoir_par_pan(
        LAYOUT, module_specs=materiel['module'],
        onduleur_specs=materiel['onduleur'],
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation='Onduleur d essai')


def _entree(mppt):
    """L'entrée du cumul ``mppt`` dans un rendu de ``grouper_polystring``."""
    def _lire(rendu):
        for entree in rendu['entrees']:
            if entree['mppt'] == mppt:
                return entree
        return None
    return _lire


class MiseEnParalleleTest(SimpleTestCase):
    """Deux orientations sur UNE entrée : les courants s'additionnent."""

    def test_par_defaut_chaque_pan_a_son_entree(self):
        conception = _conception()
        rendu = grouper_polystring(conception)

        self.assertFalse(rendu['applique'])
        self.assertEqual(rendu['motif'], MOTIF_SANS_SAISIE)
        self.assertEqual(sorted(e['mppt'] for e in rendu['entrees']), [1, 2])

    def test_l_isc_cumule_est_celui_des_deux_pans(self):
        conception = _conception()
        avant = grouper_polystring(conception)
        rendu = grouper_polystring(conception, groupes=GROUPE_EST_OUEST)

        entree = _entree(1)(rendu)
        attendu = round(sum(c.isc_a for c in conception.chaines), 3)
        self.assertTrue(rendu['applique'])
        self.assertEqual(entree['pans'], ['PAN-EST', 'PAN-OUEST'])
        self.assertAlmostEqual(entree['isc_cumule_a'], attendu, places=3)
        # …et c'est bien PLUS que ce qu'une entrée portait avant.
        self.assertGreater(entree['isc_cumule_a'],
                           _entree(1)(avant)['isc_cumule_a'])

    def test_l_imp_cumule_suit_le_meme_chemin(self):
        conception = _conception()
        rendu = grouper_polystring(conception, groupes=GROUPE_EST_OUEST)

        attendu = round(sum(c.imp_a for c in conception.chaines), 3)
        self.assertAlmostEqual(_entree(1)(rendu)['imp_cumule_a'], attendu,
                               places=3)

    def test_chaque_pan_garde_ses_propres_chaines(self):
        conception = _conception()
        rendu = grouper_polystring(conception, groupes=GROUPE_EST_OUEST)

        # Le nombre de chaînes et leur longueur ne bougent pas : seul le
        # numéro d'entrée change.
        self.assertEqual(len(rendu['chaines']), len(conception.chaines))
        for avant, apres in zip(conception.chaines, rendu['chaines']):
            self.assertEqual(apres.pan, avant.pan)
            self.assertEqual(apres.nb_modules, avant.nb_modules)
        self.assertEqual({c.mppt for c in rendu['chaines']}, {1})

    def test_le_groupe_publie_une_branche_par_pan_avec_son_azimut(self):
        conception = _conception()
        rendu = grouper_polystring(conception, groupes=GROUPE_EST_OUEST)

        azimuts = {b['pan']: b['azimut_deg']
                   for b in rendu['groupes'][0]['branches']}
        self.assertEqual(azimuts, {'PAN-EST': 90.0, 'PAN-OUEST': 270.0})

    def test_l_isc_cumule_hors_specification_est_prononce_par_le_noyau(self):
        # Les deux pans sur une entrée dont la fiche n'admet que 20 A.
        conception = _conception(isc_max_mppt_a=20.0)
        rendu = grouper_polystring(conception, groupes=GROUPE_EST_OUEST)

        codes = {v.code for v in rendu['verdicts']}
        self.assertIn('CH_ISC_CUMULE_HORS_SPECIFICATION', codes)
        self.assertTrue(rendu['bloquants'])


class RegleUneOrientationParChaineTest(SimpleTestCase):
    """La règle de physique n'est pas ouverte : elle est CITÉE au refus."""

    def test_un_couplage_en_serie_est_refuse_en_citant_la_regle(self):
        conception = _conception()

        with self.assertRaises(PolystringRefuse) as capture:
            grouper_polystring(conception, groupes=[
                {'mppt': 1, 'pans': ['PAN-EST', 'PAN-OUEST'],
                 'couplage': 'serie'}])

        self.assertIn(REGLE_UNE_ORIENTATION_PAR_CHAINE, str(capture.exception))
        self.assertEqual(capture.exception.champ, 'groupes.0.couplage')

    def test_un_pan_inconnu_est_refuse_en_le_nommant(self):
        conception = _conception()

        with self.assertRaises(PolystringRefuse) as capture:
            grouper_polystring(conception,
                               groupes=[{'mppt': 1, 'pans': ['PAN-NORD']}])

        self.assertIn('PAN-NORD', str(capture.exception))
        self.assertEqual(capture.exception.champ, 'groupes.0.pans.0')

    def test_un_pan_reclame_deux_fois_est_refuse(self):
        conception = _conception()

        with self.assertRaises(PolystringRefuse) as capture:
            grouper_polystring(conception, groupes=[
                {'mppt': 1, 'pans': ['PAN-EST']},
                {'mppt': 2, 'pans': ['PAN-EST']}])

        self.assertEqual(capture.exception.champ, 'groupes.1.pans.0')

    def test_une_entree_que_la_fiche_n_a_pas_est_refusee(self):
        conception = _conception()

        with self.assertRaises(PolystringRefuse) as capture:
            grouper_polystring(conception,
                               groupes=[{'mppt': 5, 'pans': ['PAN-EST']}])

        self.assertEqual(capture.exception.champ, 'groupes.0.mppt')


class SansSaisieRienNeChangeTest(SimpleTestCase):
    """Le comportement d'aujourd'hui, à l'identique (D12)."""

    def test_les_chaines_rendues_sont_les_objets_de_la_conception(self):
        conception = _conception()
        rendu = grouper_polystring(conception)

        self.assertEqual(rendu['chaines'], tuple(conception.chaines))
        for avant, apres in zip(conception.chaines, rendu['chaines']):
            self.assertIs(avant, apres)

    def test_le_resultat_publie_ne_porte_aucune_cle_polystring(self):
        resultat = resultat_calepinage(_Calepinage(),
                                       materiel=_materiel())

        self.assertNotIn(CLE_POLYSTRING, resultat['electrique'])

    def test_la_saisie_publie_le_bloc_et_son_cumul(self):
        resultat = resultat_calepinage(
            _Calepinage({CLE_POLYSTRING: GROUPE_EST_OUEST}),
            materiel=_materiel())

        bloc = resultat['electrique'][CLE_POLYSTRING]
        self.assertTrue(bloc['applique'])
        self.assertEqual(bloc['groupes'][0]['pans'],
                         ['PAN-EST', 'PAN-OUEST'])

    def test_une_saisie_refusee_ne_casse_pas_le_resultat(self):
        resultat = resultat_calepinage(
            _Calepinage({CLE_POLYSTRING: [{'mppt': 1,
                                           'pans': ['PAN-NORD']}]}),
            materiel=_materiel())

        self.assertNotIn(CLE_POLYSTRING, resultat['electrique'])
        self.assertTrue(any('PAN-NORD' in message
                            for message in resultat['avertissements']))

    def test_un_regroupement_hors_specification_refuse_la_publication(self):
        evaluation = evaluation_electrique(
            _Calepinage({CLE_POLYSTRING: GROUPE_EST_OUEST}),
            materiel=_materiel(isc_max_mppt_a=20.0))

        self.assertEqual(evaluation['verdict'], 'bloquant')
        self.assertFalse(evaluation['publiable'])
        self.assertTrue(any('Isc cumulé' in message
                            for message in evaluation['bloquants']))
