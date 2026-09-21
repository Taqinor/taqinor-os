"""CALX144 — σ est composé de composantes SOURCÉES, ou il n'existe pas.

Ce que ce fichier garde tient en deux phrases. Premièrement, aucun quantile
publié ne peut venir d'un chiffre sans origine : le repli
``DEFAULT_ANNUAL_VARIABILITY = 0.06`` de ``apps/ventes/solar_design.py`` n'a
aucune citation dans le dépôt, et il ne doit apparaître dans AUCUN état
committé de ce contrat. Deuxièmement, quand σ ne peut pas être composé, le
résultat le DIT (``motif_refus``) et laisse P75/P90/P95 nuls — jamais un P50
recopié en P90, qui se lirait « la production est certaine ».

Les quantiles de l'exemple sont vérifiés par la fonction quantile de la loi
normale (``statistics.NormalDist``) : un écran qui se calerait sur un exemple
faux serait faux avec lui.

Aucune base de données, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx144_contrat_incertitude
"""
from __future__ import annotations

import json
import math
import pathlib
import statistics
import unittest

from apps.ventes.solar_design import DEFAULT_ANNUAL_VARIABILITY

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


INCERTITUDE = charger('calepinage_incertitude.json')
SIMULATION = charger('calepinage_simulation.json')

#: Les états qui portent le bloc lui-même (le refus 400 est à part).
ETATS = ('exemple', 'exemple_sigma_refuse', 'exemple_vide')

#: Les quantiles publiés et leur probabilité de dépassement.
DEPASSEMENT = {'p75_kwh': 0.75, 'p90_kwh': 0.90, 'p95_kwh': 0.95}


def bloc(etat):
    return INCERTITUDE[etat]['incertitude']


