"""CALX224 — la longueur RÉELLE d'un tronçon : plan, saisie, ou les deux.

CE QUE CE FICHIER GARDE
-----------------------
1. **Les trois origines de longueur**, exercées sur l'exemple COMMITTÉ de
   CALX202 (``contract_samples/electrique_cheminements.json``) : ``ch1`` et
   ``ch2`` (polyligne pure), ``ch4`` (saisie pure), ``ch3`` (mixte). L'origine
   CALCULÉE doit retomber sur celle que le document DÉCLARE — sinon l'une des
   deux ment.
2. **Aucune longueur par défaut n'est jamais substituée** : sans tracé
   exploitable ET sans longueur saisie, ``longueur_m`` vaut ``null`` (jamais
   ``0``) et une omission NOMME le tronçon, le champ et le motif.
3. **Le dénivelé entre quand il est connu, et seulement là.** Deux points
   confondus séparés de 3 m d'altitude font 3 m de câble ; si l'un des deux
   n'a pas d'``altitudeM``, le segment est compté à plat (CALX202 : une
   altitude absente ne veut pas dire « au sol »).
4. **La polyligne est additive** : mesurer A→B→C revient à mesurer A→B puis
   B→C. Une mesure qui ne l'est pas n'est pas une longueur.

Aucune base de données : ``SimpleTestCase`` pur sur des documents en mémoire.

Run :
    python manage.py test apps.calepinage.tests.test_calx224_troncons_longueur
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services import troncons as service

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')

CHEMINEMENTS = json.loads(
    (ECHANTILLONS / 'electrique_cheminements.json').read_text(
        encoding='utf-8'))

#: Le fragment de document servi par `GET layout/` — lu TEL QUEL.
DOCUMENT_EXEMPLE = CHEMINEMENTS['exemple']

LAT = 33.5
LNG = -7.6


def point(lng=LNG, lat=LAT, altitude='absente'):
    brut = {'lng': lng, 'lat': lat}
    if altitude != 'absente':
        brut['altitudeM'] = altitude
    return brut


def document(*cheminements):
    return {'electrical': {'cheminements': list(cheminements)}}


def par_id(paquet):
    return {t['id']: t for t in paquet['troncons']}


class Calepinage:
    """Le strict minimum qu'une enveloppe MINCE lit : le document."""

    def __init__(self, roof_layout):
        self.roof_layout = roof_layout


class TroisOriginesTest(SimpleTestCase):
    """Les trois cas de test que l'exemple de CALX202 exerce."""

    def setUp(self):
        self.troncons = par_id(service.troncons_du_calepinage(
            Calepinage(DOCUMENT_EXEMPLE)))

    def test_polyligne_pure_lit_le_plan(self):
        for identifiant in ('ch1', 'ch2', 'ch5'):
            troncon = self.troncons[identifiant]
            self.assertEqual(troncon['longueur_origine'], 'plan',
                             '%s : tracé seul, origine « plan » attendue'
                             % identifiant)
            self.assertIsNotNone(troncon['longueur_m'])
            self.assertGreater(troncon['longueur_m'], 0.0)

    def test_saisie_pure_rend_exactement_la_valeur_saisie(self):
        """``ch4`` n'a aucun point : la longueur EST la saisie, au réel."""
        self.assertEqual(self.troncons['ch4']['longueur_origine'], 'saisie')
        self.assertEqual(self.troncons['ch4']['longueur_m'], 12.0)

    def test_mixte_additionne_le_trace_et_la_saisie(self):
        """``ch3`` = tracé plan PLUS une descente saisie de 3,2 m."""
        mixte = self.troncons['ch3']
        self.assertEqual(mixte['longueur_origine'], 'mixte')
        sans_saisie = dict(
            [c for c in DOCUMENT_EXEMPLE['electrical']['cheminements']
             if c['id'] == 'ch3'][0])
        sans_saisie.pop('longueurSaisieM')
        trace_seul = par_id(service.troncons_du_calepinage(
            Calepinage(document(sans_saisie))))['ch3']
        self.assertEqual(trace_seul['longueur_origine'], 'plan')
        self.assertAlmostEqual(mixte['longueur_m'],
                               round(trace_seul['longueur_m'] + 3.2, 2),
                               places=2)

    def test_l_origine_calculee_retombe_sur_celle_du_document(self):
        for cheminement in DOCUMENT_EXEMPLE['electrical']['cheminements']:
            self.assertEqual(
                self.troncons[cheminement['id']]['longueur_origine'],
                cheminement['origine'],
                '%s : origine déclarée et origine mesurée divergent'
                % cheminement['id'])

    def test_les_extremites_du_document_sont_recopiees(self):
        for cheminement in DOCUMENT_EXEMPLE['electrical']['cheminements']:
            troncon = self.troncons[cheminement['id']]
            self.assertEqual(troncon['cote'], cheminement['cote'])
            self.assertEqual(troncon['de'], cheminement['de'])
            self.assertEqual(troncon['vers'], cheminement['vers'])


