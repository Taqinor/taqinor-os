"""CALX225 — une section et une chute PAR TRONÇON, pas deux pour tout le champ.

CE QUE CE FICHIER GARDE
-----------------------
1. **Trois tronçons DC en cascade rendent trois sections DÉCROISSANTES vers
   l'aval.** C'est tout le sujet : ``dimensionner_cables`` ne connaît que
   ``W1``/``W2``, donc un tronçon amont de forte intensité et un tronçon
   terminal reçoivent aujourd'hui la même section.
2. **Le plancher DC de 6 mm² reste appliqué ET NOMMÉ** (décision fondateur du
   19/08/2026, portée par le noyau) : le critère publié est celui du noyau,
   lu par sa constante et jamais recopié en texte.
3. **Norme non applicable ⇒ aucune section publiée, motif affiché** (D1) —
   et la LONGUEUR, elle, reste publiée : c'est la section qui manque, pas le
   mètre.
4. **La forme publiée est celle du contrat CALX203**, clé pour clé : les 14
   champs d'un tronçon, les 3 clés de ``totaux``, les 3 d'une omission. Une
   grandeur non calculable vaut ``null``, jamais ``0``.

Aucune base de données : ``SimpleTestCase`` pur. Le contexte électrique est
construit soit à la main (tronçon par tronçon), soit depuis une VRAIE
conception montée par ``concevoir_par_pan`` sur un plan en mémoire.

Run :
    python manage.py test apps.calepinage.tests.test_calx225_troncons_sections
"""
from __future__ import annotations

import json
import pathlib
from unittest.mock import patch

from django.test import SimpleTestCase

from core.electrique import cables as noyau

from apps.calepinage.services import troncons as service
from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import temperatures_site
from apps.calepinage.services.norme import norme_applicable

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


CONTRAT = charger('calepinage_troncons.json')
DOCUMENT_EXEMPLE = charger('electrique_cheminements.json')['exemple']

#: Les 14 champs d'un tronçon, LUS sur l'échantillon committé — le contrat
#: est la source, jamais une liste recopiée à la main dans ce test.
CHAMPS_TRONCON = set(CONTRAT['exemple']['troncons'][0])
CLES_TOTAUX = set(CONTRAT['exemple']['totaux'])
CLES_OMISSION = set(CONTRAT['exemple']['omissions'][0])

#: Les grandeurs qui valent `null` quand elles ne sont pas calculables.
GRANDEURS = ('section_mm2', 'ib_a', 'iz_a', 'chute_pct', 'chute_cumulee_pct')

NORME_FR = norme_applicable({'imagerie': {'pays': 'fr'},
                             'norme_electrique': {}})
NORME_MA = norme_applicable({'imagerie': {'pays': 'ma'},
                             'norme_electrique': {}})

TENSION_DC_V = 600.0
LONGUEUR_M = 10.0


def contexte(norme=NORME_FR, courants=None, dc=None, ac=None):
    return {'norme': norme, 'dc': dc, 'ac': ac, 'courants': courants or {}}


def cascade_dc(*courants):
    """Un document à N tronçons DC en série, de l'amont vers l'aval."""
    cheminements = []
    for rang, _courant in enumerate(courants, start=1):
        cheminements.append({
            'id': 'ch%d' % rang, 'cote': 'dc',
            'de': 'n%d' % rang, 'vers': 'n%d' % (rang + 1),
            'longueurSaisieM': LONGUEUR_M, 'points': [],
        })
    return {'electrical': {'cheminements': cheminements}}


def courants_cascade(*courants):
    return {'ch%d' % rang: {'ib_a': courant, 'tension_v': TENSION_DC_V}
            for rang, courant in enumerate(courants, start=1)}


def par_id(paquet):
    return {t['id']: t for t in paquet['troncons']}


# ── une VRAIE conception, montée sans base de données ───────────────────────
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
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-A', 'geometry': {
        'count': 6, 'azimuthDeg': 180.0, 'tiltDeg': 15.0,
        'panels': [{'cx': rang * 1.2, 'cy': 0.0} for rang in range(6)]}},
]}


def conception_reelle():
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation='Onduleur d essai')


