"""ACAL206 (C-ACAL-025) — « Appliquer l'azimut au pan » : la provenance et la
précision de l'azimut s'écrivent PAR LA PRIMITIVE DE SECTION.

L'écran du relevé pose, sur UN pan choisi, ``facingAzimuthDeg`` +
``facingAzimuthSource = 'releve'`` + ``facingAzimuthPrecisionDeg`` par
``POST layout/section/`` (C-ACAL-044). Deux garanties tenues ici :

* le schéma ``roof_layout_v2`` accepte les trois clés (M0 unique, ACAL2) ET la
  liste blanche de la section ``zones`` les laisse passer — sans quoi l'écran
  recevrait un 400 « champ de zone non autorisé » ;
* l'écriture RÉELLE (base, jeton) ne touche que le pan visé : l'autre pan et
  les autres clés du document sont octet-identiques, et la relecture porte les
  trois clés.

Run :
    python manage.py test apps.calepinage.tests.test_acal_releve_azimut_pan -v2
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import (
    CHAMPS_SECTION_ZONE, empreinte_document, enregistrer_section,
)
from authentication.models import Company

SCHEMA = (Path(__file__).resolve().parent.parent / 'contract_samples'
          / 'roof_layout_v2.schema.json')

CLES_PROVENANCE = ('facingAzimuthDeg', 'facingAzimuthSource',
                   'facingAzimuthPrecisionDeg')


class ProvenanceAcceptee(SimpleTestCase):

    def test_cles_de_provenance_acceptees_par_le_schema(self):
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        proprietes = {}
        for definition in schema['$defs'].values():
            proprietes.update(definition.get('properties', {}))
        for cle in CLES_PROVENANCE:
            self.assertIn(cle, proprietes, cle)
            self.assertIn(cle, CHAMPS_SECTION_ZONE, cle)
        self.assertEqual(proprietes['facingAzimuthSource']['enum'],
                         ['releve', 'visite', 'saisie'])


DOCUMENT = {
    'version': 2,
    'panelWatt': 575,
    'zones': [
        {'id': 'zA', 'label': 'Pan A', 'facingAzimuthDeg': 90,
         'pitchDeg': 22, 'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]]},
        {'id': 'zB', 'label': 'Pan B', 'facingAzimuthDeg': 270,
         'pitchDeg': 15, 'vertices': [[12, 0], [18, 0], [18, 5], [12, 5]]},
    ],
}


class EcritureParSection(TestCase):

    def setUp(self):
        self.societe = Company.objects.create(nom='ACAL206', slug='acal206')
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=1, titre='Azimut 206',
            roof_layout=copy.deepcopy(DOCUMENT))

    def test_azimut_applique_au_pan_choisi_et_seulement_a_lui(self):
        jeton = empreinte_document(self.calepinage.roof_layout)
        enregistrer_section(
            self.calepinage, 'zones',
            {'facingAzimuthDeg': 187, 'facingAzimuthSource': 'releve',
             'facingAzimuthPrecisionDeg': 5},
            base_empreinte=jeton, zone_id='zB')
        self.calepinage.refresh_from_db()
        zones = {z['id']: z for z in self.calepinage.roof_layout['zones']}
        self.assertEqual(zones['zB']['facingAzimuthDeg'], 187)
        self.assertEqual(zones['zB']['facingAzimuthSource'], 'releve')
        self.assertEqual(zones['zB']['facingAzimuthPrecisionDeg'], 5)
        # Le pan non choisi et les autres clés : intacts.
        self.assertEqual(zones['zA'], DOCUMENT['zones'][0])
        self.assertEqual(zones['zB']['pitchDeg'], 15)
        self.assertEqual(self.calepinage.roof_layout['panelWatt'], 575)