class AucuneLongueurParDefautTest(SimpleTestCase):
    """Sans mesure, ``null`` et un motif — jamais ``0``, jamais un forfait."""

    def _sans_rien(self):
        return service.troncons_du_calepinage(Calepinage(document(
            {'id': 'chX', 'cote': 'dc', 'de': 'z1', 'vers': 'eq2',
             'points': []})))

    def test_ni_trace_ni_saisie_rend_null_et_pas_zero(self):
        troncon = par_id(self._sans_rien())['chX']
        self.assertIsNone(troncon['longueur_m'])
        self.assertIsNone(troncon['longueur_origine'])

    def test_le_motif_nomme_le_troncon_le_champ_et_les_deux_saisies(self):
        omissions = self._sans_rien()['omissions']
        self.assertEqual(len(omissions), 1)
        omission = omissions[0]
        self.assertEqual(omission['troncon'], 'chX')
        self.assertEqual(omission['champ'], 'longueur_m')
        self.assertIn('chX', omission['motif'])
        self.assertIn('points', omission['motif'])
        self.assertIn('longueurSaisieM', omission['motif'])

    def test_un_seul_point_ne_fait_pas_un_trace(self):
        paquet = service.troncons_du_calepinage(Calepinage(document(
            {'id': 'chY', 'cote': 'dc', 'points': [point(altitude=3.0)]})))
        self.assertIsNone(par_id(paquet)['chY']['longueur_m'])

    def test_une_saisie_negative_est_refusee_pas_redressee(self):
        paquet = service.troncons_du_calepinage(Calepinage(document(
            {'id': 'chZ', 'cote': 'ac', 'points': [],
             'longueurSaisieM': -4.0})))
        self.assertIsNone(par_id(paquet)['chZ']['longueur_m'])
        self.assertIn('négative', paquet['omissions'][0]['motif'])

    def test_document_sans_electrical_ne_publie_aucun_troncon(self):
        paquet = service.troncons_du_calepinage(Calepinage({}))
        self.assertEqual(paquet['troncons'], [])
        omission = paquet['omissions'][0]
        self.assertIsNone(omission['troncon'])
        self.assertEqual(omission['champ'], 'electrical.cheminements')
        self.assertIn('PAS de chute calculable', omission['motif'])


class DeniveleTest(SimpleTestCase):
    """Le dénivelé entre quand il est CONNU des deux côtés du segment."""

    def _longueur(self, *points):
        paquet = service.troncons_du_calepinage(Calepinage(document(
            {'id': 'ch', 'cote': 'dc', 'points': list(points)})))
        return par_id(paquet)['ch']['longueur_m']

    def test_une_descente_verticale_vaut_sa_hauteur(self):
        """Deux points confondus, 3 m d'écart d'altitude : 3 m de câble."""
        self.assertAlmostEqual(
            self._longueur(point(altitude=6.0), point(altitude=3.0)),
            3.0, places=2)

    def test_altitude_absente_compte_le_segment_a_plat(self):
        """« altitudeM absente » ne vaut PAS « au sol » (CALX202)."""
        self.assertAlmostEqual(
            self._longueur(point(altitude=6.0), point()), 0.0, places=2)
        self.assertAlmostEqual(
            self._longueur(point(altitude=6.0), point(altitude=None)),
            0.0, places=2)

    def test_la_polyligne_est_additive(self):
        a = point(lng=LNG, altitude=0.0)
        b = point(lng=LNG + 0.0005, altitude=0.0)
        c = point(lng=LNG + 0.0005, lat=LAT + 0.0005, altitude=0.0)
        self.assertAlmostEqual(
            self._longueur(a, b, c),
            round(self._longueur(a, b) + self._longueur(b, c), 2), places=2)

    def test_la_mesure_est_en_metres(self):
        """Un millième de degré de latitude ≈ 110 m — l'ordre de grandeur
        vérifie que la longueur publiée est bien métrique."""
        mesure = self._longueur(point(lat=LAT), point(lat=LAT + 0.001))
        self.assertGreater(mesure, 100.0)
        self.assertLess(mesure, 120.0)


class DisciplineLongueurTest(SimpleTestCase):
    """La longueur porte ses COMPOSANTES et leurs origines (cables.py)."""

    def test_le_mixte_publie_ses_deux_composantes_avec_leur_origine(self):
        longueur, motif = service._longueur_du_troncon(
            {'id': 'ch3', 'points': [point(altitude=0.0),
                                     point(lng=LNG + 0.0005, altitude=0.0)],
             'longueurSaisieM': 3.2})
        self.assertIsNone(motif)
        origines = [origine for _poste, _valeur, origine
                    in longueur.composantes]
        self.assertEqual(origines, ['plan', 'saisie'])
        self.assertEqual(longueur.origine, 'mixte')

    def test_la_longueur_est_la_somme_de_ses_composantes(self):
        longueur, _motif = service._longueur_du_troncon(
            {'id': 'ch', 'points': [point(altitude=0.0),
                                    point(lng=LNG + 0.0005, altitude=0.0)],
             'longueurSaisieM': 3.2})
        self.assertAlmostEqual(
            longueur.valeur_m,
            sum(v for _p, v, _o in longueur.composantes), places=6)
