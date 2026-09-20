"""CAL98 — l'ombrage remonte à la chaîne, avec l'écart CHIFFRÉ ou le silence.

Ce qui est tenu :

* une chaîne contenant le module le plus ombré est SIGNALÉE, avec l'écart
  chiffré ;
* accès solaire absent du document ⇒ AUCUN signalement inventé (silence
  explicite) ;
* aucun kWh n'est calculé ici.

Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.ombrage_chaines import (
    MOTIF_SANS_ACCES, acces_par_module, ombrage_des_chaines,
)


def layout(valeurs, *, label='PAN-SUD'):
    """Un document à UN pan portant ``solarAccess.values`` (schéma v2)."""
    return {'zones': [{
        'id': 'z1', 'label': label,
        'geometry': {
            'count': len(valeurs), 'kwc': 0.36 * len(valeurs),
            'azimuthDeg': 180.0, 'tiltDeg': 15.0,
            'panels': [{'cx': 1.2 * rang, 'cy': 0.0}
                       for rang in range(len(valeurs))],
            'solarAccess': {
                'values': list(valeurs),
                'method': "tracé d'ombres du client (CAL248)",
                'computedAt': '2026-09-20T10:00:00Z',
            },
        },
    }]}


def affectation(repartition, *, pan='PAN-SUD'):
    """``{chaine: [rangs]}`` → la table de CAL125, dans son ordre."""
    lignes = []
    for chaine, rangs in repartition.items():
        for rang in rangs:
            lignes.append({'module': f'{pan}#{rang}', 'pan': pan,
                           'chaine': chaine, 'onduleur': 1, 'mppt': 1})
    return lignes


class LectureDuDocumentTest(unittest.TestCase):

    def test_les_valeurs_sont_lues_par_label_ET_par_id(self):
        lu = acces_par_module(layout([1.0, 0.5]))
        self.assertEqual(lu['PAN-SUD'], [1.0, 0.5])
        self.assertEqual(lu['z1'], [1.0, 0.5])

    def test_un_null_du_document_reste_un_trou(self):
        lu = acces_par_module(layout([1.0, None, 0.4]))
        self.assertEqual(lu['PAN-SUD'], [1.0, None, 0.4])


class SignalementTest(unittest.TestCase):

    def test_la_chaine_du_module_le_plus_ombre_est_signalee_avec_l_ecart(self):
        resultat = ombrage_des_chaines(
            layout([1.0, 0.98, 0.97, 0.55]),
            affectation({1: [1, 2], 2: [3, 4]}))
        self.assertTrue(resultat['mesure'])
        self.assertEqual(len(resultat['signalements']), 1)
        signal = resultat['signalements'][0]
        self.assertEqual(signal['chaine'], 2)
        self.assertEqual(signal['module'], 'PAN-SUD#4')
        self.assertEqual(signal['acces'], 0.55)
        # L'écart est CHIFFRÉ, relatif au module le mieux exposé du toit.
        self.assertAlmostEqual(signal['ecart'], 0.45, places=4)
        self.assertIn('55.0', signal['raison'])

    def test_chaque_chaine_publie_ses_modules_et_ses_extremes(self):
        resultat = ombrage_des_chaines(
            layout([1.0, 0.9, 0.8, 0.6]),
            affectation({1: [1, 2], 2: [3, 4]}))
        chaine1, chaine2 = resultat['chaines']
        self.assertEqual([m['module'] for m in chaine1['modules']],
                         ['PAN-SUD#1', 'PAN-SUD#2'])
        self.assertEqual(chaine1['acces_min'], 0.9)
        self.assertEqual(chaine2['acces_min'], 0.6)
        self.assertAlmostEqual(chaine2['ecart_interne'], 0.2, places=4)

    def test_aucun_kwh_ni_aucune_perte_n_est_publie(self):
        resultat = ombrage_des_chaines(layout([1.0, 0.5]),
                                       affectation({1: [1, 2]}))
        texte = repr(resultat)
        for interdit in ('kwh', 'kWh', 'pertes', 'p50'):
            self.assertNotIn(interdit, texte)

    def test_le_seuil_d_ecart_n_est_applique_que_s_il_est_SAISI(self):
        entree = (layout([1.0, 0.98, 0.9, 0.55]),
                  affectation({1: [1, 2], 2: [3, 4]}))
        sans_seuil = ombrage_des_chaines(*entree)
        avec_seuil = ombrage_des_chaines(*entree, ecart_signale=0.05)
        self.assertEqual(len(sans_seuil['signalements']), 1)
        # La chaîne 1 (écart interne 0,02) reste sous le seuil ; seule la
        # chaîne du pire module est signalée, et elle l'est UNE fois.
        self.assertEqual(len(avec_seuil['signalements']), 1)

    def test_un_seuil_saisi_signale_une_autre_chaine_dispersee(self):
        resultat = ombrage_des_chaines(
            layout([1.0, 0.70, 0.99, 0.60]),
            affectation({1: [1, 2], 2: [3, 4]}), ecart_signale=0.25)
        chaines_signalees = {s['chaine'] for s in resultat['signalements']}
        self.assertEqual(chaines_signalees, {1, 2})

    def test_un_module_non_cable_n_ombre_aucune_chaine(self):
        lignes = affectation({1: [1, 2]})
        lignes.append({'module': 'PAN-SUD#3', 'pan': 'PAN-SUD',
                       'chaine': None, 'onduleur': None, 'mppt': None})
        resultat = ombrage_des_chaines(layout([1.0, 0.9, 0.1]), lignes)
        modules = [m['module'] for c in resultat['chaines']
                   for m in c['modules']]
        self.assertNotIn('PAN-SUD#3', modules)
        self.assertEqual(resultat['signalements'][0]['acces'], 0.9)


class SilenceExpliciteTest(unittest.TestCase):

    def test_sans_acces_solaire_aucun_signalement_invente(self):
        sans = {'zones': [{'id': 'z1', 'label': 'PAN-SUD',
                           'geometry': {'count': 4, 'azimuthDeg': 180.0}}]}
        resultat = ombrage_des_chaines(sans, affectation({1: [1, 2]}))
        self.assertFalse(resultat['mesure'])
        self.assertEqual(resultat['signalements'], [])
        self.assertEqual(resultat['chaines'], [])
        self.assertEqual(resultat['motif'], MOTIF_SANS_ACCES)

    def test_document_absent_aucun_signalement(self):
        self.assertFalse(ombrage_des_chaines(None, [])['mesure'])
        self.assertFalse(ombrage_des_chaines({}, [])['mesure'])

    def test_un_module_sans_valeur_est_nomme_et_n_est_pas_complete(self):
        resultat = ombrage_des_chaines(
            layout([1.0, None, 0.8, 0.7]),
            affectation({1: [1, 2], 2: [3, 4]}))
        self.assertEqual(resultat['modules_sans_acces'], ['PAN-SUD#2'])
        self.assertTrue(resultat['avertissements'])
        chaine1 = resultat['chaines'][0]
        # Le module sans accès est PUBLIÉ (il ne disparaît pas) mais il
        # n'entre dans aucun extrême.
        self.assertEqual([m['acces'] for m in chaine1['modules']],
                         [1.0, None])
        self.assertEqual(chaine1['acces_min'], 1.0)

    def test_une_chaine_entierement_sans_acces_ne_signale_rien(self):
        resultat = ombrage_des_chaines(
            layout([None, None]), affectation({1: [1, 2]}))
        self.assertTrue(resultat['mesure'])
        self.assertEqual(resultat['signalements'], [])
        self.assertIsNone(resultat['chaines'][0]['acces_min'])

    def test_un_document_plus_court_que_le_pan_ne_complete_rien(self):
        resultat = ombrage_des_chaines(
            layout([1.0, 0.9]), affectation({1: [1, 2], 2: [3, 4]}))
        self.assertEqual(resultat['modules_sans_acces'],
                         ['PAN-SUD#3', 'PAN-SUD#4'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
