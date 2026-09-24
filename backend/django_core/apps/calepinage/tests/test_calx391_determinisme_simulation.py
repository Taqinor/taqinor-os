"""CALX391 — le DÉTERMINISME de la simulation, entrée pour entrée.

CE QUE CE FICHIER AFFIRME
--------------------------
``docs/moteur-calepinage.md`` §1 promet que tout artefact porte
``(hash_entree, version_moteur)`` ; ``services/electrique.py`` (CALX70) ne SERT
une simulation persistée que tant que son ``hash_entree`` est celui du
document d'aujourd'hui. Les deux promesses supposent la même chose : la MÊME
entrée rend le MÊME résultat, et une entrée DIFFÉRENTE rend une empreinte
différente. Un résultat non reproductible ne se compare pas (HelioScope publie
sa reproductibilité face à un tiers :
https://help-center.helioscope.com/hc/en-us/articles/39323166747667-P90-P95-and-P99-Values-Accuracy-Study).

1. **deux exécutions de la même entrée** rendent strictement le même
   ``hash_entree``, les mêmes totaux de ``resultat['production']``, la même
   liste ``resultat['pertes']`` (ORDRE et valeurs), la même cascade (ordre
   des postes et valeurs, ``resultat['cascade']``) et la même somme de
   ``serie_horaire`` — et, au-delà, le même ``resultat`` entier ;
2. **l'ordre des clés ne compte pas** : la seconde exécution reçoit un
   document, des fiches, des réglages et des postes dont CHAQUE dictionnaire
   a ses clés dans l'ordre inverse. Un dictionnaire sérialisé dans un ordre
   non déterminé (un ``json.dumps`` sans ``sort_keys`` dans une empreinte, un
   ensemble itéré pour bâtir une liste) fait rougir ce test — le dernier cas
   le PROUVE par mutation ;
3. **la garde tient dans l'autre sens** : une entrée modifiée d'UN centimètre
   change ``hash_entree``.

LA MÉTÉO est la série figée de CALX389 (``fixtures/calx389_serie_pvgis.json``,
réponse PVGIS réelle enregistrée) : aucun réseau, et la sonde de transport
vérifie qu'aucun appel n'est tenté — un résultat qui dépendrait de la
disponibilité de PVGIS ne serait pas une fonction de son entrée.

AUCUNE HORLOGE VIVE dans une affirmation : l'instant du calcul est figé
(``MAINTENANT``) ; la seule grandeur vive, ``simulation.duree_s`` (durée
mesurée par ``time.monotonic``), est exclue NOMMÉMENT des comparaisons
(``CLES_HORLOGE``).

AUCUNE BASE : ``SimpleTestCase``, pivot factice à ``pk = None``.

Run :
    python manage.py test apps.calepinage.tests.test_calx391_determinisme_simulation -v2
"""
from __future__ import annotations

import copy
import hashlib
import json
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services import chaines, pvgis_serie, simulation
from apps.calepinage.tests.test_calx389_budget_simulation import (
    ENTREE_ELECTRIQUE, MAINTENANT, MATERIEL, POSTES_SAISIS, REGLAGES,
    CalepinageEssai, ClientFixture, document,
)

#: Les seules grandeurs VIVES du résultat, exclues nommément des
#: comparaisons : la durée mesurée du calcul change à chaque exécution.
CLES_HORLOGE = (('simulation', 'duree_s'),)

#: L'instant figé, tel que l'en-tête du résultat doit le porter.
CALCULE_LE = '2026-09-24T08:00:00Z'

#: Un centimètre, en mètres — l'unité des longueurs de liaison saisies.
UN_CENTIMETRE_M = 0.01


def inverser(valeur):
    """La MÊME valeur, chaque dictionnaire reconstruit clés à l'envers.

    Les listes gardent leur ordre (il est porteur de sens : pans, postes,
    points horaires) ; seuls les dictionnaires sont retournés, à toute
    profondeur. Deux entrées ainsi construites sont ÉGALES au sens de Python
    et du JSON — toute différence de résultat vient donc d'un ordre de
    parcours non déterminé.
    """
    if isinstance(valeur, dict):
        return {cle: inverser(valeur[cle]) for cle in reversed(list(valeur))}
    if isinstance(valeur, list):
        return [inverser(element) for element in valeur]
    if isinstance(valeur, tuple):
        return tuple(inverser(element) for element in valeur)
    return valeur


