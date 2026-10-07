# -*- coding: utf-8 -*-
"""ACAL253 — migration de données : la pente RACINE ``penteDeg`` devient la
pente du pan unique ; à plusieurs pans, rien n'est deviné (note de chatter).

La fonction de migration RÉELLE (``0026_acal253_pente_racine_vers_pan``) est
appelée sur des ``Calepinage`` réels en base, avec le registre d'applications
réel.
"""
from __future__ import annotations

import importlib

from django.apps import apps as registre
from django.contrib.contenttypes.models import ContentType

from apps.calepinage.models import Calepinage
from apps.records.models import Activity

from .test_api_liste import BaseApiCalepinage

MIGRATION = importlib.import_module(
    'apps.calepinage.migrations.0026_acal253_pente_racine_vers_pan')


def _pan(ident, label):
    return {'id': ident, 'label': label,
            'geometry': {'count': 4, 'azimuthDeg': 180}}


class MigrationPenteRacineTest(BaseApiCalepinage):

    def _calepinage(self, layout):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit',
            roof_layout=layout)

    def test_un_pan_recoit_la_pente(self):
        calepinage = self._calepinage({
            'version': 2, 'penteDeg': 30, 'penteSource': 'degres',
            'zones': [_pan('z1', 'Pan Sud')]})

        MIGRATION.migrer_pente_racine(registre, None)

        calepinage.refresh_from_db()
        layout = calepinage.roof_layout
        self.assertNotIn('penteDeg', layout)
        self.assertNotIn('penteSource', layout)
        self.assertEqual(layout['zones'][0]['pitchDeg'], 30)
        self.assertEqual(layout['zones'][0]['pitchSource'],
                         {'mode': 'degres', 'degres': 30})
        # Rejouer la migration ne change plus rien (idempotente).
        avant = calepinage.roof_layout
        MIGRATION.migrer_pente_racine(registre, None)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout, avant)

        # L'inverse restaure la pente racine depuis le pan unique.
        MIGRATION.restaurer_pente_racine(registre, None)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout['penteDeg'], 30)

    def test_plusieurs_pans_journalise_sans_deviner(self):
        zones = [_pan('z1', 'Pan Sud'), _pan('z2', 'Pan Nord')]
        calepinage = self._calepinage({'version': 2, 'penteDeg': 22.5,
                                       'zones': zones})

        inventaire = MIGRATION.inventaire_pente_racine(registre)
        self.assertEqual([ligne['calepinage'] for ligne in inventaire],
                         [calepinage.pk])
        self.assertEqual(inventaire[0]['note'],
                         'pente saisie 22,5° non attribuée (plusieurs pans)')
        calepinage.refresh_from_db()
        self.assertIn('penteDeg', calepinage.roof_layout)  # dry-run : rien

        MIGRATION.migrer_pente_racine(registre, None)

        calepinage.refresh_from_db()
        layout = calepinage.roof_layout
        self.assertNotIn('penteDeg', layout)
        self.assertEqual(layout['zones'], zones)  # aucun pan deviné
        note = Activity.objects.get(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk, kind='note')
        self.assertEqual(note.body,
                         'pente saisie 22,5° non attribuée (plusieurs pans)')
        self.assertEqual(note.company_id, self.company.pk)
