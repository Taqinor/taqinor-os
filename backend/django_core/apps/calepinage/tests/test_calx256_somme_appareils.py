"""CALX256 — la méthode « somme d'appareils », avec la provenance de chacun.

Ce qui est prouvé ici :

* deux appareils de 3 kWh/j sur des créneaux DISJOINTS ⇒ 6 kWh par jour et
  aucune heure où les deux se recouvrent ;
* un appareil sans ``provenance`` est refusé en NOMMANT
  ``appareils[0].provenance`` ; un appareil de la table de l'atelier est
  publié ``source: 'table_atelier'`` avec la mention « non mesurée » ;
* frontière d'Aurora : avec un total annuel SAISI, la courbe garde ce total
  quels que soient les appareils (ils ne donnent que la répartition), et
  l'écart somme-des-appareils ↔ total saisi est PUBLIÉ (deux nombres + %) ;
* propriété : retirer un appareil rend EXACTEMENT la courbe d'avant (au kWh
  près), et l'entrée n'est jamais modifiée.

Fonction PURE : aucune base de données.
"""
from __future__ import annotations

import copy
import random
import unittest

from apps.calepinage.services.consommation import (
    ProfilInvalide, courbe_appareils,
)
from apps.calepinage.services.pompage import JOURS_PAR_MOIS


def appareil(kwh, debut, fin, *, provenance='saisi', **autres):
    return {'kind': autres.get('kind', 'autre'),
            'label': autres.get('label', 'Appareil'),
            'dailyKwh': kwh, 'startHour': debut, 'endHour': fin,
            'billing': 'inBill', 'provenance': provenance}


class SommeDesAppareilsTest(unittest.TestCase):

    def test_deux_appareils_disjoints_font_6_kwh_sans_recouvrement(self):
        resultat = courbe_appareils([appareil(3, 8, 11),
                                     appareil(3, 18, 21)])
        courbe = resultat['courbe']
        self.assertEqual(len(courbe), 24)
        self.assertAlmostEqual(resultat['total_journalier_kwh'], 6.0,
                               places=6)
        self.assertAlmostEqual(resultat['total_appareils_kwh_jour'], 6.0)
        premier, second = (set(a['creneau']) for a in resultat['appareils'])
        self.assertEqual(premier & second, set())
        for heure in range(24):
            attendu = 1.0 if heure in premier | second else 0.0
            self.assertAlmostEqual(courbe[heure], attendu, places=6)

    def test_un_creneau_traverse_minuit(self):
        resultat = courbe_appareils([appareil(8, 22, 6)])
        self.assertEqual(resultat['appareils'][0]['creneau'],
                         [22, 23, 0, 1, 2, 3, 4, 5])
        self.assertAlmostEqual(resultat['courbe'][23], 1.0)
        self.assertAlmostEqual(resultat['courbe'][6], 0.0)

    def test_debut_egal_fin_couvre_la_journee(self):
        resultat = courbe_appareils([appareil(2.4, 0, 24)])
        self.assertEqual(len(resultat['appareils'][0]['creneau']), 24)
        self.assertAlmostEqual(resultat['courbe'][12], 0.1)

    def test_sans_appareil_aucune_courbe_inventee(self):
        resultat = courbe_appareils([])
        self.assertIsNone(resultat['courbe'])
        self.assertTrue(resultat['avertissements'])


class ProvenanceTest(unittest.TestCase):

    def test_appareil_sans_provenance_refuse_en_la_nommant(self):
        sans = appareil(3, 8, 11)
        del sans['provenance']
        with self.assertRaises(ProfilInvalide) as capture:
            courbe_appareils([sans])
        self.assertEqual(capture.exception.champ, 'appareils[0].provenance')
        self.assertIn('appareils[0].provenance', str(capture.exception))

    def test_provenance_inconnue_refusee_en_la_nommant(self):
        with self.assertRaises(ProfilInvalide) as capture:
            courbe_appareils([appareil(3, 8, 11),
                              appareil(1, 9, 10, provenance='releve')])
        self.assertEqual(capture.exception.champ, 'appareils[1].provenance')

    def test_valeur_de_la_table_publiee_comme_valeur_type(self):
        resultat = courbe_appareils(
            [appareil(1.2, 18, 23, provenance='table_atelier')])
        publie = resultat['appareils'][0]
        self.assertEqual(publie['source'], 'table_atelier')
        self.assertEqual(publie['mention'],
                         "valeur type de l'atelier, non mesurée")
        self.assertTrue(any('non mesurée' in avis
                            for avis in resultat['avertissements']))

    def test_energie_ou_heure_illisible_refusee_en_la_nommant(self):
        cas = (
            (appareil(-1, 8, 11), 'appareils[0].dailyKwh'),
            (appareil('beaucoup', 8, 11), 'appareils[0].dailyKwh'),
            (appareil(1, 24, 11), 'appareils[0].startHour'),
            (appareil(1, 8, 25), 'appareils[0].endHour'),
            (appareil(1, 8.5, 11), 'appareils[0].startHour'),
        )
        for entree, champ in cas:
            with self.assertRaises(ProfilInvalide) as capture:
                courbe_appareils([entree])
            self.assertEqual(capture.exception.champ, champ)


