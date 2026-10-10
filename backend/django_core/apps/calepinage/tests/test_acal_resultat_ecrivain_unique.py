# -*- coding: utf-8 -*-
"""ACAL57 — ``Calepinage.resultat`` écrit par UN seul helper, sous verrou.

Deux instances du MÊME calepinage, lues AVANT toute écriture (le job de
simulation et la requête de l'utilisateur) : l'écriture de l'une ne doit
jamais reporter l'instantané périmé de l'autre. Base RÉELLE, aucune source
mockée — chaque écrivain de production est appelé tel quel.
"""
from __future__ import annotations

import threading

from django.db import connections
from django.test import TestCase, TransactionTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, CLE_FIL_ECARTS, enregistrer_entree, _journaliser_ecart_longueur,
)
from apps.calepinage.services.resultat import CLES_SAISIES, modifier_resultat
from apps.calepinage.services.sld import CLE_EDITION, enregistrer_edition_sld
from apps.calepinage.views.raccordement import CLE_SAISIE, _persister
from apps.crm.models import Client
from authentication.models import Company

#: Le bloc qu'une simulation pose en fin de calcul (même geste que
#: ``services/simulation.py::simuler_calepinage``).
BLOCS_SIMULATION = {'production': {'total': {'p50_kwh': 1234.0}}}

DESSIN_VIDE = {'svg': None, 'blocs': (), 'liaisons': ()}


def _simulation(calepinage):
    modifier_resultat(calepinage,
                      lambda resultat: resultat.update(BLOCS_SIMULATION))


def _ecrivains():
    """``(nom, écrire(calepinage), clé attendue)`` — les écrivains de
    ``resultat`` (ACAL325 : le rejeu du verdict n'en est plus un)."""
    return (
        ('enregistrer_entree',
         lambda c: enregistrer_entree(c, {'dc_m': 25.0}), CLE_ENTREE),
        # ACAL325 — ``rejouer_apres_layout`` n'écrit PLUS ``resultat`` (le
        # verdict est servi à la demande) : il sort de la liste des écrivains.
        ('journaliser_ecart_longueur',
         lambda c: _journaliser_ecart_longueur(c, {
             'hors_tolerance': True, 'longueur': 12,
             'longueur_dossier': 15, 'ecart': 3}), CLE_FIL_ECARTS),
        ('enregistrer_edition_sld',
         lambda c: enregistrer_edition_sld(c, {}, dessin=DESSIN_VIDE),
         CLE_EDITION),
        ('raccordement',
         lambda c: _persister(c, {'puissance_souscrite_kva': 12.0}),
         CLE_SAISIE),
        ('_fusionner', _simulation, 'production'),
    )


class _Base:

    def _creer(self):
        self.company = Company.objects.create(nom='Ecrivain Co',
                                              slug='ecrivain-co-acal57')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client A')
        return Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Écrivain',
            resultat={'pertes': [{'poste': 'soiling', 'pct': 2.0}]})

    def _deux(self, pk):
        return (Calepinage.objects.get(pk=pk),
                Calepinage.objects.get(pk=pk))


class EcrivainUnique(_Base, TestCase):

    def setUp(self):
        self.calepinage = self._creer()

    def test_simulation_tardive_conserve_la_saisie(self):
        job, requete = self._deux(self.calepinage.pk)
        enregistrer_entree(requete, {'dc_m': 25.0})
        _simulation(job)          # le job a lu AVANT la saisie
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat[CLE_ENTREE]['dc_m'], 25.0)
        self.assertIn('production', self.calepinage.resultat)
        self.assertEqual(len(self.calepinage.resultat['pertes']), 1)

    def test_saisie_tardive_conserve_la_simulation(self):
        job, requete = self._deux(self.calepinage.pk)
        _simulation(job)
        enregistrer_entree(requete, {'dc_m': 25.0})  # requête lue AVANT
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat[CLE_ENTREE]['dc_m'], 25.0)
        self.assertEqual(self.calepinage.resultat['production'],
                         BLOCS_SIMULATION['production'])

    def test_six_ecrivains(self):
        for nom, ecrire, cle in _ecrivains():
            for ordre in ('ecrivain_dabord', 'ecrivain_ensuite'):
                with self.subTest(ecrivain=nom, ordre=ordre):
                    calepinage = self._recreer()
                    premier, second = self._deux(calepinage.pk)
                    temoin = {'temoin_%s' % ordre: True}

                    def _temoin(instance, valeurs=temoin):
                        modifier_resultat(
                            instance,
                            lambda resultat: resultat.update(valeurs))

                    if ordre == 'ecrivain_dabord':
                        ecrire(premier)
                        _temoin(second)
                    else:
                        _temoin(premier)
                        ecrire(second)
                    calepinage.refresh_from_db()
                    self.assertIn(cle, calepinage.resultat)
                    self.assertIn('temoin_%s' % ordre, calepinage.resultat)
                    self.assertIn('pertes', calepinage.resultat)

    def test_un_modifier_qui_leve_n_ecrit_rien(self):
        avant = dict(self.calepinage.resultat)

        def _casse(resultat):
            resultat['partiel'] = True
            raise ValueError('refus')

        with self.assertRaises(ValueError):
            modifier_resultat(self.calepinage, _casse)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat, avant)

    def test_les_cles_saisies_sont_publiees(self):
        for cle in (CLE_ENTREE, CLE_EDITION, CLE_SAISIE):
            self.assertIn(cle, CLES_SAISIES)

    _compteur = 0

    def _recreer(self):
        EcrivainUnique._compteur += 1
        return Calepinage.objects.create(
            company=self.company, client=self.client_a,
            titre='Écrivain %d' % EcrivainUnique._compteur,
            resultat={'pertes': [{'poste': 'soiling', 'pct': 2.0}]})


class VerrouDeLigne(_Base, TransactionTestCase):
    """Deux threads, deux connexions : le second attend le verrou du premier
    et relit APRÈS sa validation — retirer ``select_for_update`` fait perdre
    l'une des deux clés."""

    def test_deux_threads_aucune_cle_perdue(self):
        calepinage = self._creer()
        lu = threading.Event()
        continuer = threading.Event()
        erreurs = []

        def _premier():
            try:
                def _lent(resultat):
                    lu.set()
                    continuer.wait(5)
                    resultat['a'] = 1
                modifier_resultat(Calepinage.objects.get(pk=calepinage.pk),
                                  _lent)
            except Exception as exc:  # noqa: BLE001 — remonté au test
                erreurs.append(exc)
            finally:
                connections.close_all()

        def _second():
            try:
                lu.wait(5)
                threading.Timer(0.5, continuer.set).start()
                modifier_resultat(
                    Calepinage.objects.get(pk=calepinage.pk),
                    lambda resultat: resultat.__setitem__('b', 2))
            except Exception as exc:  # noqa: BLE001 — remonté au test
                erreurs.append(exc)
            finally:
                connections.close_all()

        fils = [threading.Thread(target=_premier),
                threading.Thread(target=_second)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(15)
        self.assertEqual(erreurs, [])
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat.get('a'), 1)
        self.assertEqual(calepinage.resultat.get('b'), 2)
