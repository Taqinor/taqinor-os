"""CALX267 — plusieurs groupes de batteries, chacun avec son couplage.

Ce qui est tenu ici (le « Done » de la tâche) :

* un groupe UNIQUE rend EXACTEMENT le résultat d'aujourd'hui : l'agrégat est,
  clé à clé, le dict de ``simuler_batterie`` ;
* deux groupes de 5 kWh utiles ⇒ décharge totale ≤ 10 kWh, et la somme des
  ``decharge_batterie_kwh`` des groupes égale celle de l'agrégat au 0,001 kWh
  près ;
* un groupe couplé DC sans onduleur est refusé en NOMMANT
  ``groupes[0].onduleur_ref`` ;
* deux modèles différents ⇒ la mention « agrégat de capacités —
  approximation » et sa raison ; un seul modèle ⇒ aucune mention ;
* le contrat partagé ``contract_samples/calepinage_batterie.json`` est le
  résultat RÉEL du service sur son entrée synthétique (le test frontend
  ``contratGroupesBatterie.test.jsx`` importe le même fichier).

Tests PURS : aucune base, aucun réseau. Séries SYNTHÉTIQUES, fabriquées pour
le test, ne décrivant aucune installation réelle.
"""
from __future__ import annotations

import json
import pathlib
import unittest

from django.test import SimpleTestCase

from apps.calepinage.services.batterie import (
    COUPLAGES, StrategieInvalide, simuler_batterie, simuler_groupes,
)

CONTRAT = (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'calepinage_batterie.json')

#: Une journée : consommation à plat, 12 h de production excédentaire
#: (2 kWh de surplus par heure) PUIS 12 h de nuit (12 kWh de déficit).
CONSO = [1.0] * 24
PROD = [3.0] * 12 + [0.0] * 12

#: Un pack de 5 kWh UTILES, grandeurs SAISIES pour le test.
PACK = dict(strategie='autoconso', capacite_utile_kwh=5.0,
            puissance_charge_kw=5.0, puissance_decharge_kw=5.0,
            rendement_ar_pct=100.0)


def groupe(nom='G1', *, couplage='ac', onduleur_ref=None, modele='PACK-X',
           **parametres):
    declaration = dict(PACK, groupe=nom, couplage=couplage,
                       onduleur_ref=onduleur_ref, modele=modele)
    declaration.update(parametres)
    return declaration


def cles(objet):
    """La FORME d'une structure JSON : ses clés, récursivement."""
    if isinstance(objet, dict):
        return {cle: cles(valeur) for cle, valeur in objet.items()}
    if isinstance(objet, list):
        return [cles(objet[0])] if objet else []
    return None


class GroupeUniqueTest(unittest.TestCase):
    """Un seul groupe : le résultat d'AUJOURD'HUI, rien de plus."""

    def test_un_groupe_unique_est_cle_a_cle_simuler_batterie(self):
        attendu = simuler_batterie(CONSO, PROD, **PACK)
        resultat = simuler_groupes(CONSO, PROD, [groupe()])

        self.assertEqual(set(resultat['agregat']), set(attendu))
        for cle, valeur in attendu.items():
            with self.subTest(cle=cle):
                self.assertEqual(resultat['agregat'][cle], valeur)
        self.assertEqual(resultat['groupes'][0]['resultat'], attendu)
        self.assertIsNone(resultat['mention_agregat'])

    def test_le_groupe_publie_son_couplage_et_son_onduleur(self):
        resultat = simuler_groupes(
            CONSO, PROD, [groupe(couplage='dc', onduleur_ref='OND-TEST-1')])
        ligne = resultat['groupes'][0]
        self.assertEqual(ligne['couplage'], 'dc')
        self.assertEqual(ligne['onduleur_ref'], 'OND-TEST-1')
        self.assertEqual(ligne['groupe'], 'G1')

    def test_les_deux_couplages_sont_nommes(self):
        self.assertEqual(COUPLAGES, ('ac', 'dc'))