class TotalSaisiTest(unittest.TestCase):

    JOURS = sum(JOURS_PAR_MOIS)

    def test_la_courbe_garde_le_total_saisi(self):
        total_annuel = 3650.0          # 10 kWh/j
        seul = courbe_appareils([appareil(3, 8, 11)],
                                total_annuel_kwh=total_annuel)
        deux = courbe_appareils([appareil(3, 8, 11), appareil(3, 18, 21)],
                                total_annuel_kwh=total_annuel)
        for resultat in (seul, deux):
            self.assertAlmostEqual(resultat['total_journalier_kwh'],
                                   total_annuel / self.JOURS, places=3)

    def test_lecart_est_publie_avec_les_deux_nombres(self):
        resultat = courbe_appareils(
            [appareil(3, 8, 11), appareil(3, 18, 21)],
            total_annuel_kwh=3650.0)
        norm = resultat['normalisation']
        self.assertEqual(norm['total_annuel_saisi_kwh'], 3650.0)
        self.assertAlmostEqual(norm['total_appareils_annuel_kwh'],
                               6 * self.JOURS)
        self.assertEqual(norm['ecart_pct'],
                         round((6 * self.JOURS - 3650) / 3650 * 100, 1))
        self.assertTrue(any("s'écarte" in avis and '%' in avis
                            for avis in resultat['avertissements']))

    def test_sans_total_saisi_aucune_normalisation(self):
        resultat = courbe_appareils([appareil(3, 8, 11)])
        self.assertIsNone(resultat['normalisation'])

    def test_total_saisi_illisible_refuse_en_le_nommant(self):
        with self.assertRaises(ProfilInvalide) as capture:
            courbe_appareils([appareil(3, 8, 11)], total_annuel_kwh=-5)
        self.assertEqual(capture.exception.champ, 'total_annuel_kwh')


class RetraitProprieteTest(unittest.TestCase):
    """Propriété : retirer un appareil rend EXACTEMENT la courbe d'avant."""

    def _liste(self, alea, taille):
        return [appareil(round(alea.uniform(0, 5), 3), alea.randrange(24),
                         alea.randrange(25),
                         provenance=alea.choice(('saisi', 'table_atelier')))
                for _ in range(taille)]

    def test_ajouter_puis_retirer_rend_la_courbe_davant(self):
        alea = random.Random(256)
        for _ in range(200):
            base = self._liste(alea, alea.randrange(1, 6))
            nouveau = self._liste(alea, 1)[0]
            total = alea.choice((None, round(alea.uniform(500, 9000), 1)))
            gele = copy.deepcopy(base)
            avant = courbe_appareils(base, total_annuel_kwh=total)
            courbe_appareils(base + [nouveau], total_annuel_kwh=total)
            apres = courbe_appareils(
                [a for a in base + [nouveau] if a is not nouveau],
                total_annuel_kwh=total)
            self.assertEqual(apres['courbe'], avant['courbe'])
            self.assertEqual(base, gele)          # l'entrée n'est pas touchée

    def test_sans_total_lapport_dun_appareil_se_retire_au_kwh_pres(self):
        alea = random.Random(2560)
        for _ in range(200):
            base = self._liste(alea, alea.randrange(1, 6))
            nouveau = self._liste(alea, 1)[0]
            avant = courbe_appareils(base)['courbe']
            avec = courbe_appareils(base + [nouveau])['courbe']
            seul = courbe_appareils([nouveau])['courbe']
            for heure in range(24):
                self.assertAlmostEqual(avec[heure] - seul[heure],
                                       avant[heure], delta=1e-3)


if __name__ == '__main__':
    unittest.main()
