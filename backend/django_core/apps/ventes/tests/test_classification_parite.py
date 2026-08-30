"""QJR91 (M4, audit L3 du 29/08/2026) — PARITÉ DES CLASSIFIEURS : PDF vs ÉCRAN.

CE QUE CE FICHIER PROTÈGE, ET POURQUOI IL EXISTE.

``apps/ventes/quote_engine/builder.py`` et
``frontend/src/features/ventes/solar.js`` classifient CHACUN de leur côté la
MÊME désignation de ligne de devis, sans jamais lire une table commune. Le
commentaire de ``builder.py:258-261`` PRÉTEND être le « miroir de solar.js » —
et c'est FAUX depuis le 19/08 : exactement le mode d'échec qu'un commentaire ne
peut jamais prévenir et qu'une fixture partagée prévient toujours. La fixture
QJR2 (``apps/ventes/contract_samples/classification_lignes.json``) est cette
table commune ; ce fichier en est la moitié PDF, son jumeau JavaScript
(``frontend/src/features/ventes/classifieurs.parite.test.mjs``) la moitié
écran. Mêmes entrées, mêmes valeurs attendues, un seul fichier source de
vérité.

ÉTAT ATTENDU AUJOURD'HUI (QJR91 pose la garde, QJR92 met au vert) :

* ROUGE ici — cas « Batterie Deye BOS-B-Pack », capacité batterie.
  ``builder.py:263 BATTERY_DEFAULT_KWH = 5.0``, appliqué ``builder.py:290``,
  fait contribuer 5,0 kWh à une ligne dont la désignation ne porte AUCUN kWh
  lisible : un nombre FABRIQUÉ, publié sur un PDF client. L'ÉCRAN a raison
  (règle BAT5DEF du 26/08 : contribuer 0, faire remonter l'inconnu) — c'est la
  règle fondateur absolue « zéro chiffre inventé ». QJR92b retire ce défaut
  ici ET dans ``public_views.py:1862-1886`` (même défaut, page publique).
* VERT ici — cas « Module PV 550 W » : ``_is_panel`` le classe correctement
  panneau. C'est l'ÉCRAN qui est rouge sur ce cas (``solar.js:947 isPanel`` ne
  teste que le mot « panneau », et le devis est refusé à l'enregistrement comme
  n'ayant aucun panneau) — QJR92a y élargit ``isPanel``.

Aucune de ces deux corrections n'est dans ce commit : QJR91 CONSTATE, QJR92
corrige.
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.quote_engine.builder import (
    _battery_kwh_from_items,
    _is_battery,
    _is_hybrid_inverter,
    _is_inverter,
    _is_panel,
    _is_reseau_inverter,
    _parse_kwh,
)

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'classification_lignes.json')

# Les six colonnes que les DEUX moitiés doivent reproduire à l'identique
# (``notes.colonnes`` de la fixture).
COLONNES = (
    'designation', 'panneau', 'batterie',
    'onduleur_hybride', 'onduleur_reseau', 'kwh_lisible',
)


def _cas():
    with CONTRAT.open(encoding='utf-8') as fh:
        return json.load(fh).get('exemple', {}).get('cas', [])


def _etiquette(cas):
    """Nomme le cas dans la sortie de test, divergence QJR92 comprise."""
    div = cas.get('divergence_actuelle')
    if not div:
        return cas['designation']
    return '{} [DIVERGENCE {} — ROUGE ATTENDU jusqu\'à QJR92]'.format(
        cas['designation'], div.get('champ'))


class ClassificationPariteFixtureTest(SimpleTestCase):
    """La fixture partagée est lisible et porte ses six colonnes."""

    def test_fixture_lisible_et_complete(self):
        cas = _cas()
        self.assertTrue(cas, 'classification_lignes.json ne porte aucun cas')
        for c in cas:
            for col in COLONNES:
                self.assertIn(
                    col, c,
                    "le cas « {} » ne porte pas la colonne {}".format(
                        c.get('designation'), col))


class ClassificationPariteBackendTest(SimpleTestCase):
    """Les classifieurs de ``builder.py`` sur CHAQUE cas de la fixture QJR2.

    Un ``subTest`` par (cas, colonne) : un cas rouge nomme EXACTEMENT la
    colonne qui diverge, et les autres colonnes du même cas continuent d'être
    vérifiées.
    """

    def test_colonnes_de_classification(self):
        for c in _cas():
            d = c['designation']
            nom = _etiquette(c)

            with self.subTest(cas=nom, colonne='panneau'):
                self.assertEqual(
                    _is_panel(d), c['panneau'],
                    "_is_panel(« {} ») attendu {} (contrat QJR2)".format(
                        d, c['panneau']))

            with self.subTest(cas=nom, colonne='batterie'):
                self.assertEqual(
                    _is_battery(d), c['batterie'],
                    "_is_battery(« {} ») attendu {} (contrat QJR2)".format(
                        d, c['batterie']))

            with self.subTest(cas=nom, colonne='onduleur_hybride'):
                self.assertEqual(
                    _is_hybrid_inverter(d), c['onduleur_hybride'],
                    "_is_hybrid_inverter(« {} ») attendu {} (contrat QJR2)"
                    .format(d, c['onduleur_hybride']))

            with self.subTest(cas=nom, colonne='onduleur_reseau'):
                self.assertEqual(
                    _is_reseau_inverter(d), c['onduleur_reseau'],
                    "_is_reseau_inverter(« {} ») attendu {} (contrat QJR2)"
                    .format(d, c['onduleur_reseau']))

            with self.subTest(cas=nom, colonne='kwh_lisible'):
                self.assertEqual(
                    _parse_kwh(d), c['kwh_lisible'],
                    "_parse_kwh(« {} ») attendu {} (contrat QJR2)".format(
                        d, c['kwh_lisible']))

            # Sens UNIQUE, jamais l'inverse : un onduleur classé hybride ou
            # réseau est forcément un onduleur. La réciproque est fausse par
            # construction (un micro-onduleur est ``_is_inverter`` sans être ni
            # l'un ni l'autre) — ne jamais l'affirmer ici, la fixture ne porte
            # pas ce cas.
            if c['onduleur_hybride'] or c['onduleur_reseau']:
                with self.subTest(cas=nom, colonne='_is_inverter'):
                    self.assertTrue(
                        _is_inverter(d),
                        "_is_inverter(« {} ») doit être vrai pour un onduleur "
                        "classé".format(d))


class BatterieCapaciteParitesTest(SimpleTestCase):
    """``_battery_kwh_from_items`` — la capacité totale, ligne par ligne.

    BAT5DEF (26/08/2026, règle fondateur « zéro chiffre inventé ») : une ligne
    batterie sans kWh lisible contribue 0, JAMAIS un défaut fabriqué. C'est le
    comportement de ``solar.js batteryKwhFromLines`` que ce moteur doit adopter
    (QJR92b retire ``BATTERY_DEFAULT_KWH``).
    """

    def test_capacite_ligne_par_ligne(self):
        for c in _cas():
            if not c['batterie']:
                continue
            attendu = c['kwh_lisible'] or 0
            with self.subTest(cas=_etiquette(c)):
                total = _battery_kwh_from_items(
                    [{'designation': c['designation'], 'quantite': 1}])
                self.assertAlmostEqual(
                    total, attendu, places=6,
                    msg="attendu {} kWh (contrat QJR2), obtenu {}".format(
                        attendu, total))

    def test_capacite_totale_aucune_ligne_n_invente_de_kwh(self):
        cas = _cas()
        lignes = [{'designation': c['designation'], 'quantite': 1}
                  for c in cas]
        attendu = sum((c['kwh_lisible'] or 0) for c in cas if c['batterie'])
        total = _battery_kwh_from_items(lignes)
        self.assertAlmostEqual(
            total, attendu, places=6,
            msg="capacité totale attendue {} kWh (somme des kWh RÉELLEMENT "
                "lisibles), obtenu {}".format(attendu, total))
