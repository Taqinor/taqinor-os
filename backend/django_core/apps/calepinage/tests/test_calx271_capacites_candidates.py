"""CALX271 — des capacités candidates, classées par la motivation, SANS PRIX.

Ce qui est tenu ici (le « Done » de la tâche) :

* trois capacités croissantes en motivation ``autoconso`` ⇒ indicateur
  monotone NON DÉCROISSANT (test de propriété, sur plusieurs séries) ;
* une liste de capacités vide ⇒ refus nommant ``capacites_kwh`` ;
* le résultat ne contient AUCUNE clé dont le nom contient ``prix``, ``cout``
  ou ``marge`` — et la garde ``test_aucun_prix_achat`` (``cles_interdites``)
  est étendue au service ;
* contrat partagé ``contract_samples/calepinage_simulation.json`` : le bloc
  ``batterie.capacites_candidates`` a la forme que le service rend (le test
  frontend ``PanneauBatterie.test.jsx`` importe le même fichier).

Plus : une liste ORDONNÉE avec son critère écrit en toutes lettres, jamais une
recommandation unique ; une candidate sans rendement est ÉCARTÉE (jamais
simulée à 100 %) ; le bloc de la chaîne est présent même quand le dispatch est
omis.

Tests PURS : aucune base, aucun réseau. Séries SYNTHÉTIQUES.
"""
from __future__ import annotations

import json
import pathlib
import random
import unittest

from django.test import SimpleTestCase

from apps.calepinage.services.batterie import (
    MOTIVATIONS, StrategieInvalide, candidates_omises, capacites_candidates,
)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_simulation.json').read_text(encoding='utf-8'))

CONSO = [1.0] * 24
PROD = [0.0] * 7 + [3.0] * 10 + [0.0] * 7
COMMUNS = dict(puissance_charge_kw=5.0, puissance_decharge_kw=5.0,
               rendement_ar_pct=90.0)

MOTS_INTERDITS = ('prix', 'cout', 'marge')


def cles(objet, chemin=''):
    """Toutes les clés d'une structure JSON, avec leur chemin."""
    trouvees = []
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            trouvees.append((f'{chemin}.{cle}', str(cle).lower()))
            trouvees.extend(cles(valeur, f'{chemin}.{cle}'))
    elif isinstance(objet, (list, tuple)):
        for rang, valeur in enumerate(objet):
            trouvees.extend(cles(valeur, f'{chemin}[{rang}]'))
    return trouvees


def forme(objet):
    if isinstance(objet, dict):
        return {cle: forme(valeur) for cle, valeur in objet.items()}
    if isinstance(objet, list):
        return [forme(objet[0])] if objet else []
    return None


def serie_synthetique(graine, jours=3):
    """Une série FABRIQUÉE, reproductible : charge et soleil variables."""
    tirage = random.Random(graine)
    conso, prod = [], []
    for _jour in range(jours):
        crete = tirage.uniform(2.0, 6.0)
        for heure in range(24):
            conso.append(round(tirage.uniform(0.3, 2.5), 3))
            soleil = max(0.0, 1.0 - abs(heure - 13) / 6.0)
            prod.append(round(crete * soleil, 3))
    return conso, prod


