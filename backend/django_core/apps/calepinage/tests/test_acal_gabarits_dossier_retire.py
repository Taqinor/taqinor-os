# -*- coding: utf-8 -*-
"""ACAL320 — la section JSON ``ParametresCalepinage.gabarits_dossier`` est
retirée : jumelle DORMANTE du modèle ``GabaritDossierReglementaire``.

LE CONSTAT (C-ACAL-065) : la section n'était lue par personne hors de sa
sérialisation (le seul mécanisme réel des dossiers réglementaires est le
modèle ``GabaritDossierReglementaire``, lu par ``services/reglementaire.py``)
— un réglage saisi là ne faisait RIEN. GET/PUT ``parametres/`` ne la portent
plus, un PUT qui la cite est refusé en la NOMMANT, les contrats ne la publient
plus, et la migration 0031 se rejoue à l'envers.
"""
from __future__ import annotations

import importlib
import json
import pathlib

from django.db import migrations

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.selectors import SECTIONS_PARAMETRES

from .test_api_liste import BaseApiCalepinage

URL_PARAMETRES = '/api/django/calepinage/parametres/'
ECHANTILLONS = pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
MIGRATION = importlib.import_module(
    'apps.calepinage.migrations.0031_acal320_retrait_gabarits_dossier')


def _cles(noeud):
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            yield cle
            yield from _cles(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from _cles(valeur)


class Retrait(BaseApiCalepinage):

    def test_section_absente_de_get_et_put(self):
        self.assertNotIn('gabarits_dossier', SECTIONS_PARAMETRES)
        self.assertNotIn('gabarits_dossier', ParametresCalepinage.SECTIONS)
        lecture = self.api.get(URL_PARAMETRES)
        self.assertEqual(lecture.status_code, 200, lecture.data)
        self.assertNotIn('gabarits_dossier', lecture.data)

        ecriture = self.api.put(URL_PARAMETRES, {'presets': {}},
                                format='json')
        self.assertEqual(ecriture.status_code, 200, ecriture.data)
        self.assertNotIn('gabarits_dossier', ecriture.data)

    def test_put_refuse_la_section_en_la_nommant(self):
        reponse = self.api.put(URL_PARAMETRES,
                               {'gabarits_dossier': {'dp': {}}},
                               format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('gabarits_dossier', json.dumps(reponse.data,
                                                     ensure_ascii=False))

    def test_contrats_sans_la_cle(self):
        for nom in ('parametres_calepinage.json', 'site_imagerie.json'):
            donnees = json.loads((ECHANTILLONS / nom).read_text(
                encoding='utf-8'))
            sans_pourquoi = {cle: valeur for cle, valeur in donnees.items()
                             if cle != 'pourquoi'}
            self.assertNotIn('gabarits_dossier', set(_cles(sans_pourquoi)),
                             nom)

    def test_migration_reversible(self):
        operations = MIGRATION.Migration.operations
        self.assertEqual(len(operations), 1)
        retrait = operations[0]
        self.assertIsInstance(retrait, migrations.RemoveField)
        self.assertEqual((retrait.model_name, retrait.name),
                         ('parametrescalepinage', 'gabarits_dossier'))
        self.assertTrue(retrait.reversible)