class EnveloppeTest(unittest.TestCase):
    """L'échantillon se relit, et tous ses états portent les mêmes clés."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, INCERTITUDE)
        self.assertIn('resultat/', INCERTITUDE['endpoint'])

    def test_memes_clefs_que_le_bloc_incertitude_de_calx4(self):
        attendu = sorted(SIMULATION['exemple']['incertitude'])
        for etat in ETATS:
            self.assertEqual(sorted(bloc(etat)), attendu,
                             f'{etat} : les clés du bloc ont divergé de '
                             'calepinage_simulation.json (CALX4).')
            self.assertEqual(
                sorted(bloc(etat)['quantiles']),
                sorted(SIMULATION['exemple']['incertitude']['quantiles']),
                f'{etat}.quantiles : clés divergentes de CALX4.')

    def test_chaque_composante_porte_les_cinq_champs(self):
        attendu = set(SIMULATION['exemple']['incertitude']['composantes'][0])
        for etat in ETATS:
            for composante in bloc(etat)['composantes']:
                self.assertEqual(set(composante), attendu,
                                 f"{etat} : composante "
                                 f"« {composante.get('nom')} » en écart.")


class AucunSigmaSansSourceTest(unittest.TestCase):
    """La règle qui fait exister ce contrat."""

    def test_toute_composante_committee_est_sourcee_et_referencee(self):
        for etat in ETATS:
            for composante in bloc(etat)['composantes']:
                nom = composante['nom']
                self.assertTrue((composante['source'] or '').strip(),
                                f'{etat} : la composante « {nom} » n’a pas '
                                'de source — elle ne peut pas entrer dans σ.')
                self.assertTrue((composante['reference'] or '').strip(),
                                f'{etat} : la composante « {nom} » n’a pas '
                                'de référence.')

    def test_le_repli_non_source_n_apparait_dans_aucun_etat(self):
        for etat in ETATS:
            for composante in bloc(etat)['composantes']:
                self.assertNotEqual(
                    composante['sigma_relatif'], DEFAULT_ANNUAL_VARIABILITY,
                    f"{etat} : la composante « {composante['nom']} » publie "
                    f'la variabilité de repli ({DEFAULT_ANNUAL_VARIABILITY}) '
                    "de apps/ventes/solar_design.py, littéral sans citation "
                    'dans le dépôt. CALX184 le supprime ; ce contrat '
                    "l'interdit d'avance.")
            self.assertNotEqual(bloc(etat)['sigma_total'],
                                DEFAULT_ANNUAL_VARIABILITY, etat)

    def test_une_composante_sans_source_est_refusee_en_la_nommant(self):
        refus = INCERTITUDE['exemple_refus_composante_sans_source']
        self.assertEqual(len(refus), 1,
                         'Le refus nomme UN champ fautif, comme partout '
                         'ailleurs dans le module.')
        champ, message = next(iter(refus.items()))
        self.assertIn('source', champ,
                      'Le champ fautif désigné est bien la source manquante.')
        self.assertIn('composantes', champ)
        self.assertIn('biais_long_terme', message,
                      'Le refus doit NOMMER la composante refusée : un refus '
                      'générique laisse chercher laquelle.')


class QuadratureTest(unittest.TestCase):
    """σ total est la composition en quadrature des composantes sourcées."""

    def test_sigma_total_est_la_racine_de_la_somme_des_carres(self):
        composantes = bloc('exemple')['composantes']
        self.assertGreater(len(composantes), 1,
                           "L'exemple doit montrer au moins deux composantes "
                           ': la quadrature sur une seule ne prouve rien.')
        attendu = math.sqrt(sum(c['sigma_relatif'] ** 2 for c in composantes))
        self.assertAlmostEqual(bloc('exemple')['sigma_total'], attendu,
                               places=4)
        self.assertEqual(bloc('exemple')['methode'], 'quadrature')

    def test_les_quantiles_suivent_sigma_total(self):
        publie = bloc('exemple')['quantiles']
        sigma = bloc('exemple')['sigma_total']
        p50 = publie['p50_kwh']
        loi = statistics.NormalDist()
        for cle, depassement in DEPASSEMENT.items():
            attendu = p50 * (1.0 + loi.inv_cdf(1.0 - depassement) * sigma)
            self.assertAlmostEqual(
                publie[cle], attendu, places=1,
                msg=f'{cle} : l’exemple committé ne suit pas σ = {sigma}.')
        self.assertGreater(publie['p50_kwh'], publie['p75_kwh'])
        self.assertGreater(publie['p75_kwh'], publie['p90_kwh'])
        self.assertGreater(publie['p90_kwh'], publie['p95_kwh'])

    def test_la_portee_des_quantiles_est_declaree_annuelle(self):
        self.assertEqual(bloc('exemple')['portee'], 'annuelle',
                         'Un P90 annuel qui ne dit pas sa portée finit cité '
                         "comme une garantie sur la durée de vie de "
                         "l'installation.")


class RefusDeSigmaTest(unittest.TestCase):
    """Sans composante sourcée : des `null` et un motif, jamais un chiffre."""

    def test_aucune_composante_rend_les_quatre_quantiles_nuls(self):
        vide = bloc('exemple_vide')
        self.assertEqual(vide['composantes'], [])
        self.assertIsNone(vide['sigma_total'])
        self.assertIsNone(vide['methode'])
        for cle, valeur in vide['quantiles'].items():
            self.assertIsNone(valeur, f'quantiles.{cle}')
        self.assertTrue(vide['motif_refus'].strip(),
                        'Un σ absent se DIT ; il ne se devine pas.')

    def test_sigma_refuse_sert_p50_et_laisse_les_autres_nuls(self):
        refuse = bloc('exemple_sigma_refuse')
        self.assertEqual(refuse['composantes'], [])
        self.assertIsNone(refuse['sigma_total'])
        quantiles = refuse['quantiles']
        self.assertIsNotNone(
            quantiles['p50_kwh'],
            "P50 n'est pas déduit de σ : c'est la production simulée "
            'elle-même, elle reste servie.')
        for cle in ('p75_kwh', 'p90_kwh', 'p95_kwh'):
            self.assertIsNone(
                quantiles[cle],
                f'{cle} : un P50 recopié ici se lirait « la production est '
                'certaine ».')
        self.assertTrue(refuse['motif_refus'].strip())

    def test_un_motif_accompagne_toujours_un_sigma_absent(self):
        for etat in ETATS:
            if bloc(etat)['sigma_total'] is None:
                self.assertTrue(bloc(etat)['motif_refus'].strip(), etat)
            else:
                self.assertEqual(bloc(etat)['motif_refus'], '', etat)


if __name__ == '__main__':
    unittest.main()
