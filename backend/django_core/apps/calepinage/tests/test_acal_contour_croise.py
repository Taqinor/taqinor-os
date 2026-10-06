"""ACAL76 (C-ACAL-037) — un contour NOUVELLEMENT croisé (nœud papillon) est
refusé à l'enregistrement et à l'import, en nommant son chemin.

Avant : ``[[0,0],[10,6],[10,0],[0,6]]`` (aire signée 0 au lieu de 60, sonde
NET-G1-01) était enregistré tel quel ; aire, pavage et kWc en sortaient faux.
Le test est le noyau réel ``core.calepinage.geometrie.est_polygone_simple`` ;
porte HTTP réelle, base réelle — aucun mock.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import enregistrer_layout
from core.calepinage.geometrie import est_polygone_simple

from .test_api_liste import BaseApiCalepinage, url_detail

PAPILLON = [[0, 0], [10, 6], [10, 0], [0, 6]]
RECTANGLE = [[0, 0], [10, 0], [10, 6], [0, 6]]

D0 = {
    'version': 2,
    'zones': [{'id': 'z1', 'label': 'Pan sud', 'pitchDeg': 15,
               'vertices': copy.deepcopy(RECTANGLE)}],
    'panelWatt': 575,
}

_SCHEMA = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'roof_layout_v2.schema.json')
EXEMPLE_V2 = json.loads(_SCHEMA.read_text(encoding='utf-8'))['exemple']


class EstPolygoneSimpleTest(SimpleTestCase):

    def test_papillon_n_est_pas_simple(self):
        self.assertFalse(est_polygone_simple(PAPILLON))

    def test_rectangle_et_l_sont_simples(self):
        self.assertTrue(est_polygone_simple(RECTANGLE))
        self.assertTrue(est_polygone_simple(RECTANGLE + [[0, 0]]))
        self.assertTrue(est_polygone_simple(
            [[0, 0], [6, 0], [6, 2], [2, 2], [2, 6], [0, 6]]))

    def test_contact_d_un_sommet_et_repli_colineaire(self):
        self.assertFalse(est_polygone_simple(
            [[0, 0], [4, 0], [4, 4], [2, 0], [0, 4]]))
        self.assertFalse(est_polygone_simple([[0, 0], [10, 0], [5, 0],
                                              [5, 5]]))


class ContourCroiseApiTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL76')
        enregistrer_layout(self.calepinage, copy.deepcopy(D0), user=self.user)
        self.url = f'{url_detail(self.calepinage.pk)}layout/'

    def _lire(self):
        return self.api.get(self.url).data['roof_layout']

    def _poster(self, document):
        # ACAL316 — If-Match obligatoire : le jeton lu juste avant d'écrire.
        jeton = self.api.get(self.url).data['empreinte_document'] or ''
        return self.api.post(self.url, {'roof_layout': document},
                             format='json', HTTP_IF_MATCH=f'"{jeton}"')

    def test_papillon_nouveau_refuse_400_nomme(self):
        document = copy.deepcopy(D0)
        document['zones'][0]['vertices'] = copy.deepcopy(PAPILLON)
        reponse = self._poster(document)
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('zones.0.vertices', reponse.data)
        self.assertIn('se croise', reponse.data['zones.0.vertices'])
        self.assertEqual(self._lire(), D0)

    def test_zone_d_exclusion_croisee_refusee(self):
        document = dict(copy.deepcopy(D0), exclusionZones=[{
            'id': 'zx-1', 'nature': 'INTERDITE',
            'vertices': copy.deepcopy(PAPILLON)}])
        reponse = self._poster(document)
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('exclusionZones.0.vertices', reponse.data)
        self.assertEqual(self._lire(), D0)

    def test_papillon_deja_stocke_et_inchange_accepte(self):
        ancien = copy.deepcopy(D0)
        ancien['zones'][0]['vertices'] = copy.deepcopy(PAPILLON)
        # Un dossier HISTORIQUE porte déjà le contour croisé.
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=ancien)
        document = copy.deepcopy(ancien)
        document['panelWatt'] = 580
        reponse = self._poster(document)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._lire(), document)

    def test_import_papillon_refuse(self):
        document = copy.deepcopy(EXEMPLE_V2)
        document['zones'][0]['vertices'] = copy.deepcopy(PAPILLON)
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}import-layout/', document,
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('zones.0.vertices', reponse.data)
        self.assertEqual(self._lire(), D0)
