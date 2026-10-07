# -*- coding: utf-8 -*-
"""ACAL247 — ``PoseReelle.modules_prevus`` / ``prevu_source`` : nuls / vides
par défaut (relevé ancien, prévu vivant), relus à l'identique une fois posés."""
from __future__ import annotations

import datetime

from apps.calepinage.models import Calepinage, PoseReelle

from .test_api_liste import BaseApiCalepinage


class SchemaPoseTest(BaseApiCalepinage):

    def test_modules_prevus_et_source_nuls_par_defaut_et_relus(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa')
        pose = PoseReelle.objects.create(
            company=self.company, calepinage=calepinage, pan='Toit Sud',
            modules_poses=12, releve_le=datetime.date(2026, 10, 1))

        pose.refresh_from_db()
        self.assertIsNone(pose.modules_prevus)
        self.assertEqual(pose.prevu_source, '')

        pose.modules_prevus = 12
        pose.prevu_source = 'conception'
        pose.save(update_fields=['modules_prevus', 'prevu_source'])
        relu = PoseReelle.objects.get(pk=pose.pk)
        self.assertEqual(relu.modules_prevus, 12)
        self.assertEqual(relu.prevu_source, 'conception')
