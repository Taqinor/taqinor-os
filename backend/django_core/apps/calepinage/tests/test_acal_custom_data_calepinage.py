# -*- coding: utf-8 -*-
"""ACAL294 — les champs personnalisés branchés sur le calepinage (D-ACAL-20 :
brancher plutôt que retirer).

LE CONSTAT (C-ACAL-146) : ``platform.py`` déclarait ``'calepinage'`` cible du
registre ``customfields`` sans colonne ``custom_data`` : une définition se
créait mais rien ne se saisissait, et le contrôle d'un renommage de code
(``_code_has_data``) levait ``FieldError`` (500).

Base réelle, route HTTP réelle (société A), registre réel. Aucun mock.
"""
from __future__ import annotations

from apps.calepinage.models import Calepinage
from apps.customfields.models import CustomFieldDef
from apps.customfields.serializers import CustomFieldDefSerializer

from .test_api_liste import BaseApiCalepinage, url_detail


class CustomDataCalepinageTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.definition = CustomFieldDef.objects.create(
            company=self.company, module='calepinage', code='parcelle',
            libelle='N° de parcelle cadastrale', type='text')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')

    def _detail(self):
        reponse = self.api.get(url_detail(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_definition_calepinage_saisie_et_relue(self):
        self.assertIsNone(self._detail()['custom_data'])

        reponse = self.api.patch(url_detail(self.calepinage.pk),
                                 {'custom_data': {'parcelle': 'T-1234'}},
                                 format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._detail()['custom_data'], {'parcelle': 'T-1234'})
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.custom_data, {'parcelle': 'T-1234'})
        # Enregistrer la fiche SANS toucher aux champs : rien ne bouge.
        reponse = self.api.patch(url_detail(self.calepinage.pk),
                                 {'titre': 'Villa Anfa — v2'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._detail()['custom_data'], {'parcelle': 'T-1234'})

    def test_valeur_hors_definition_refusee_400(self):
        reponse = self.api.patch(url_detail(self.calepinage.pk),
                                 {'custom_data': {'inconnu': 'x'}},
                                 format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('custom_data', reponse.data)
        self.assertIn('inconnu', str(reponse.data['custom_data']))
        self.calepinage.refresh_from_db()
        self.assertIsNone(self.calepinage.custom_data)

    def test_patch_code_definition_sans_field_error(self):
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            custom_data={'parcelle': 'T-1234'})

        serializer = CustomFieldDefSerializer(
            self.definition, data={'code': 'parcelle_v2'}, partial=True)

        # Le contrôle lit enfin la colonne : refus NOMMÉ (code verrouillé
        # par la donnée saisie), jamais un FieldError.
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)
