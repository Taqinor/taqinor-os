"""CAL216 — import/export JSON du ``roof_layout``.

Ce qui est prouvé ici :

* un export réimporté donne le MÊME hash (round-trip) ;
* export sans document enregistré rend ``roof_layout: None`` (jamais
  ``{}``) et le numéro de version du schéma ;
* un JSON hors schéma est refusé, en NOMMANT le chemin du champ fautif ;
* un document non-objet (liste, nombre…) est refusé ;
* l'import passe par le chemin d'écriture unique : il hérite donc du
  verrou CAL207/ACAL42 (devis accepté → 409) sans code dupliqué.

Run :
    python manage.py test apps.calepinage.tests.test_cal216_import_export -v2
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import APIException

from apps.calepinage.models import Calepinage
from apps.calepinage.services.io_layout import (
    ImportLayoutRefuse, VERSION_SCHEMA, exporter_layout, importer_layout,
    valider_document,
)
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.services import layout_hash
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
            reference='DEV-CAL216-1', statut=Devis.Statut.ACCEPTE)
        lie = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=devis)
        with self.assertRaises(APIException) as ctx:
            importer_layout(lie, _DOCUMENT_VALIDE)
        self.assertEqual(ctx.exception.status_code, 409)

    def _refus_pan(self, **cles):
        """Le champ nommé par le refus d'un premier pan portant ``cles``."""
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        document['zones'][0].update(cles)
        with self.assertRaises(ImportLayoutRefuse) as ctx:
            importer_layout(self.calepinage, document)
        return ctx.exception.champ

    def _hash_importe(self, document):
        autre = Calepinage.objects.create(company=self.company,
                                          client=self.client_a)
        importer_layout(autre, document)
        autre.refresh_from_db()
        return autre.layout_hash

    def test_pan_sans_cles_neuves_garde_son_hash(self):
        # ACAL573/586/587 — aucune des clés de pan neuves dans l'exemple.
        for cle in ('existant', 'anneeMiseEnService', 'coupuresPavage',
                    'porteeEntrePieds'):
            self.assertNotIn(cle, _DOCUMENT_VALIDE['zones'][0])
        self.assertEqual(self._hash_importe(_DOCUMENT_VALIDE),
                         layout_hash(_DOCUMENT_VALIDE))

    def test_pan_existant_accepte(self):
        # ACAL573
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        document['zones'][0].update(existant=True, anneeMiseEnService=2019)
        self.assertTrue(self._hash_importe(document))

    def test_existant_non_booleen_refuse(self):
        self.assertEqual(self._refus_pan(existant='oui'), 'zones.0.existant')

    def test_annee_texte_refusee(self):
        self.assertEqual(self._refus_pan(anneeMiseEnService='2019'),
                         'zones.0.anneeMiseEnService')

    def test_coupure_de_pavage(self):
        # ACAL586
        coupure = {'tousLesNModules': 10, 'largeurCoupureM': 0.8,
                   'source': 'allée de maintenance'}
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        document['zones'][0]['coupuresPavage'] = coupure
        self.assertTrue(self._hash_importe(document))
        self.assertEqual(
            self._refus_pan(coupuresPavage=dict(coupure, largeurCoupureM=0)),
            'zones.0.coupuresPavage.largeurCoupureM')
        self.assertEqual(
            self._refus_pan(coupuresPavage=dict(coupure, source='')),
            'zones.0.coupuresPavage.source')

    def test_portee_entre_pieds(self):
        # ACAL587
        portee = {'valeurM': 2.4, 'source': 'notice du système, p. 12'}
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        document['zones'][0]['porteeEntrePieds'] = portee
        self.assertTrue(self._hash_importe(document))
        self.assertEqual(
            self._refus_pan(porteeEntrePieds=dict(portee, valeurM=0)),
            'zones.0.porteeEntrePieds.valeurM')
        self.assertEqual(self._refus_pan(porteeEntrePieds={'valeurM': 2.4}),
                         'zones.0.porteeEntrePieds')

    def test_import_d_un_export_plus_ancien_garde_le_plafond(self):
        """Revue lot 8 (suite ACAL1720) — importer un export d'AVANT des
        numéros dépensés : la conception du fichier revient, le plafond
        stocké couvre les numéros dépensés depuis (jamais redonnés) ; clé
        volatile : l'empreinte « document » est celle du fichier."""
        from apps.calepinage.services.layout import empreinte_document

        ancien = copy.deepcopy(_DOCUMENT_VALIDE)
        pan = ancien['zones'][0]
        poses = [p['n'] for p in pan['geometry']['panels']]
        depense = copy.deepcopy(ancien)
        depense['zones'][0]['geometry']['panels'][-1]['n'] = max(poses) + 50
        importer_layout(self.calepinage, depense)
        importer_layout(self.calepinage, copy.deepcopy(ancien))
        self.calepinage.refresh_from_db()
        stocke = self.calepinage.roof_layout
        self.assertEqual(stocke['zones'], ancien['zones'])
        self.assertEqual(stocke['plafondsNumerotation'],
                         {pan['id']: max(poses) + 50})
        self.assertEqual(empreinte_document(stocke), empreinte_document(ancien))
        self.assertEqual(self.calepinage.layout_hash, layout_hash(ancien))


