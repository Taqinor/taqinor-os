"""CALX226 — la chute cumulée bout en bout, verdictée UNE seule fois.

CE QUE CE FICHIER GARDE
-----------------------
1. **Quatre tronçons qui tiennent CHACUN leur cible mais dont le cumul
   dépasse le maximum rendent UN bloquant**, qui nomme le cumul ET les
   tronçons contributeurs. C'est le trou que CALX226 ferme :
   ``dimensionner_cables`` compare la chute de CHAQUE câble à sa propre
   cible, donc personne ne voit la somme.
2. **La somme des chutes par tronçon ÉGALE la chute cumulée publiée.** Si
   elle ne l'égale pas, le cumul n'est pas un cumul.
3. **UN verdict par côté, jamais deux** — et jamais un verdict par tronçon.
   Chaque verdict se lit par son CODE, jamais par sa position.
4. **Aucune borne neuve.** Cible et maximum sont ceux que le noyau porte
   déjà, lus par la norme applicable, et le texte du verdict cite LEUR
   référence.
5. **Un côté dont la chute n'est pas calculable n'a pas de verdict** : un
   vert prononcé sur une absence serait le pire des faux verts.

Aucune base de données : ``SimpleTestCase`` pur.

Run :
    python manage.py test apps.calepinage.tests.test_calx226_chute_cumulee
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services import troncons as service
from apps.calepinage.services.norme import norme_applicable

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
DOCUMENT_EXEMPLE = json.loads(
    (ECHANTILLONS / 'electrique_cheminements.json').read_text(
        encoding='utf-8'))['exemple']

NORME_FR = norme_applicable({'imagerie': {'pays': 'fr'},
                             'norme_electrique': {}})
NORME_MA = norme_applicable({'imagerie': {'pays': 'ma'},
                             'norme_electrique': {}})

#: 20 A sur 100 m sous 600 V : la section retenue tient la cible DC de très
#: peu, ce qui rend chaque tronçon conforme PRIS ISOLÉMENT.
COURANT_A = 20.0
LONGUEUR_M = 100.0
TENSION_DC_V = 600.0


def chaine_dc(nombre):
    """``nombre`` tronçons DC en SÉRIE, n1 → n2 → … → n(nombre+1)."""
    return {'electrical': {'cheminements': [
        {'id': 'ch%d' % rang, 'cote': 'dc', 'de': 'n%d' % rang,
         'vers': 'n%d' % (rang + 1), 'points': [],
         'longueurSaisieM': LONGUEUR_M}
        for rang in range(1, nombre + 1)]}}


def contexte(norme=NORME_FR):
    return {'norme': norme,
            'dc': {'ib_a': COURANT_A, 'tension_v': TENSION_DC_V},
            'ac': {'ib_a': 21.7, 'tension_v': 400.0, 'phases': 3},
            'courants': {}}


def par_id(paquet):
    return {t['id']: t for t in paquet['troncons']}


def verdict(paquet, code):
    """Le verdict lu par son CODE — jamais par sa position dans la liste."""
    trouves = [v for v in paquet['verdicts'] if v['code'] == code]
    return trouves[0] if trouves else None


class CumulQuiDepasseTest(SimpleTestCase):
    """Quatre tronçons conformes un par un, non conformes ensemble."""

    def setUp(self):
        self.paquet = service._troncons_du_document(chaine_dc(4), contexte())
        self.troncons = par_id(self.paquet)
        self.cible = NORME_FR['coefficients']['chute_dc_cible_pct']['valeur']
        self.maximum = NORME_FR['coefficients']['chute_dc_max_pct']['valeur']

    def test_chaque_troncon_tient_sa_cible_pris_isolement(self):
        for rang in range(1, 5):
            chute = self.troncons['ch%d' % rang]['chute_pct']
            self.assertIsNotNone(chute)
            self.assertLessEqual(chute, self.cible,
                                 'ch%d doit tenir la cible seul' % rang)

    def test_le_cumul_depasse_le_maximum(self):
        self.assertGreater(self.paquet['totaux']['dc_chute_pct'],
                           self.maximum)

    def test_un_seul_bloquant_pour_tout_le_cote(self):
        bloquants = [v for v in self.paquet['verdicts'] if v['bloquant']]
        self.assertEqual(len(bloquants), 1, self.paquet['verdicts'])
        self.assertEqual(bloquants[0]['code'], 'chute_cumulee_dc')
        self.assertIs(bloquants[0]['conforme'], False)

    def test_le_bloquant_nomme_le_cumul_et_les_contributeurs(self):
        bloquant = verdict(self.paquet, 'chute_cumulee_dc')
        self.assertEqual(bloquant['valeur_pct'],
                         self.paquet['totaux']['dc_chute_pct'])
        self.assertEqual(bloquant['troncons'],
                         ['ch1', 'ch2', 'ch3', 'ch4'])
        for nom in ('ch1', 'ch2', 'ch3', 'ch4'):
            self.assertIn(nom, bloquant['detail'])
        # Le cumul est écrit en français dans le texte du verdict.
        cumul = self.paquet['totaux']['dc_chute_pct']
        self.assertIn(('%.2f' % cumul).replace('.', ','), bloquant['detail'])

    def test_le_verdict_cite_la_reference_du_noyau_sans_borne_neuve(self):
        bloquant = verdict(self.paquet, 'chute_cumulee_dc')
        self.assertEqual(bloquant['cible_pct'], self.cible)
        self.assertEqual(bloquant['maximum_pct'], self.maximum)
        self.assertIn(
            NORME_FR['coefficients']['chute_dc_max_pct']['reference'],
            bloquant['detail'])

    def test_la_somme_des_chutes_egale_le_cumul_publie(self):
        somme = sum(self.troncons['ch%d' % rang]['chute_pct']
                    for rang in range(1, 5))
        self.assertAlmostEqual(somme, self.paquet['totaux']['dc_chute_pct'],
                               places=2)

    def test_le_cumul_croit_le_long_de_la_chaine(self):
        cumuls = [self.troncons['ch%d' % rang]['chute_cumulee_pct']
                  for rang in range(1, 5)]
        self.assertEqual(cumuls, sorted(cumuls))
        self.assertAlmostEqual(cumuls[-1],
                               self.paquet['totaux']['dc_chute_pct'],
                               places=3)


class TroisEtatsDuVerdictTest(SimpleTestCase):
    """Sous la cible, entre cible et maximum, au-dessus du maximum."""

    def _verdict(self, nombre):
        return verdict(service._troncons_du_document(chaine_dc(nombre),
                                                     contexte()),
                       'chute_cumulee_dc')

    def test_un_seul_troncon_tient_la_cible(self):
        rendu = self._verdict(1)
        self.assertIs(rendu['conforme'], True)
        self.assertFalse(rendu['bloquant'])
        self.assertEqual(rendu['source'], 'norme')

    def test_deux_troncons_passent_la_cible_sans_bloquer(self):
        rendu = self._verdict(2)
        self.assertIs(rendu['conforme'], False)
        self.assertFalse(rendu['bloquant'],
                         'au-dessus de la cible mais sous le maximum : '
                         'une alerte, pas un bloquant')

    def test_quatre_troncons_bloquent(self):
        self.assertTrue(self._verdict(4)['bloquant'])


class UnVerdictParCoteTest(SimpleTestCase):
    """Un verdict par côté calculable — jamais deux, jamais par tronçon."""

    def test_les_deux_cotes_de_lexemple_ont_un_verdict_chacun(self):
        paquet = service._troncons_du_document(DOCUMENT_EXEMPLE, contexte())
        codes = [v['code'] for v in paquet['verdicts']]
        self.assertEqual(sorted(codes),
                         ['chute_cumulee_ac', 'chute_cumulee_dc'])
        self.assertEqual(len(codes), len(set(codes)))

    def test_aucun_verdict_sans_chute_calculable(self):
        """Norme non applicable : rien à verdicter, et surtout pas un vert."""
        paquet = service._troncons_du_document(DOCUMENT_EXEMPLE,
                                               contexte(norme=NORME_MA))
        self.assertEqual(paquet['verdicts'], [])
        self.assertIsNone(paquet['totaux']['dc_chute_pct'])
        self.assertIsNone(paquet['totaux']['ac_chute_pct'])

    def test_la_terre_ne_produit_aucun_verdict_de_chute(self):
        paquet = service._troncons_du_document(DOCUMENT_EXEMPLE, contexte())
        self.assertIsNone(par_id(paquet)['ch5']['chute_cumulee_pct'])
        for rendu in paquet['verdicts']:
            self.assertIn(rendu['cote'], ('dc', 'ac'))


class CumulNonCalculableTest(SimpleTestCase):
    """Un maillon muet rend le cumul AVAL absent, jamais partiel."""

    def test_une_chute_manquante_en_amont_coupe_le_cumul(self):
        document = chaine_dc(3)
        # ch1 perd sa longueur : sa chute n'est pas calculable.
        document['electrical']['cheminements'][0].pop('longueurSaisieM')

        paquet = service._troncons_du_document(document, contexte())
        troncons = par_id(paquet)

        self.assertIsNone(troncons['ch1']['chute_pct'])
        self.assertIsNone(troncons['ch1']['chute_cumulee_pct'])
        self.assertIsNone(troncons['ch2']['chute_cumulee_pct'],
                          'un cumul partiel se lirait comme un budget de '
                          'chute encore disponible')
        self.assertIsNone(troncons['ch3']['chute_cumulee_pct'])
        self.assertIsNone(paquet['totaux']['dc_chute_pct'])
        self.assertEqual(paquet['verdicts'], [])

    def test_le_cumul_retient_la_branche_la_plus_defavorable(self):
        """Deux branches se rejoignent : c'est la pire qui décide."""
        document = {'electrical': {'cheminements': [
            {'id': 'courte', 'cote': 'dc', 'de': 'a', 'vers': 'jonction',
             'points': [], 'longueurSaisieM': 10.0},
            {'id': 'longue', 'cote': 'dc', 'de': 'b', 'vers': 'jonction',
             'points': [], 'longueurSaisieM': LONGUEUR_M},
            {'id': 'commune', 'cote': 'dc', 'de': 'jonction', 'vers': 'ond',
             'points': [], 'longueurSaisieM': 10.0},
        ]}}

        troncons = par_id(service._troncons_du_document(document,
                                                        contexte()))

        self.assertGreater(troncons['longue']['chute_pct'],
                           troncons['courte']['chute_pct'])
        self.assertAlmostEqual(
            troncons['commune']['chute_cumulee_pct'],
            round(troncons['longue']['chute_cumulee_pct']
                  + troncons['commune']['chute_pct'], 3), places=3)

    def test_une_boucle_dans_le_trace_ne_fait_pas_tourner_le_calcul(self):
        document = {'electrical': {'cheminements': [
            {'id': 'aller', 'cote': 'dc', 'de': 'x', 'vers': 'y',
             'points': [], 'longueurSaisieM': 10.0},
            {'id': 'retour', 'cote': 'dc', 'de': 'y', 'vers': 'x',
             'points': [], 'longueurSaisieM': 10.0},
        ]}}

        troncons = par_id(service._troncons_du_document(document,
                                                        contexte()))

        for nom in ('aller', 'retour'):
            self.assertIsNotNone(troncons[nom]['chute_pct'])
            self.assertIsNone(troncons[nom]['chute_cumulee_pct'])