class ProprieteMonotoneTest(unittest.TestCase):
    """« Trois capacités croissantes ⇒ indicateur non décroissant »."""

    def test_autoconso_monotone_sur_plusieurs_series(self):
        for graine in range(12):
            conso, prod = serie_synthetique(graine)
            for triplet in ((2.0, 5.0, 10.0), (1.0, 1.5, 3.0),
                            (4.0, 8.0, 30.0)):
                with self.subTest(graine=graine, triplet=triplet):
                    resultat = capacites_candidates(
                        conso, prod, motivation='autoconso',
                        capacites_kwh=list(triplet), **COMMUNS)
                    par_capacite = {
                        ligne['capacite_utile_kwh']: ligne['valeur']
                        for ligne in resultat['candidates']}
                    valeurs = [par_capacite[c] for c in triplet]
                    self.assertTrue(all(v is not None for v in valeurs))
                    for avant, apres in zip(valeurs, valeurs[1:]):
                        self.assertLessEqual(avant, apres + 1e-9, valeurs)

    def test_la_liste_est_ordonnee_par_le_critere(self):
        resultat = capacites_candidates(
            CONSO, PROD, motivation='autoconso',
            capacites_kwh=[2.0, 10.0, 5.0], **COMMUNS)
        valeurs = [ligne['valeur'] for ligne in resultat['candidates']]
        self.assertEqual(valeurs, sorted(valeurs, reverse=True))
        self.assertEqual([ligne['rang'] for ligne in resultat['candidates']],
                         [1, 2, 3])

    def test_la_couverture_est_monotone_aussi(self):
        conso, prod = serie_synthetique(99)
        resultat = capacites_candidates(
            conso, prod, motivation='couverture',
            capacites_kwh=[1.0, 4.0, 12.0], **COMMUNS)
        par_capacite = {ligne['capacite_utile_kwh']: ligne['valeur']
                        for ligne in resultat['candidates']}
        self.assertLessEqual(par_capacite[1.0], par_capacite[4.0] + 1e-9)
        self.assertLessEqual(par_capacite[4.0], par_capacite[12.0] + 1e-9)


class CritereNommeTest(unittest.TestCase):

    def test_le_critere_est_ecrit_en_toutes_lettres(self):
        for motivation in ('autoconso', 'couverture'):
            with self.subTest(motivation=motivation):
                resultat = capacites_candidates(
                    CONSO, PROD, motivation=motivation,
                    capacites_kwh=[5.0], **COMMUNS)
                self.assertGreater(len(resultat['critere']), 40)
                self.assertEqual(resultat['indicateur'],
                                 MOTIVATIONS[motivation]['indicateur'])

    def test_aucune_recommandation_unique(self):
        resultat = capacites_candidates(
            CONSO, PROD, motivation='autoconso', capacites_kwh=[5.0, 10.0],
            **COMMUNS)
        for chemin, cle in cles(resultat):
            self.assertNotIn('recommand', cle, chemin)
        self.assertEqual(len(resultat['candidates']), 2)

    def test_la_pointe_classe_de_la_plus_basse_a_la_plus_haute(self):
        conso = [8.0] * 6
        prod = [0.0] * 6
        resultat = capacites_candidates(
            conso, prod, motivation='pointe', capacites_kwh=[2.0, 20.0, 6.0],
            seuil_effacement_kw=5.0, **COMMUNS)
        valeurs = [ligne['valeur'] for ligne in resultat['candidates']]
        self.assertEqual(valeurs, sorted(valeurs))
        self.assertIn('5 kW', resultat['critere'])

    def test_la_pointe_sans_seuil_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            capacites_candidates(CONSO, PROD, motivation='pointe',
                                 capacites_kwh=[5.0], **COMMUNS)
        self.assertEqual(refus.exception.champ, 'seuil_effacement_kw')