class CascadeDecroissanteTest(SimpleTestCase):
    """Le courant décroît vers l'aval : la section aussi."""

    def setUp(self):
        # 130 A / 90 A / 50 A : trois exigences d'échauffement distinctes du
        # barème H1Z2Z2-K, la dernière sous le plancher DC.
        self.troncons = par_id(service._troncons_du_document(
            cascade_dc(130.0, 90.0, 50.0),
            contexte(courants=courants_cascade(130.0, 90.0, 50.0))))

    def test_trois_sections_strictement_decroissantes(self):
        sections = [self.troncons['ch%d' % rang]['section_mm2']
                    for rang in (1, 2, 3)]
        self.assertEqual(len(set(sections)), 3,
                         'trois tronçons, trois sections : %r' % (sections,))
        self.assertGreater(sections[0], sections[1])
        self.assertGreater(sections[1], sections[2])

    def test_chaque_troncon_publie_son_propre_courant(self):
        self.assertEqual(self.troncons['ch1']['ib_a'], 130.0)
        self.assertEqual(self.troncons['ch2']['ib_a'], 90.0)
        self.assertEqual(self.troncons['ch3']['ib_a'], 50.0)

    def test_chaque_troncon_publie_sa_propre_chute(self):
        chutes = [self.troncons['ch%d' % rang]['chute_pct']
                  for rang in (1, 2, 3)]
        for chute in chutes:
            self.assertIsNotNone(chute)
            self.assertGreater(chute, 0.0)

    def test_le_plancher_dc_est_applique_et_nomme(self):
        """Le tronçon terminal tombe sous 6 mm² : le plancher tranche."""
        terminal = self.troncons['ch3']
        self.assertEqual(terminal['section_mm2'],
                         noyau.SECTION_MIN_DC_MM2)
        self.assertEqual(terminal['critere_dimensionnant'],
                         noyau.CRITERE_PLANCHER)

    def test_la_regle_source_cite_des_references_pas_des_nombres(self):
        source = self.troncons['ch1']['regle_source']
        for reference in ('EN 50618', 'IEC 62548', 'NF C 15-100'):
            self.assertIn(reference, source)


class NormeNonApplicableTest(SimpleTestCase):
    """D1 — pays « ma » sans norme : le dimensionnement s'OMET en le disant."""

    def setUp(self):
        self.paquet = service._troncons_du_document(
            DOCUMENT_EXEMPLE,
            contexte(norme=NORME_MA,
                     dc={'ib_a': 23.0, 'tension_v': TENSION_DC_V},
                     ac={'ib_a': 21.7, 'tension_v': 400.0, 'phases': 3}))

    def test_aucune_section_publiee(self):
        for troncon in self.paquet['troncons']:
            for grandeur in GRANDEURS:
                self.assertIsNone(troncon[grandeur],
                                  '%s.%s devrait être omis sans norme'
                                  % (troncon['id'], grandeur))

    def test_la_longueur_reste_publiee(self):
        for troncon in self.paquet['troncons']:
            self.assertIsNotNone(troncon['longueur_m'])
            self.assertIsNotNone(troncon['longueur_origine'])

    def test_chaque_omission_nomme_le_troncon_le_champ_et_la_norme(self):
        omissions = [o for o in self.paquet['omissions']
                     if o['champ'] == 'section_mm2']
        self.assertEqual(len(omissions),
                         len(self.paquet['troncons']))
        for omission in omissions:
            self.assertIn('norme', omission['motif'])
            self.assertIn('norme_applicable', omission['motif'])

    def test_le_metre_garde_la_ligne_de_section_omise(self):
        lignes = self.paquet['totaux']['metre_par_section']
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0]['section_mm2'])
        attendu = sum(t['longueur_m'] for t in self.paquet['troncons'])
        self.assertAlmostEqual(lignes[0]['longueur_m'], round(attendu, 2),
                               places=2)


