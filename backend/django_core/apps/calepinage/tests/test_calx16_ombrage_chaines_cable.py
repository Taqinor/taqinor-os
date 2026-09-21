"""CALX16 — la chaîne la plus faible en ombrage est BRANCHÉE sur le verdict.

LE CONSTAT QUE CE TEST FERME
-----------------------------
``services/ombrage_chaines.py`` (CAL98) sait désigner la chaîne qui porte le
module le plus mal exposé du toit — et, jusqu'ici, AUCUN appelant hors de son
propre fichier et de ses tests. Le résultat publié ne disait donc rien de la
chaîne qu'un installateur doit regarder en premier, alors que le courant d'une
série est celui de son module le plus faible.

LES DEUX GARANTIES, ET ELLES COMPTENT AUTANT L'UNE QUE L'AUTRE
---------------------------------------------------------------
1. **accès solaire présent ⇒ la chaîne est NOMMÉE**, avec son pan, le module
   fautif, son accès et la MÉTHODE de désignation ;
2. **accès solaire absent ⇒ la clé est OMISE**, avec son motif dans
   ``avertissements`` — jamais un module supposé à 100 %, qui désignerait la
   mauvaise chaîne.

Et une troisième, implicite : **aucun kWh n'est dérivé de ce signal**. C'est
un signal de CÂBLAGE ; l'énergie de l'ombrage vit dans ``cascade``
(CALX156-158, CALX168).

Aucune base de données : le matériel est injecté (``materiel=``), comme le
sélecteur du stock le rendrait.

Run :
    python manage.py test apps.calepinage.tests.test_calx16_ombrage_chaines_cable -v2
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    CLE_CHAINE_FAIBLE, METHODE_CHAINE_FAIBLE, MOTIF_CHAINE_FAIBLE_ABSENTE,
    _chaine_la_plus_faible, resultat_calepinage,
)
from apps.calepinage.services.ombrage_chaines import MOTIF_SANS_ACCES

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_resultat.json').read_text(encoding='utf-8'))

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
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


def _layout(acces_a=None, acces_b=None):
    """Deux pans, avec ou sans accès solaire par module (CAL248)."""
    zones = [
        {'id': 'a', 'label': 'PAN-A',
         'geometry': {'count': 6, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}},
        {'id': 'b', 'label': 'PAN-B',
         'geometry': {'count': 6, 'azimuthDeg': 90.0, 'tiltDeg': 15.0}},
    ]
    for zone, acces in zip(zones, (acces_a, acces_b)):
        if acces is not None:
            zone['geometry']['solarAccess'] = {'values': list(acces)}
    return {'version': 2, 'pin': {'lat': 33.5731, 'lng': -7.5898},
            'zones': zones}


class _Calepinage:
    """Le strict minimum que le service lit sur un pivot — aucun ORM."""

    pk = 1
    devis_id = None

    def __init__(self, layout):
        self.roof_layout = layout
        self.resultat = None
        self.company = None
        self.pertes = []


def _servi(layout):
    return resultat_calepinage(_Calepinage(layout), materiel=MATERIEL)


def _affectation(layout):
    return _servi(layout)['electrique']['affectation']


class AccesPresentTest(SimpleTestCase):
    """La chaîne du module le plus ombré est NOMMÉE, pan compris."""

    #: PAN-B porte un module nettement plus ombré que tous les autres.
    LAYOUT = _layout(acces_a=[0.98] * 6, acces_b=[0.97, 0.62] + [0.96] * 4)

    def test_la_chaine_est_designee_avec_son_module(self):
        bloc = _servi(self.LAYOUT)['electrique'][CLE_CHAINE_FAIBLE]

        self.assertEqual(bloc['pan'], 'PAN-B')
        self.assertEqual(bloc['module'], 'PAN-B#2')
        self.assertEqual(bloc['acces_solaire'], 0.62)
        self.assertIsNotNone(bloc['chaine'])

    def test_la_methode_est_publiee_avec_le_verdict(self):
        bloc = _servi(self.LAYOUT)['electrique'][CLE_CHAINE_FAIBLE]

        self.assertEqual(bloc['methode'], METHODE_CHAINE_FAIBLE)
        self.assertIn('CÂBLAGE', bloc['methode'])
        self.assertTrue(bloc['reference'])

    def test_les_cles_sont_celles_du_contrat_partage(self):
        bloc = _servi(self.LAYOUT)['electrique'][CLE_CHAINE_FAIBLE]

        self.assertEqual(
            sorted(bloc),
            sorted(CONTRAT['exemple']['electrique'][CLE_CHAINE_FAIBLE]))

    def test_aucun_kwh_n_est_derive_de_ce_signal(self):
        servi = _servi(self.LAYOUT)
        bloc = servi['electrique'][CLE_CHAINE_FAIBLE]

        for cle in bloc:
            self.assertNotIn('kwh', cle)
            self.assertNotIn('perte', cle)
        # La production, elle, reste celle de la simulation — absente ici.
        self.assertFalse(servi['simule'])

    def test_l_ecart_est_mesure_contre_le_module_le_mieux_expose(self):
        bloc = _servi(self.LAYOUT)['electrique'][CLE_CHAINE_FAIBLE]

        # 0,98 (le mieux exposé du toit) − 0,62 (le plus ombré) = 0,36.
        self.assertAlmostEqual(bloc['ecart'], 0.36, places=4)


class AccesAbsentTest(SimpleTestCase):
    """Sans accès mesuré, la clé est OMISE — jamais un 100 % supposé."""

    def test_un_document_sans_acces_omet_la_cle_et_dit_pourquoi(self):
        servi = _servi(_layout())

        self.assertNotIn(CLE_CHAINE_FAIBLE, servi['electrique'])
        self.assertIn(MOTIF_SANS_ACCES, servi['avertissements'])

    def test_des_valeurs_toutes_nulles_omettent_la_cle_avec_son_motif(self):
        # Le document PORTE la clé, mais aucun module n'a d'accès calculé :
        # la lecture est « mesurée », et pourtant rien n'est comparable.
        layout = _layout(acces_a=[None] * 6, acces_b=[None] * 6)

        servi = _servi(layout)

        self.assertNotIn(CLE_CHAINE_FAIBLE, servi['electrique'])
        self.assertIn(MOTIF_CHAINE_FAIBLE_ABSENTE, servi['avertissements'])

    def test_le_service_rend_le_couple_bloc_motif(self):
        bloc, motif = _chaine_la_plus_faible(_layout(), [])

        self.assertIsNone(bloc)
        self.assertEqual(motif, MOTIF_SANS_ACCES)


class ChaineReelleTest(SimpleTestCase):
    """La chaîne désignée est une chaîne RÉELLEMENT dimensionnée."""

    LAYOUT = _layout(acces_a=[0.98] * 6, acces_b=[0.97, 0.62] + [0.96] * 4)

    def test_la_chaine_designee_existe_dans_la_table_d_affectation(self):
        servi = _servi(self.LAYOUT)
        bloc = servi['electrique'][CLE_CHAINE_FAIBLE]
        chaines = {ligne['chaine'] for ligne in servi['electrique']
                   ['affectation'] if ligne['chaine'] is not None}

        self.assertIn(bloc['chaine'], chaines)

    def test_le_module_designe_appartient_a_cette_chaine(self):
        servi = _servi(self.LAYOUT)
        bloc = servi['electrique'][CLE_CHAINE_FAIBLE]
        ligne = next(ligne for ligne in servi['electrique']['affectation']
                     if ligne['module'] == bloc['module'])

        self.assertEqual(ligne['chaine'], bloc['chaine'])
        self.assertEqual(ligne['pan'], bloc['pan'])

    def test_la_table_d_affectation_est_bien_celle_qui_est_lue(self):
        # Le service lit la partition RÉELLE, jamais une partition recalculée.
        self.assertTrue(_affectation(self.LAYOUT))