class ContratDePanSansBaseTest(SimpleTestCase):
    """Les mêmes refus par la porte ``valider_document``, sans base."""

    def _champ(self, **cles):
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        document['zones'][0].update(cles)
        with self.assertRaises(ImportLayoutRefuse) as ctx:
            valider_document(document)
        return ctx.exception.champ

    def _accepte(self, **cles):
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        document['zones'][0].update(cles)
        valider_document(document)

    def test_acal573_pan_existant(self):
        self._accepte(existant=True, anneeMiseEnService=2019)
        self._accepte(existant=True, anneeMiseEnService=None)
        self.assertEqual(self._champ(existant='oui'), 'zones.0.existant')
        self.assertEqual(self._champ(anneeMiseEnService='2019'),
                         'zones.0.anneeMiseEnService')

    def test_acal586_coupure_de_pavage(self):
        coupure = {'tousLesNModules': 10, 'largeurCoupureM': 0.8,
                   'source': 'joint de dilatation'}
        self._accepte(coupuresPavage=coupure)
        self.assertEqual(
            self._champ(coupuresPavage=dict(coupure, largeurCoupureM=0)),
            'zones.0.coupuresPavage.largeurCoupureM')
        self.assertEqual(self._champ(coupuresPavage=dict(coupure, source='')),
                         'zones.0.coupuresPavage.source')

    def test_acal587_portee_entre_pieds(self):
        portee = {'valeurM': 2.4, 'source': 'notice du système, p. 12'}
        self._accepte(porteeEntrePieds=portee)
        self.assertEqual(
            self._champ(porteeEntrePieds=dict(portee, valeurM=0)),
            'zones.0.porteeEntrePieds.valeurM')
        self.assertEqual(self._champ(porteeEntrePieds={'valeurM': 2.4}),
                         'zones.0.porteeEntrePieds')
        self.assertEqual(
            self._champ(porteeEntrePieds=dict(portee, source='')),
            'zones.0.porteeEntrePieds.source')


class ReperesChantierSchemaTest(SimpleTestCase):
    """ACAL599 — la couche « Repères de chantier » : forme du contrat."""

    def _champ(self, **cles):
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        document['reperesChantier'][0].update(cles)
        with self.assertRaises(ImportLayoutRefuse) as ctx:
            valider_document(document)
        return ctx.exception.champ

    def test_l_exemple_complet_porte_un_repere_et_est_valide(self):
        self.assertEqual(len(_DOCUMENT_VALIDE['reperesChantier']), 1)
        valider_document(copy.deepcopy(_DOCUMENT_VALIDE))

    def test_sans_la_cle_le_document_reste_valide(self):
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        del document['reperesChantier']
        valider_document(document)

    def test_rayon_null_accepte(self):
        document = copy.deepcopy(_DOCUMENT_VALIDE)
        document['reperesChantier'][0]['rayonM'] = None
        valider_document(document)

    def test_cas_refuses_nomment_le_champ(self):
        for cles, champ in (
                ({'type': 'grue'}, 'reperesChantier.0.type'),
                ({'rayonM': 0}, 'reperesChantier.0.rayonM'),
                ({'rayonM': -1}, 'reperesChantier.0.rayonM'),
                ({'point': [-7.62]}, 'reperesChantier.0.point'),
                ({'id': ''}, 'reperesChantier.0.id')):
            with self.subTest(cles=cles):
                self.assertEqual(self._champ(**cles), champ)