def _sonde_reseau(url, timeout_s):
    raise AssertionError('appel réseau PVGIS pendant la simulation : ' + url)


def simuler(layout, *, entree=None, pertes=None, materiel=MATERIEL,
            reglages=REGLAGES):
    """Simule et FUSIONNE (``enregistrer=True``) sur un pivot sans base.

    Rend le ``Calepinage.resultat`` tel que la simulation l'a laissé : c'est
    lui que ``GET resultat/`` sert. ``forcer=True`` : chaque exécution
    calcule vraiment. Le transport réseau par défaut du client PVGIS est
    remplacé par une sonde (tout appel serait avalé plus haut en « pas de
    donnée » — il est donc aussi COMPTÉ).
    """
    calepinage = CalepinageEssai(layout, entree=entree, pertes=pertes)
    sonde = mock.MagicMock(side_effect=_sonde_reseau)
    with mock.patch.object(pvgis_serie, '_transport_urllib', sonde):
        simulation.simuler_calepinage(
            calepinage, client=ClientFixture(), materiel=materiel,
            reglages=reglages, enregistrer=True, maintenant=MAINTENANT,
            forcer=True)
    if sonde.called:
        raise AssertionError('La simulation a tenté %d appel(s) réseau : '
                             'son résultat dépendrait de PVGIS, pas de son '
                             'entrée.' % sonde.call_count)
    return calepinage.resultat


def sans_horloge(resultat):
    """Une copie du résultat SANS ses grandeurs vives (``CLES_HORLOGE``)."""
    copie = copy.deepcopy(resultat)
    for chemin in CLES_HORLOGE:
        bloc = copie
        for cle in chemin[:-1]:
            bloc = bloc.get(cle) or {}
        bloc.pop(chemin[-1], None)
    return copie


def canonique(resultat):
    """Le résultat sérialisé à clés TRIÉES — la forme que l'on compare."""
    return json.dumps(sans_horloge(resultat), sort_keys=True,
                      ensure_ascii=False)


def ordre_de_la_cascade(resultat):
    """Les postes de la cascade, dans l'ordre publié."""
    return [etape['etape'] for etape in resultat['cascade']['etapes']]


def sommes_de_la_serie(resultat):
    """``{colonne: somme}`` de la série horaire persistée, colonne par
    colonne, dans l'ordre des points — ``None`` pour une colonne vide."""
    points = resultat['serie_horaire']['points']
    colonnes = sorted({cle for point in points for cle in point})
    sommes = {}
    for colonne in colonnes:
        valeurs = [point.get(colonne) for point in points
                   if isinstance(point.get(colonne), (int, float))
                   and not isinstance(point.get(colonne), bool)]
        sommes[colonne] = sum(valeurs) if valeurs else None
    return sommes


def ecarts(premier, second):
    """Ce qui DIFFÈRE entre deux résultats, nommé — ``[]`` s'ils sont égaux."""
    lignes = []
    if (premier['simulation']['hash_entree']
            != second['simulation']['hash_entree']):
        lignes.append('hash_entree')
    if premier['production']['total'] != second['production']['total']:
        lignes.append('production.total')
    if premier['pertes'] != second['pertes']:
        lignes.append('pertes')
    if ordre_de_la_cascade(premier) != ordre_de_la_cascade(second):
        lignes.append('cascade.ordre')
    if premier['cascade']['etapes'] != second['cascade']['etapes']:
        lignes.append('cascade.etapes')
    if sommes_de_la_serie(premier) != sommes_de_la_serie(second):
        lignes.append('serie_horaire.somme')
    if canonique(premier) != canonique(second):
        lignes.append('resultat')
    return lignes


