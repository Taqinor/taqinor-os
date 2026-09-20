"""CAL216 — import/export JSON du ``roof_layout``.

Ce qui est prouvé ici :

* un export réimporté donne le MÊME hash (round-trip) ;
* export sans document enregistré rend ``roof_layout: None`` (jamais
  ``{}``) et le numéro de version du schéma ;
* un JSON hors schéma est refusé, en NOMMANT le chemin du champ fautif ;
* un document non-objet (liste, nombre…) est refusé ;
* l'import passe par le chemin d'écriture unique : il hérite donc du
  verrou CAL207 (devis envoyé → 409) sans code dupliqué.

Run :
    python manage.py test apps.calepinage.tests.test_cal216_import_export -v2
"""
import json
from pathlib import Path

from django.test import TestCase
from rest_framework.exceptions import APIException

from apps.calepinage.models import Calepinage
from apps.calepinage.services.io_layout import (
    ImportLayoutRefuse, VERSION_SCHEMA, exporter_layout, importer_layout,
)
from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.models import Company

_SCHEMA = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'roof_layout_v2.schema.json')

with open(_SCHEMA, encoding='utf-8') as _fichier:
    _DOCUMENT_VALIDE = json.load(_fichier)['exemple']


class ExportLayoutTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='IO Layout Co',
                                              slug='io-layout-co-216')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client IO')
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a)

    def test_sans_document_rend_none_pas_un_objet_vide(self):
        resultat = exporter_layout(self.calepinage)
        self.assertIsNone(resultat['roof_layout'])
        self.assertEqual(resultat['schema_version'], VERSION_SCHEMA)

    def test_avec_document_rend_le_document_tel_quel(self):
        importer_layout(self.calepinage, _DOCUMENT_VALIDE)
        self.calepinage.refresh_from_db()
        resultat = exporter_layout(self.calepinage)
        self.assertEqual(resultat['roof_layout'], _DOCUMENT_VALIDE)
        self.assertTrue(resultat['layout_hash'])


class ImporterLayoutTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Import Layout Co',
                                              slug='import-layout-co-216')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client Import')
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a)

    def test_export_reimporte_donne_le_meme_hash(self):
        importer_layout(self.calepinage, _DOCUMENT_VALIDE)
        self.calepinage.refresh_from_db()
        premier_hash = self.calepinage.layout_hash

        export = exporter_layout(self.calepinage)
        autre = Calepinage.objects.create(company=self.company,
                                          client=self.client_a)
        importer_layout(autre, export['roof_layout'])
        autre.refresh_from_db()

        self.assertEqual(autre.layout_hash, premier_hash)

    def test_document_non_objet_refuse(self):
        with self.assertRaises(ImportLayoutRefuse) as ctx:
            importer_layout(self.calepinage, ['pas', 'un', 'objet'])
        self.assertEqual(ctx.exception.champ, 'roof_layout')

    def test_hors_schema_refuse_en_nommant_le_champ(self):
        invalide = dict(_DOCUMENT_VALIDE, version='deux')  # doit être un entier
        with self.assertRaises(ImportLayoutRefuse) as ctx:
            importer_layout(self.calepinage, invalide)
        self.assertEqual(ctx.exception.champ, 'version')

    def test_scenario_hors_enum_refuse(self):
        invalide = dict(_DOCUMENT_VALIDE, scenario='inexistant')
        with self.assertRaises(ImportLayoutRefuse) as ctx:
            importer_layout(self.calepinage, invalide)
        self.assertEqual(ctx.exception.champ, 'scenario')

    def test_import_herite_du_verrou_cal207(self):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-CAL216-1', statut=Devis.Statut.ENVOYE)
        lie = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=devis)
        with self.assertRaises(APIException) as ctx:
            importer_layout(lie, _DOCUMENT_VALIDE)
        self.assertEqual(ctx.exception.status_code, 409)