class DeuxGroupesTest(unittest.TestCase):

    def setUp(self):
        self.resultat = simuler_groupes(
            CONSO, PROD, [groupe('G1'), groupe('G2')])

    def test_deux_groupes_de_5_kwh_ne_dechargent_pas_plus_de_10_kwh(self):
        self.assertLessEqual(
            self.resultat['agregat']['decharge_batterie_kwh'], 10.0 + 1e-9)

    def test_la_somme_des_groupes_egale_l_agregat(self):
        somme = sum(ligne['resultat']['decharge_batterie_kwh']
                    for ligne in self.resultat['groupes'])
        self.assertAlmostEqual(
            somme, self.resultat['agregat']['decharge_batterie_kwh'],
            delta=0.001)
        somme_charge = sum(ligne['resultat']['charge_batterie_kwh']
                           for ligne in self.resultat['groupes'])
        self.assertAlmostEqual(
            somme_charge, self.resultat['agregat']['charge_batterie_kwh'],
            delta=0.001)

    def test_chaque_groupe_est_publie_separement_dans_l_ordre(self):
        noms = [ligne['groupe'] for ligne in self.resultat['groupes']]
        self.assertEqual(noms, ['G1', 'G2'])
        # Chaque groupe a vraiment servi quelque chose (5 kWh chacun).
        for ligne in self.resultat['groupes']:
            self.assertAlmostEqual(
                ligne['resultat']['decharge_batterie_kwh'], 5.0, delta=0.001)

    def test_l_agregat_a_les_cles_de_simuler_batterie(self):
        attendu = simuler_batterie(CONSO, PROD, **PACK)
        self.assertEqual(set(self.resultat['agregat']), set(attendu))
        self.assertEqual(set(self.resultat['agregat']['parametres']),
                         set(attendu['parametres']))

    def test_l_import_est_celui_qui_reste_apres_le_dernier_groupe(self):
        # 12 h de nuit à 1 kWh, 10 kWh servis par les deux groupes.
        self.assertAlmostEqual(
            self.resultat['agregat']['import_reseau_kwh'], 2.0, delta=0.001)
        self.assertEqual(self.resultat['agregat']['import_reseau_kwh'],
                         self.resultat['groupes'][-1]['resultat'][
                             'import_reseau_kwh'])

    def test_les_capacites_s_additionnent_dans_les_parametres(self):
        self.assertEqual(
            self.resultat['agregat']['parametres']['capacite_utile_kwh'],
            10.0)


class ResiduTest(unittest.TestCase):
    """Le groupe suivant tourne sur le RÉSIDU du précédent."""

    def test_un_premier_groupe_qui_absorbe_tout_ne_laisse_rien(self):
        gros = groupe('GROS', capacite_utile_kwh=50.0,
                      puissance_charge_kw=50.0, puissance_decharge_kw=50.0)
        resultat = simuler_groupes(CONSO, PROD, [gros, groupe('PETIT')])
        second = resultat['groupes'][1]['resultat']
        # Le premier stocke tout le surplus et sert toute la nuit : le
        # second n'a ni surplus à stocker ni déficit à servir.
        self.assertEqual(second['charge_batterie_kwh'], 0.0)
        self.assertEqual(second['decharge_batterie_kwh'], 0.0)

    def test_l_etat_de_charge_agrege_est_la_somme_des_groupes(self):
        resultat = simuler_groupes(CONSO, PROD, [groupe('G1'), groupe('G2')])
        premier = resultat['groupes'][0]['resultat']['etat_de_charge_kwh']
        second = resultat['groupes'][1]['resultat']['etat_de_charge_kwh']
        for rang, etat in enumerate(
                resultat['agregat']['etat_de_charge_kwh']):
            self.assertAlmostEqual(etat, premier[rang] + second[rang],
                                   delta=1e-3)


class RefusTest(unittest.TestCase):

    def test_un_groupe_dc_sans_onduleur_est_refuse_en_nommant_le_champ(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD, [groupe(couplage='dc')])
        self.assertEqual(refus.exception.champ, 'groupes[0].onduleur_ref')
        self.assertIn('onduleur', str(refus.exception))

    def test_le_second_groupe_dc_sans_onduleur_est_nomme_au_bon_rang(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD,
                            [groupe('G1'), groupe('G2', couplage='dc')])
        self.assertEqual(refus.exception.champ, 'groupes[1].onduleur_ref')

    def test_un_couplage_non_declare_est_refuse(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD, [groupe(couplage=None)])
        self.assertEqual(refus.exception.champ, 'groupes[0].couplage')

    def test_aucun_groupe_est_refuse(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD, [])
        self.assertEqual(refus.exception.champ, 'groupes')

    def test_un_parametre_refuse_est_prefixe_du_groupe(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD, [
                groupe('G1'), groupe('G2', strategie='peak_shaving')])
        self.assertEqual(refus.exception.champ,
                         'groupes[1].seuil_effacement_kw')

    def test_une_grandeur_obligatoire_absente_est_nommee(self):
        declaration = groupe()
        declaration.pop('capacite_utile_kwh')
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD, [declaration])
        self.assertEqual(refus.exception.champ,
                         'groupes[0].capacite_utile_kwh')


