"""CALX141 — le contrat de la CASCADE de pertes tient ses quatre promesses.

Ce fichier garde un DOCUMENT, pas un service : `resultat['cascade']` n'a
encore aucun producteur (il arrive avec `services/chaine_pertes.py`,
CALX147). Ce qui peut être affirmé aujourd'hui — et qui compte, puisque deux
écrans et une vingtaine de modules d'étape vont brancher dessus — c'est que
l'exemple committé se relit, qu'il est CONTINU, qu'il n'a forfaitisé aucune
étape omise, et qu'il n'a pas dérivé de `calepinage_simulation.json` (CALX4).

Le quatrième contrôle est le plus important du lot : `resultat['pertes']`
reste une LISTE PLATE (D-CALX 11). Quatre lecteurs l'itèrent déjà comme telle ;
le jour où quelqu'un « unifierait » les deux blocs, ce test le dirait ici.

Aucune base de données, aucun réseau : trois fichiers JSON et des assertions.

Run :
    python manage.py test apps.calepinage.tests.test_calx141_contrat_cascade
"""
from __future__ import annotations

import json
import pathlib
import unittest

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


CASCADE = charger('calepinage_pertes_cascade.json')
SIMULATION = charger('calepinage_simulation.json')
RESULTAT = charger('calepinage_resultat.json')

#: Les douze clés d'une étape — l'ordre n'a pas d'importance, la présence si.
CLES_ETAPE = {
    'rang', 'etape', 'libelle', 'kwh_avant', 'kwh_apres', 'perte_kwh',
    'perte_pct', 'gain', 'source', 'entree', 'reference', 'motif_omission',
}