class RefusTest(unittest.TestCase):

    def test_une_liste_vide_est_refusee_en_nommant_le_champ(self):
        with self.assertRaises(StrategieInvalide) as refus:
            capacites_candidates(CONSO, PROD, motivation='autoconso',
                                 capacites_kwh=[], **COMMUNS)
        self.assertEqual(refus.exception.champ, 'capacites_kwh')

    def test_une_motivation_inconnue_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            capacites_candidates(CONSO, PROD, motivation='prestige',
                                 capacites_kwh=[5.0], **COMMUNS)
        self.assertEqual(refus.exception.champ, 'motivation')

    def test_une_capacite_illisible_est_nommee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            capacites_candidates(CONSO, PROD, motivation='autoconso',
                                 capacites_kwh=[5.0, 'beaucoup'], **COMMUNS)
        self.assertEqual(refus.exception.champ, 'capacites_kwh[1]')

    def test_une_candidate_sans_rendement_est_ecartee_jamais_parfaite(self):
        resultat = capacites_candidates(
            CONSO, PROD, motivation='autoconso', capacites_kwh=[
                {'libelle': 'FICHE-MUETTE', 'capacite_utile_kwh': 10.0,
                 'puissance_charge_kw': 5.0, 'puissance_decharge_kw': 5.0,
                 'rendement_ar_pct': {'valeur': None, 'source': None}},
                {'libelle': 'FICHE-COMPLETE', 'capacite_utile_kwh': 5.0,
                 'puissance_charge_kw': 5.0, 'puissance_decharge_kw': 5.0,
                 'rendement_ar_pct': {'valeur': 90.0, 'source': 'fiche'}},
            ])
        dernier = resultat['candidates'][-1]
        self.assertEqual(dernier['libelle'], 'FICHE-MUETTE')
        self.assertIsNone(dernier['valeur'])
        self.assertIn('rendement_ar_pct', dernier['motif_absence'])
        self.assertEqual(resultat['candidates'][0]['libelle'],
                         'FICHE-COMPLETE')
        self.assertTrue(resultat['avertissements'])


class AucunPrixTest(unittest.TestCase):
    """Aucune clé de prix, de coût ni de marge — garde CAL122 ÉTENDUE."""

    def _toutes(self):
        sorties = [capacites_candidates(CONSO, PROD, motivation=m,
                                        capacites_kwh=[5.0, 10.0],
                                        seuil_effacement_kw=0.5, **COMMUNS)
                   for m in MOTIVATIONS]
        sorties.append(candidates_omises('pointe', 'motif'))
        return sorties

    def test_aucune_cle_prix_cout_ni_marge(self):
        for sortie in self._toutes():
            for chemin, cle in cles(sortie):
                for mot in MOTS_INTERDITS:
                    self.assertNotIn(mot, cle, chemin)

    def test_la_garde_cal122_est_etendue_au_service(self):
        try:
            from apps.calepinage.tests.test_aucun_prix_achat import (
                cles_interdites,
            )
        except Exception as erreur:  # noqa: BLE001 — registre Django absent
            self.skipTest(f'registre Django non chargé ici : {erreur}')
        for sortie in self._toutes():
            self.assertEqual(cles_interdites(sortie), [])