class MentionAgregatTest(unittest.TestCase):

    def test_deux_modeles_differents_portent_la_mention_et_sa_raison(self):
        resultat = simuler_groupes(CONSO, PROD, [
            groupe('G1', modele='PACK-A'), groupe('G2', modele='PACK-B')])
        mention = resultat['mention_agregat']
        self.assertIn('agrégat de capacités — approximation', mention)
        self.assertIn('ne s’additionnent pas', mention)
        self.assertIn('PACK-A', mention)

    def test_un_seul_modele_ne_porte_aucune_mention(self):
        resultat = simuler_groupes(CONSO, PROD, [
            groupe('G1', modele='PACK-A'), groupe('G2', modele='PACK-A')])
        self.assertIsNone(resultat['mention_agregat'])

    def test_un_modele_non_declare_ne_se_suppose_pas_identique(self):
        resultat = simuler_groupes(CONSO, PROD, [
            groupe('G1', modele='PACK-A'), groupe('G2', modele=None)])
        self.assertIn('agrégat de capacités — approximation',
                      resultat['mention_agregat'])


class ContratPartageTest(unittest.TestCase):
    """``contract_samples/calepinage_batterie.json`` : l'exemple COMMITTÉ."""

    def setUp(self):
        self.document = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_l_exemple_committe_est_le_resultat_reel_du_service(self):
        entree = self.document['entree_synthetique']
        resultat = simuler_groupes(entree['charge_horaire'],
                                   entree['production_horaire'],
                                   entree['groupes'])
        self.assertEqual(resultat, self.document['exemple'])

    def test_la_forme_de_l_exemple_est_celle_du_service(self):
        resultat = simuler_groupes(CONSO, PROD, [
            groupe('G1', modele='PACK-A'),
            groupe('G2', couplage='dc', onduleur_ref='OND', modele='PACK-B')])
        self.assertEqual(cles(resultat), cles(self.document['exemple']))

    def test_l_exemple_est_coherent(self):
        exemple = self.document['exemple']
        somme = sum(ligne['resultat']['decharge_batterie_kwh']
                    for ligne in exemple['groupes'])
        self.assertAlmostEqual(
            somme, exemple['agregat']['decharge_batterie_kwh'], delta=0.001)
        self.assertTrue(exemple['mention_agregat'])

    def test_l_en_tete_du_contrat(self):
        self.assertTrue(self.document['endpoint'].startswith('GET /api/'))
        self.assertEqual(self.document['forme_serveur'], 'partielle')
        self.assertTrue(self.document['pourquoi'])


class ChaineDeSimulationTest(SimpleTestCase):
    """La banque du document DÉCLARE son couplage : la chaîne la fait
    passer par ``simuler_groupes`` (``etapes/batterie.py``)."""

    def _bloc(self, **declaration):
        from apps.calepinage.services.etapes import batterie as bloc
        from apps.calepinage.tests.test_calx188_batterie import (
            contexte_de_test, serie_de_test,
        )

        contexte = contexte_de_test(heures=48, **declaration)
        return bloc.bloc_batterie(serie_de_test(heures=48), contexte)

    def test_un_couplage_ac_declare_rend_le_dispatch_d_aujourd_hui(self):
        _suite, sans = self._bloc()
        _suite, avec = self._bloc(couplage='ac')
        self.assertEqual(avec['motif_absence'], '')
        self.assertEqual(avec['total'], sans['total'])

    def test_une_banque_dc_sans_onduleur_omet_le_bloc_en_le_nommant(self):
        suite, resultat = self._bloc(couplage='dc')
        self.assertIsNone(resultat['total'])
        self.assertIn('batterie.groupes[0].onduleur_ref',
                      resultat['motif_absence'])
        self.assertNotIn('batterie_soc_pct', suite['points'][0])

    def test_une_banque_dc_avec_son_onduleur_est_simulee(self):
        _suite, resultat = self._bloc(couplage='dc',
                                      onduleur_ref='OND-TEST-1')
        self.assertEqual(resultat['motif_absence'], '')
        self.assertIsNotNone(resultat['total'])


class AucunPrixTest(unittest.TestCase):

    def test_aucun_prix_ne_sort_de_ce_service(self):
        resultat = simuler_groupes(CONSO, PROD, [
            groupe('G1', modele='PACK-A'), groupe('G2', modele='PACK-B')])
        texte = json.dumps(resultat).lower()
        for interdit in ('prix', 'achat', 'marge', 'cout'):
            self.assertNotIn(interdit, texte)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