class ContratTest(SimpleTestCase):
    """La sortie épingle ``calepinage_troncons.json``, clé pour clé."""

    def setUp(self):
        self.paquet = service._troncons_du_document(
            DOCUMENT_EXEMPLE,
            contexte(dc={'ib_a': 23.0, 'i_service_a': 17.1,
                         'tension_v': TENSION_DC_V, 'calibre_in_a': None},
                     ac={'ib_a': 21.7, 'tension_v': 400.0, 'phases': 3,
                         'calibre_in_a': 25.0}))

    def test_les_quatorze_champs_dun_troncon(self):
        for troncon in self.paquet['troncons']:
            self.assertEqual(set(troncon), CHAMPS_TRONCON,
                             'tronçon %s' % troncon['id'])

    def test_les_cles_de_totaux(self):
        self.assertEqual(set(self.paquet['totaux']), CLES_TOTAUX)

    def test_les_cles_dune_omission(self):
        for omission in self.paquet['omissions']:
            self.assertEqual(set(omission), CLES_OMISSION)

    def test_les_troncons_sont_ceux_du_document(self):
        attendus = [c['id'] for c
                    in DOCUMENT_EXEMPLE['electrical']['cheminements']]
        self.assertEqual([t['id'] for t in self.paquet['troncons']], attendus)

    def test_la_terre_nest_pas_dimensionnee_mais_reste_mesuree(self):
        terre = par_id(self.paquet)['ch5']
        self.assertEqual(terre['nb_conducteurs'],
                         service.NB_CONDUCTEURS_TERRE)
        self.assertIsNone(terre['section_mm2'])
        self.assertIsNotNone(terre['longueur_m'])
        motifs = [o['motif'] for o in self.paquet['omissions']
                  if o['troncon'] == 'ch5']
        self.assertTrue(any('terre' in m for m in motifs), motifs)

    def test_le_metre_se_recompose_depuis_les_troncons(self):
        attendu = {}
        for troncon in self.paquet['troncons']:
            if troncon['longueur_m'] is None:
                continue
            cle = troncon['section_mm2']
            attendu[cle] = attendu.get(cle, 0.0) + troncon['longueur_m']
        lignes = {ligne['section_mm2']: ligne['longueur_m']
                  for ligne in self.paquet['totaux']['metre_par_section']}
        self.assertEqual(set(lignes), set(attendu))
        for section, longueur in attendu.items():
            self.assertAlmostEqual(lignes[section], round(longueur, 2),
                                   places=2)

    def test_un_troncon_sans_longueur_ne_compte_pas_au_metre(self):
        paquet = service._troncons_du_document(
            {'electrical': {'cheminements': [
                {'id': 'chX', 'cote': 'dc', 'points': []}]}},
            contexte(dc={'ib_a': 23.0, 'tension_v': TENSION_DC_V}))
        self.assertEqual(paquet['totaux']['metre_par_section'], [])

    def test_le_nombre_de_conducteurs_suit_le_cote(self):
        troncons = par_id(self.paquet)
        self.assertEqual(troncons['ch1']['nb_conducteurs'],
                         service.NB_CONDUCTEURS_DC)
        self.assertEqual(troncons['ch3']['nb_conducteurs'],
                         service.NB_CONDUCTEURS_AC_TRI)


class ContexteDepuisLaConceptionTest(SimpleTestCase):
    """Le courant vient de la CONCEPTION du calepinage — lecture seule."""

    def test_une_conception_reelle_publie_les_deux_cotes(self):
        contexte_lu = service._contexte_electrique(conception_reelle(),
                                                   NORME_FR)
        self.assertIsNotNone(contexte_lu['dc'])
        self.assertIsNotNone(contexte_lu['ac'])
        self.assertGreater(contexte_lu['dc']['ib_a'], MODULE['isc_a'])
        self.assertEqual(contexte_lu['dc']['i_service_a'], MODULE['imp_a'])
        self.assertEqual(contexte_lu['ac']['phases'], ONDULEUR['phases'])

    def test_sans_chaine_le_contexte_dit_ce_qui_manque(self):
        contexte_lu = service._contexte_electrique(None, NORME_FR)
        self.assertIsNone(contexte_lu['dc'])
        self.assertIn('chaîne', contexte_lu['manque'])

    def test_sans_courant_la_section_est_omise_en_nommant_le_champ(self):
        paquet = service._troncons_du_document(
            cascade_dc(1.0), service._contexte_electrique(None, NORME_FR))
        self.assertIsNone(par_id(paquet)['ch1']['section_mm2'])
        omission = [o for o in paquet['omissions']
                    if o['champ'] == 'ib_a'][0]
        self.assertIn('ib_a', omission['motif'])
        self.assertIn('chaîne', omission['motif'])


class EnveloppeTest(SimpleTestCase):
    """L'enveloppe ne fait que LIRE : document, norme, conception."""

    @patch('apps.calepinage.services.electrique.parametres_societe')
    @patch('apps.calepinage.services.electrique.conception_du_calepinage')
    def test_le_calepinage_traverse_jusquau_metre(self, conception, reglages):
        reglages.return_value = {'imagerie': {'pays': 'fr'},
                                 'norme_electrique': {}}
        conception.return_value = (conception_reelle(), {}, {},
                                   DOCUMENT_EXEMPLE)

        paquet = service.troncons_du_calepinage(object())

        self.assertEqual(set(paquet['totaux']), CLES_TOTAUX)
        self.assertEqual(len(paquet['troncons']),
                         len(DOCUMENT_EXEMPLE['electrical']['cheminements']))
        for troncon in paquet['troncons']:
            self.assertEqual(set(troncon), CHAMPS_TRONCON)
        dc = par_id(paquet)['ch1']
        self.assertIsNotNone(dc['section_mm2'])
        self.assertGreaterEqual(dc['section_mm2'], noyau.SECTION_MIN_DC_MM2)
