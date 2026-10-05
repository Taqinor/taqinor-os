# -*- coding: utf-8 -*-
"""ACAL10 → ACAL173 — les contrats ventes F06 posés SEULS sur main (PACT10)
portent leurs clés, et la moitié servie (``fiche_batterie``, ACAL173) rend
EXACTEMENT les clés de l'exemple.

Test-du-test : retirer une clé de ``fiche_batterie`` (ou de ``source_entree``)
dans un exemple ⇒ ``test_cles_presentes_dans_les_exemples`` échoue ; ajouter
une clé au servi sans l'écrire au contrat ⇒ idem.

La moitié servie de ``source_entree`` (conception électrique) est livrée par
ACAL165 : la clé vit désormais DANS ``exemple`` (comparé à la sortie réelle par
``test_pv41_conception_electrique``) ; ce test en garde les valeurs admises.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.public.payload_batterie import _fiche_batterie_publique

SAMPLES = Path(__file__).resolve().parents[1] / 'contract_samples'

CLES_FICHE_BATTERIE = {
    'rendement_ar_pct', 'dod_pct', 'source', 'simulation_omise_motif'}
CLES_SOURCE_ENTREE = {'temperatures', 'longueurs', 'regime'}


def _contrat(nom):
    return json.loads((SAMPLES / nom).read_text(encoding='utf-8'))


class _Fiche:
    type_fiche = 'batterie'
    bat_kwh_nominal = bat_kwh_usable = bat_v_nominal = None
    bat_max_charge_kw = None
    bat_dod_pct = Decimal('90.0')
    bat_rendement_ar_pct = Decimal('94.0')


class _Produit:
    fiche_technique = _Fiche()


class _Ligne:
    produit = _Produit()
    quantite = 1
    designation = 'Batterie Dyness 5 kWh'


class _Devis:
    class lignes:  # noqa: N801 — imite le manager ``devis.lignes``
        @staticmethod
        def all():
            return [_Ligne()]


class Contrats(SimpleTestCase):

    def test_cles_presentes_dans_les_exemples(self):
        batterie = _contrat('couverture_batterie.json')
        self.assertEqual(batterie['endpoint'],
                         'GET /api/django/public/proposal/<token>/data/')
        servi = _fiche_batterie_publique(_Devis())
        self.assertIsNotNone(servi)
        for exemple in ('exemple', 'exemple_autonomie_atteignable'):
            with self.subTest(contrat='couverture_batterie', exemple=exemple):
                fiche = batterie[exemple]['fiche_batterie']
                self.assertEqual(set(fiche), CLES_FICHE_BATTERIE)
                self.assertEqual(set(fiche), set(servi))
                self.assertIn(fiche['source'], ('fiche', None))
        # Les deux états du contrat : fiche muette ⇒ null + motif ; fiche
        # complète ⇒ rendement sourcé, pas de motif.
        muette = batterie['exemple']['fiche_batterie']
        self.assertIsNone(muette['rendement_ar_pct'])
        self.assertTrue(muette['simulation_omise_motif'])
        complete = batterie['exemple_autonomie_atteignable']['fiche_batterie']
        self.assertEqual(complete['source'], 'fiche')
        self.assertIsNone(complete['simulation_omise_motif'])

        electrique = _contrat('conception_electrique.json')
        source = electrique['exemple']['source_entree']
        self.assertEqual(set(source), CLES_SOURCE_ENTREE)
        for valeur in source.values():
            self.assertIn(valeur, ('calepinage', 'surcharge', 'defaut'))