class ChaineDeSimulationTest(SimpleTestCase):
    """Le bloc ``batterie`` de la chaîne porte TOUJOURS les candidates."""

    def _stock(self):
        from apps.calepinage.tests.test_calx188_batterie import specs_de_test

        stock = []
        for produit, capacite in ((7, 5.0), (8, 10.0)):
            specs = specs_de_test(capacite=capacite)
            stock.append({
                'produit': produit, 'libelle': f'BAT-TEST-{produit}',
                'capacite_utile_kwh': specs['capacite_utile_kwh'],
                'puissance_charge_kw': specs['puissance_charge_kw'],
                'puissance_decharge_kw': specs['puissance_decharge_kw'],
                'rendement_ar_pct': specs['grandeurs']['rendement_ar_pct'],
                'source': 'fiche'})
        return stock

    def _contexte(self, *, stock, declaration=None):
        from apps.calepinage.tests.test_calx188_batterie import CONSO_KWH

        contexte = {
            'consommation': {'import_intervalle': {
                'valeurs': [CONSO_KWH] * 48,
                'origine': 'Relevé SYNTHÉTIQUE de test'}},
            'capacites_batterie_stock': stock,
        }
        if declaration is not None:
            contexte['batterie'] = declaration
        return contexte

    def test_sans_batterie_declaree_les_capacites_du_stock_sont_comparees(
            self):
        from apps.calepinage.services.etapes import batterie as bloc
        from apps.calepinage.tests.test_calx188_batterie import serie_de_test

        _suite, resultat = bloc.bloc_batterie(
            serie_de_test(heures=48), self._contexte(stock=self._stock()))
        # Le DISPATCH est omis (aucune batterie choisie)…
        self.assertIsNone(resultat['total'])
        # …mais la comparaison des capacités du stock, elle, est servie.
        candidates = resultat['capacites_candidates']
        self.assertEqual(candidates['motif_absence'], '')
        self.assertEqual(set(candidates['par_motivation']), set(MOTIVATIONS))
        autoconso = candidates['par_motivation']['autoconso']
        self.assertEqual([ligne['libelle'] for ligne in
                          autoconso['candidates']],
                         ['BAT-TEST-8', 'BAT-TEST-7'])
        # La pointe sans seuil SAISI : ses clés, et son motif nommé.
        pointe = candidates['par_motivation']['pointe']
        self.assertIn('seuil_effacement_kw', pointe['motif_absence'])
        self.assertEqual(set(pointe), set(autoconso))

    def test_la_motivation_declaree_est_republiee(self):
        from apps.calepinage.services.etapes import batterie as bloc
        from apps.calepinage.tests.test_calx188_batterie import serie_de_test

        _suite, resultat = bloc.bloc_batterie(
            serie_de_test(heures=48),
            self._contexte(stock=self._stock(), declaration={
                'motivation': 'couverture', 'seuil_effacement_kw': 0.5}))
        candidates = resultat['capacites_candidates']
        self.assertEqual(candidates['motivation_declaree'], 'couverture')
        self.assertEqual(candidates['par_motivation']['pointe'][
            'motif_absence'], '')

    def test_sans_capacite_au_stock_le_motif_est_nomme(self):
        from apps.calepinage.services.etapes import batterie as bloc
        from apps.calepinage.tests.test_calx188_batterie import serie_de_test

        _suite, resultat = bloc.bloc_batterie(
            serie_de_test(heures=48), self._contexte(stock=[]))
        candidates = resultat['capacites_candidates']
        self.assertEqual(candidates['motif_absence'],
                         bloc.MOTIF_SANS_CAPACITES_STOCK)
        self.assertEqual(candidates['capacites_stock'], [])
        self.assertIsNone(candidates['par_motivation'])

    def test_sans_societe_aucune_lecture_du_stock(self):
        from apps.calepinage.services.simulation import (
            _capacites_batterie_du_stock,
        )

        self.assertEqual(_capacites_batterie_du_stock(None), [])


class ContratPartageTest(unittest.TestCase):
    """``calepinage_simulation.json`` — ``batterie.capacites_candidates``."""

    def test_chaque_motivation_calculee_a_la_forme_du_service(self):
        bloc = CONTRAT['exemple']['batterie']['capacites_candidates']
        servi = capacites_candidates(CONSO, PROD, motivation='autoconso',
                                     capacites_kwh=[5.0, 10.0], **COMMUNS)
        self.assertEqual(forme(bloc['par_motivation']['autoconso']),
                         forme(servi))
        self.assertEqual(set(bloc['par_motivation']), set(MOTIVATIONS))

    def test_une_motivation_omise_a_la_forme_des_candidates_omises(self):
        bloc = CONTRAT['exemple']['batterie']['capacites_candidates']
        self.assertEqual(set(bloc['par_motivation']['pointe']),
                         set(candidates_omises('pointe', 'x')))
        self.assertTrue(bloc['par_motivation']['pointe']['motif_absence'])

    def test_l_etat_vide_garde_toutes_ses_cles(self):
        plein = CONTRAT['exemple']['batterie']['capacites_candidates']
        vide = CONTRAT['exemple_vide']['batterie']['capacites_candidates']
        self.assertEqual(set(plein), set(vide))
        self.assertIsNone(vide['par_motivation'])
        self.assertTrue(vide['motif_absence'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
