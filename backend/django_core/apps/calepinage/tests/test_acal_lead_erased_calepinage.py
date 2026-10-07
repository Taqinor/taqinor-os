# -*- coding: utf-8 -*-
"""ACAL301 — l'anonymisation d'un lead (DSR ET rétention) atteint ses
calepinages, par l'abonnement à ``core.events.lead_erased``.

LE CONSTAT (C-ACAL-016) : la rétention des prospects
(``crm.dsr_provider.sweep_retention_prospects``) anonymise par
``anonymiser_lead`` SANS passer par ``core.dsr.effacer`` : le calepinage d'un
prospect effacé gardait « Calepinage Dupont », ses photos et son épingle.
Désormais ``anonymiser_lead`` émet ``lead_erased`` et le calepinage s'y
abonne (``dsr_provider.on_lead_erased`` → LE scrub ``anonymiser_calepinage``).

Chaîne réelle : balayage réel, signal réel, base réelle — l'assertion porte
sur le calepinage RELU, jamais sur un espion.
"""
from __future__ import annotations

import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone

from apps.calepinage.dsr_provider import NOTE_ANONYMISATION
from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion, PhotoSite,
)
from apps.crm.dsr_provider import (
    DUREE_CONSERVATION_PROSPECTS_JOURS, RETENTION_ACTIF_SETTING,
    sweep_retention_prospects,
)
from apps.crm.models import Lead
from apps.records.models import Activity, Attachment
from core import dsr

from .test_api_liste import BaseApiCalepinage

DOCUMENT = {
    'version': 2,
    'pin': {'lat': 33.5, 'lng': -7.6},
    'zones': [{'id': 'z1', 'vertices': [[-7.6, 33.5], [-7.5999, 33.5],
                                        [-7.5999, 33.5001]]}],
}


class LeadEraseCalepinageTest(BaseApiCalepinage):

    def _calepinage_de(self, lead):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk,
            titre='Calepinage Dupont', roof_layout=DOCUMENT)
        CalepinageVersion.objects.create(company=self.company,
                                         calepinage=calepinage,
                                         roof_layout=DOCUMENT)
        CalepinageVariante.objects.create(company=self.company,
                                          calepinage=calepinage, nom='A',
                                          roof_layout=DOCUMENT)
        piece = Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk, file_key='roofs/acal301/p.jpg',
            filename='p.jpg', mime='image/jpeg')
        PhotoSite.objects.create(company=self.company, calepinage=calepinage,
                                 attachment=piece,
                                 prise_le=datetime.date(2026, 9, 1))
        return calepinage

    def _verifier_anonymise(self, calepinage):
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.titre, '')
        self.assertEqual(PhotoSite.objects.filter(
            calepinage=calepinage).count(), 0)
        documents = [calepinage.roof_layout] + [
            ligne.roof_layout for modele in (CalepinageVersion,
                                             CalepinageVariante)
            for ligne in modele.objects.filter(calepinage=calepinage)]
        for document in documents:
            self.assertNotIn('pin', document)

    def test_retention_anonymise_le_calepinage(self):
        prospect = Lead.objects.create(company=self.company, nom='Dupont',
                                       telephone='0612345678')
        calepinage = self._calepinage_de(prospect)
        plus_tard = timezone.now() + datetime.timedelta(
            days=DUREE_CONSERVATION_PROSPECTS_JOURS + 30)

        with override_settings(**{RETENTION_ACTIF_SETTING: True}):
            with self.captureOnCommitCallbacks(execute=True):
                traites = sweep_retention_prospects(plus_tard, apply_=True)

        self.assertGreaterEqual(traites, 1)
        self._verifier_anonymise(calepinage)
        # Un second balayage ne change rien (le lead est déjà anonymisé).
        avant = Calepinage.objects.get(pk=calepinage.pk).roof_layout
        with override_settings(**{RETENTION_ACTIF_SETTING: True}):
            with self.captureOnCommitCallbacks(execute=True):
                sweep_retention_prospects(plus_tard, apply_=True)
        self.assertEqual(Calepinage.objects.get(pk=calepinage.pk).roof_layout,
                         avant)

    def test_dsr_emet_une_fois_et_reste_idempotent(self):
        sujet = Lead.objects.create(company=self.company, nom='Dupont',
                                    email='dupont.acal301@example.ma')
        calepinage = self._calepinage_de(sujet)

        with self.captureOnCommitCallbacks(execute=True):
            rendu = dsr.effacer(self.company, 'dupont.acal301@example.ma')

        self.assertEqual(rendu['calepinage'], {'anonymises': 1})
        self._verifier_anonymise(calepinage)
        # Le chemin DSR (fournisseur) PUIS l'événement : scrub idempotent,
        # aucun double effet — UNE seule note d'anonymisation.
        self.assertEqual(Activity.objects.filter(
            object_id=calepinage.pk, kind='note',
            body=NOTE_ANONYMISATION).count(), 1)
