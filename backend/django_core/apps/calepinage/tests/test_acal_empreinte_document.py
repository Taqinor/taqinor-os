"""ACAL39 — « inchangé », la version et le journal se décident sur l'empreinte
« document » (D-ACAL-4), jamais sur ``layout_hash``.

Avant : ``enregistrer_layout`` comparait l'empreinte IMPRIMÉE (ventes), aveugle
à l'horizon, aux champs au sol (``poseSurfaces``)… — un horizon dessiné
répondait ``inchange: true`` et aucune version n'était déposée (live CYC-04).

Tout passe par ``enregistrer_layout`` réel sur la base de test : aucun mock.
"""
from __future__ import annotations

import copy
import json

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import (
    CLES_VOLATILES, empreinte_document, enregistrer_layout,
    garder_types_numeriques,
)
from apps.records.models import Activity

from .test_api_liste import BaseApiCalepinage, url_detail

D0 = {
    'version': 2,
    'zones': [{
        'id': 'z1', 'label': 'Pan sud', 'pitchDeg': 15,
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'geometry': {'solarAccess': {'values': [0.97, 0.95],
                                     'computedAt': '2026-10-01T10:00:00Z'}},
    }],
    'result': {'panels': 12, 'kwc': 6.9},
    'panelWatt': 575,
    'consumption': {'methode': 'facture',
                    'source': {'origine': 'facture',
                               'saisi_le': '2026-09-18T10:00:00Z'}},
}
HORIZON = {'source': 'saisie',
           'points': [{'azimuthDeg': 90, 'heightDeg': 8.0},
                      {'azimuthDeg': 270, 'heightDeg': 12.5}],
           'hauteurMaxDeg': 12.5}
POSE_SURFACES = [{'id': 'sol-1', 'kind': 'sol',
                  'engine': {'modules': 340}}]


def _variante_volatile(document):
    """Le même document, ne différant QUE par les clés volatiles nommées."""
    autre = copy.deepcopy(document)
    autre['activeAreaId'] = 'z1'
    autre['scene'] = {'sunDay': 355, 'sunHour': 9.5}
    autre['zones'][0]['geometry']['solarAccess']['computedAt'] = (
        '2026-10-05T08:00:00Z')
    autre['consumption']['source']['saisi_le'] = '2026-10-05T08:00:00Z'
    return autre


def _en_flottants(valeur):
    """ERR-ACAL351 — le document tel qu'un écrivain Python l'écrit (15.0)."""
    if isinstance(valeur, dict):
        return {cle: _en_flottants(v) for cle, v in valeur.items()}
    if isinstance(valeur, list):
        return [_en_flottants(v) for v in valeur]
    if isinstance(valeur, int) and not isinstance(valeur, bool):
        return float(valeur)
    return valeur


def _comme_javascript(valeur):
    """ERR-ACAL351 — le même document re-sérialisé par l'atelier (15)."""
    if isinstance(valeur, dict):
        return {cle: _comme_javascript(v) for cle, v in valeur.items()}
    if isinstance(valeur, list):
        return [_comme_javascript(v) for v in valeur]
    if isinstance(valeur, float) and valeur.is_integer():
        return int(valeur)
    return valeur


class EmpreinteDocumentPureTest(SimpleTestCase):

    def test_err_acal351_types_numeriques_gardes(self):
        stocke = _en_flottants(D0)
        rendu = garder_types_numeriques(stocke, _comme_javascript(stocke))
        self.assertEqual(json.dumps(rendu, sort_keys=True),
                         json.dumps(stocke, sort_keys=True))
        self.assertEqual(empreinte_document(rendu),
                         empreinte_document(stocke))
        # Une VRAIE valeur changée passe, avec son type reçu.
        recu = _comme_javascript(stocke)
        recu['zones'][0]['pitchDeg'] = 20
        self.assertEqual(
            garder_types_numeriques(stocke, recu)['zones'][0]['pitchDeg'], 20)
        # ``True`` n'est jamais confondu avec ``1``.
        self.assertIs(garder_types_numeriques({'a': 1}, {'a': True})['a'],
                      True)

    def test_cles_volatiles_nommees(self):
        self.assertEqual(set(CLES_VOLATILES), {
            'activeAreaId', 'scene',
            'zones[].geometry.solarAccess.computedAt',
            'consumption.source.saisi_le'})

    def test_volatiles_hors_empreinte(self):
        self.assertEqual(empreinte_document(D0),
                         empreinte_document(_variante_volatile(D0)))

    def test_document_non_modifie_par_le_calcul(self):
        original = copy.deepcopy(D0)
        empreinte_document(_variante_volatile(D0))
        self.assertEqual(D0, original)

    def test_horizon_pose_surfaces_et_pin_comptent(self):
        base = empreinte_document(D0)
        for cle, valeur in (('horizonProfile', HORIZON),
                            ('poseSurfaces', POSE_SURFACES),
                            ('pin', {'lat': 33.57, 'lng': -7.58})):
            with self.subTest(cle=cle):
                self.assertNotEqual(
                    base, empreinte_document(dict(D0, **{cle: valeur})))

    def test_alias_de_pans(self):
        pans = {'areas': copy.deepcopy(D0['zones'])}
        autre = copy.deepcopy(pans)
        autre['areas'][0]['geometry']['solarAccess']['computedAt'] = 'x'
        self.assertEqual(empreinte_document(pans), empreinte_document(autre))

    def test_rien_n_a_pas_d_empreinte(self):
        self.assertEqual(empreinte_document(None), '')
        self.assertEqual(len(empreinte_document({})), 64)


class EmpreinteDocumentEnBaseTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL-DOC')
        enregistrer_layout(self.calepinage, copy.deepcopy(D0), user=self.user)

    def _versions(self):
        return self.calepinage.versions.count()

    def _journal(self):
        return Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk, field='roof_layout').count()

    def test_horizon_seul_cree_une_version(self):
        versions, journal = self._versions(), self._journal()
        rendu = enregistrer_layout(
            self.calepinage, dict(copy.deepcopy(D0), horizonProfile=HORIZON),
            user=self.user)
        self.assertFalse(rendu['inchange'])
        self.assertIsNotNone(rendu['version'])
        self.assertEqual(self._versions(), versions + 1)
        self.assertEqual(self._journal(), journal + 1)

    def test_retrait_pose_surfaces_cree_une_version(self):
        enregistrer_layout(
            self.calepinage,
            dict(copy.deepcopy(D0), poseSurfaces=POSE_SURFACES),
            user=self.user)
        versions, journal = self._versions(), self._journal()
        rendu = enregistrer_layout(self.calepinage, copy.deepcopy(D0),
                                   user=self.user)
        self.assertFalse(rendu['inchange'])
        self.assertEqual(self._versions(), versions + 1)
        self.assertEqual(self._journal(), journal + 1)

    def test_cles_volatiles_ne_creent_rien(self):
        versions, journal = self._versions(), self._journal()
        rendu = enregistrer_layout(self.calepinage, _variante_volatile(D0),
                                   user=self.user)
        self.assertTrue(rendu['inchange'])
        self.assertIsNone(rendu['version'])
        self.assertEqual(self._versions(), versions)
        self.assertEqual(self._journal(), journal)

    def test_renvoi_identique_inchange(self):
        url = f'{url_detail(self.calepinage.pk)}layout/'
        d1 = dict(copy.deepcopy(D0), horizonProfile=HORIZON)
        # ACAL316 — If-Match obligatoire : le jeton lu avant chaque écriture.
        base = self.api.get(url).data['empreinte_document']
        premier = self.api.post(url, {'roof_layout': d1}, format='json',
                                HTTP_IF_MATCH=f'"{base}"')
        self.assertEqual(premier.status_code, 200, premier.data)
        self.assertFalse(premier.data['inchange'])
        relu = self.api.get(url)
        self.assertEqual(relu.status_code, 200)
        document = copy.deepcopy(relu.data['roof_layout'])
        versions, journal = self._versions(), self._journal()
        jeton = relu.data['empreinte_document']
        second = self.api.post(url, {'roof_layout': document}, format='json',
                               HTTP_IF_MATCH=f'"{jeton}"')
        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.data['inchange'])
        self.assertEqual(self._versions(), versions)
        self.assertEqual(self._journal(), journal)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout, d1)

    def test_err_acal351_flottants_entiers_premier_enregistrement_inchange(self):
        """Un document semé en flottants entiers (15.0), renvoyé sans geste par
        l'atelier (15) : « inchangée », aucune version, et les empreintes déjà
        stockées (layout_hash, jeton document) restent égales."""
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ERR-ACAL351')
        stocke = _en_flottants(dict(copy.deepcopy(D0),
                                    horizonProfile=HORIZON))
        enregistrer_layout(calepinage, stocke, user=self.user)
        calepinage.refresh_from_db()
        hash_stocke = calepinage.layout_hash
        jeton = empreinte_document(calepinage.roof_layout)
        versions = calepinage.versions.count()
        url = f'{url_detail(calepinage.pk)}layout/'
        self.assertEqual(self.api.get(url).data['empreinte_document'], jeton)
        reponse = self.api.post(
            url, {'roof_layout': _comme_javascript(stocke)}, format='json',
            HTTP_IF_MATCH=f'"{jeton}"')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['inchange'])
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.versions.count(), versions)
        self.assertEqual(calepinage.layout_hash, hash_stocke)
        self.assertEqual(empreinte_document(calepinage.roof_layout), jeton)
        self.assertEqual(reponse.data['empreinte_document'], jeton)