class EnveloppeTest(unittest.TestCase):
    """L'échantillon se relit et porte l'enveloppe PACT10."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CASCADE)
        self.assertTrue(CASCADE['endpoint'].strip())
        self.assertIn('resultat/', CASCADE['endpoint'])

    def test_les_deux_etats_portent_la_meme_clef_et_les_memes_champs(self):
        for etat in ('exemple', 'exemple_vide'):
            bloc = CASCADE[etat]['cascade']
            self.assertEqual(
                sorted(bloc),
                ['etapes', 'hash_entree', 'ordre', 'postes_non_sources',
                 'total_pct'],
                f'{etat} : les clés du bloc « cascade » ont bougé.')

    def test_vide_ne_publie_jamais_un_zero(self):
        bloc = CASCADE['exemple_vide']['cascade']
        self.assertEqual(bloc['etapes'], [])
        self.assertEqual(bloc['ordre'], [])
        self.assertIsNone(bloc['total_pct'],
                          'Un calepinage jamais simulé n’a pas 0 % de perte : '
                          'il n’a PAS de cascade.')


class FormeDesEtapesTest(unittest.TestCase):
    """Chaque étape porte les douze champs, et `ordre` les nomme toutes."""

    def setUp(self):
        self.etapes = CASCADE['exemple']['cascade']['etapes']

    def test_douze_champs_par_etape(self):
        for etape in self.etapes:
            self.assertEqual(set(etape), CLES_ETAPE,
                             f"étape « {etape.get('etape')} » : champs "
                             f"{sorted(set(etape) ^ CLES_ETAPE)} en écart.")

    def test_les_rangs_suivent_l_ordre_declare(self):
        self.assertEqual([e['rang'] for e in self.etapes],
                         list(range(1, len(self.etapes) + 1)))
        self.assertEqual(CASCADE['exemple']['cascade']['ordre'],
                         [e['etape'] for e in self.etapes],
                         '`ordre` doit nommer les étapes présentes, dans '
                         'leur ordre de rang.')


class ContinuiteTest(unittest.TestCase):
    """`kwh_avant` d'une étape est le `kwh_apres` de la précédente.

    Une étape OMISE laisse la série inchangée : son `kwh_apres` vaut ``null``
    et la suivante repart du DERNIER `kwh_apres` connu. On ne remplace jamais
    un ``null`` par un chiffre pour faire tenir la chaîne.
    """

    def test_la_chaine_est_continue_sur_toute_la_liste(self):
        etapes = CASCADE['exemple']['cascade']['etapes']
        self.assertGreater(len(etapes), 1)
        dernier_connu = etapes[0]['kwh_avant']
        for precedente, etape in zip(etapes, etapes[1:]):
            self.assertEqual(
                etape['kwh_avant'], dernier_connu,
                f"étape « {etape['etape']} » (rang {etape['rang']}) : son "
                f"kwh_avant ({etape['kwh_avant']}) n'est pas l'énergie qui "
                f"sort de « {precedente['etape']} » ({dernier_connu}).")
            if etape['kwh_apres'] is not None:
                dernier_connu = etape['kwh_apres']

    def test_total_pct_est_celui_de_la_cascade_elle_meme(self):
        bloc = CASCADE['exemple']['cascade']
        etapes = bloc['etapes']
        entree = etapes[0]['kwh_avant']
        sorties = [e['kwh_apres'] for e in etapes
                   if e['kwh_apres'] is not None]
        attendu = round(100.0 * (1.0 - sorties[-1] / entree), 1)
        self.assertEqual(bloc['total_pct'], attendu,
                         '`total_pct` se déduit des deux bouts de la '
                         'cascade ; il ne recopie pas la perte passée à '
                         'PVGIS (CAL238).')

    def test_une_perte_est_positive_et_un_gain_est_signale(self):
        for etape in CASCADE['exemple']['cascade']['etapes']:
            if etape['perte_kwh'] is None:
                continue
            if etape['gain']:
                self.assertLessEqual(etape['perte_kwh'], 0.0, etape['etape'])
                self.assertLessEqual(etape['perte_pct'], 0.0, etape['etape'])
            else:
                self.assertGreaterEqual(etape['perte_kwh'], 0.0,
                                        etape['etape'])
                self.assertGreaterEqual(etape['perte_pct'], 0.0,
                                        etape['etape'])


class OmissionTest(unittest.TestCase):
    """Une étape omise se DIT — elle ne se forfaitise pas en 0 %."""

    def test_motif_present_impose_des_null_jamais_des_zeros(self):
        omises = [e for e in CASCADE['exemple']['cascade']['etapes']
                  if (e['motif_omission'] or '').strip()]
        self.assertTrue(omises, "L'exemple doit montrer au moins une étape "
                                'omise : c’est la moitié du contrat.')
        for etape in omises:
            for champ in ('kwh_apres', 'perte_kwh', 'perte_pct'):
                self.assertIsNone(
                    etape[champ],
                    f"étape « {etape['etape']} » : {champ} vaut "
                    f"{etape[champ]!r} alors que l'étape est OMISE. Un 0 se "
                    f"lirait « cette étape ne coûte rien ».")
            self.assertIsNone(etape['source'])

    def test_une_etape_calculee_n_a_aucun_motif(self):
        for etape in CASCADE['exemple']['cascade']['etapes']:
            if etape['kwh_apres'] is None:
                continue
            self.assertEqual(etape['motif_omission'], '', etape['etape'])
            self.assertIsNotNone(etape['source'],
                                 f"étape « {etape['etape']} » : une étape "
                                 'appliquée nomme la source de son entrée.')


class PasDeDeriveTest(unittest.TestCase):
    """Le bloc détaillé ici reste celui que CALX4 annonce, et `pertes` reste
    une LISTE (D-CALX 11)."""

    def test_memes_clefs_que_le_bloc_cascade_de_calx4(self):
        for etat, jumeau in (('exemple', 'exemple'),
                             ('exemple_vide', 'exemple_vide')):
            self.assertEqual(
                sorted(CASCADE[etat]['cascade']),
                sorted(SIMULATION[jumeau]['cascade']),
                f'{etat} : les clés du bloc ont divergé de '
                'calepinage_simulation.json (CALX4).')
        self.assertEqual(
            set(SIMULATION['exemple']['cascade']['etapes'][0]), CLES_ETAPE)

    def test_pertes_reste_une_liste_plate_partout(self):
        for document, nom in ((SIMULATION, 'calepinage_simulation.json'),
                              (RESULTAT, 'calepinage_resultat.json')):
            for etat in document:
                if not etat.startswith('exemple'):
                    continue
                if 'pertes' not in document[etat]:
                    continue
                self.assertIsInstance(
                    document[etat]['pertes'], list,
                    f"{nom} ({etat}) : « pertes » doit rester une LISTE "
                    'plate — quatre lecteurs l’itèrent déjà (D-CALX 11).')


if __name__ == '__main__':
    unittest.main()