class DeterminismeTest(SimpleTestCase):
    """La même entrée rend le même résultat — au poste près, dans l'ordre."""

    def test_deux_executions_de_la_meme_entree_sont_identiques(self):
        for nb_pans in (1, 4):
            with self.subTest(pans=nb_pans):
                premier = simuler(document(nb_pans))
                second = simuler(document(nb_pans))

                self.assertEqual(premier['simulation']['hash_entree'],
                                 second['simulation']['hash_entree'])
                self.assertEqual(premier['production']['total'],
                                 second['production']['total'])
                self.assertEqual(premier['pertes'], second['pertes'])
                self.assertEqual(ordre_de_la_cascade(premier),
                                 ordre_de_la_cascade(second))
                self.assertEqual(premier['cascade']['etapes'],
                                 second['cascade']['etapes'])
                self.assertEqual(sommes_de_la_serie(premier),
                                 sommes_de_la_serie(second))
                self.assertEqual(ecarts(premier, second), [])

    def test_le_cas_compare_des_nombres_pas_des_omissions(self):
        # Un déterminisme affirmé sur des ``None`` ne prouverait rien : la
        # production, la série et des postes CALCULÉS doivent exister.
        resultat = simuler(document(1))

        self.assertIsInstance(resultat['production']['total']['p50_kwh'],
                              float)
        self.assertIsNotNone(sommes_de_la_serie(resultat)['p_w'])
        calculees = [etape for etape in resultat['cascade']['etapes']
                     if etape['perte_pct'] is not None]
        self.assertGreaterEqual(len(calculees), 2)
        self.assertTrue(resultat['pertes'])

    def test_la_liste_des_pertes_saisies_garde_son_ordre(self):
        # D-CALX 11 : la liste plate des postes SAISIS n'est jamais réécrite
        # par la simulation — ni réordonnée, ni complétée.
        resultat = simuler(document(1))

        self.assertEqual([poste['poste'] for poste in resultat['pertes']],
                         [poste['poste'] for poste in POSTES_SAISIS])

    def test_l_ordre_des_cles_des_dictionnaires_ne_change_rien(self):
        premier = simuler(document(4))
        second = simuler(inverser(document(4)),
                         entree=inverser(ENTREE_ELECTRIQUE),
                         pertes=inverser(POSTES_SAISIS),
                         materiel=inverser(MATERIEL),
                         reglages=inverser(REGLAGES))

        self.assertEqual(ecarts(premier, second), [])

    def test_aucune_horloge_vive_n_entre_dans_le_resultat_compare(self):
        resultat = simuler(document(1))

        self.assertEqual(resultat['simulation']['calcule_le'], CALCULE_LE)
        # La durée vive existe bien — et c'est la SEULE clé retirée.
        self.assertIn('duree_s', resultat['simulation'])
        self.assertNotIn('duree_s', sans_horloge(resultat)['simulation'])
        self.assertEqual(sorted(sans_horloge(resultat)),
                         sorted(resultat))


class SensibiliteTest(SimpleTestCase):
    """La garde tient dans les DEUX sens : une entrée modifiée se voit."""

    def test_une_entree_modifiee_d_un_centimetre_change_l_empreinte(self):
        # ``dc_m`` : la longueur de liaison continue SAISIE (CAL131), une
        # entrée de la chaîne (étape ohmique DC) et de l'empreinte
        # (``services/electrique.py::_options_entree``).
        modifiee = dict(ENTREE_ELECTRIQUE,
                        dc_m=ENTREE_ELECTRIQUE['dc_m'] + UN_CENTIMETRE_M)
        self.assertAlmostEqual(
            modifiee['dc_m'] - ENTREE_ELECTRIQUE['dc_m'], UN_CENTIMETRE_M)

        avant = simuler(document(1))
        apres = simuler(document(1), entree=modifiee)

        self.assertNotEqual(avant['simulation']['hash_entree'],
                            apres['simulation']['hash_entree'])
        self.assertIn('hash_entree', ecarts(avant, apres))

    def test_une_serialisation_sans_ordre_fait_rougir_la_garde(self):
        # MUTATION : une empreinte qui sérialise le document SANS trier ses
        # clés. Deux documents égaux, écrits dans deux ordres, reçoivent
        # alors deux empreintes — exactement la régression que le test
        # d'ordre inverse doit attraper.
        def empreinte_sans_ordre(layout, **_parametres):
            brut = json.dumps(layout, ensure_ascii=False)
            return hashlib.sha256(brut.encode('utf-8')).hexdigest()

        with mock.patch.object(chaines, 'empreinte_entree',
                               empreinte_sans_ordre):
            premier = simuler(document(1))
            second = simuler(inverser(document(1)))

        self.assertIn('hash_entree', ecarts(premier, second))
