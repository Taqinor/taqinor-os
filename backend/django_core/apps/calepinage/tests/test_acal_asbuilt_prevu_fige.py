# -*- coding: utf-8 -*-
"""ACAL248 — le PRÉVU est figé à la saisie du relevé ; l'as-built s'imprime
sur UNE conception.

LE CONSTAT (C-ACAL-139)
-----------------------
``ecarts_du_calepinage`` relisait le prévu de la conception COURANTE : un
relevé « 12 posés / 12 prévus, écart 0 » devenait « 12 / 14, écart −2 » dès
qu'on retouchait le toit après coup — l'as-built réécrivait l'histoire. Et la
planche « en regard » lisait ``calepinage.roof_layout`` pendant que le tableau
lisait la conception que le chantier a reçue (instantané accepté) : deux
conceptions dans un même document.

Base réelle, écrivain réel (``enregistrer_pose``), aucun mock.
"""
from __future__ import annotations

import copy
import datetime

from apps.calepinage.models import Calepinage, PoseReelle
from apps.calepinage.services.asbuilt import (
    MENTION_CONCEPTION_MODIFIEE, ecarts_du_calepinage, enregistrer_pose,
    etat_pose_reelle,
)
from apps.calepinage.services.documents.document_asbuilt import (
    _construire_document, html_du_document_asbuilt,
)
from apps.calepinage.services.planche import planche_svg_ou_vide
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage
from .test_cal171_planche import LAYOUT as LAYOUT_PLANCHE

RELEVE_LE = '2026-10-01'


def _toit(modules):
    return {'version': 2, 'zones': [{
        'id': 'z1', 'label': 'Toit Sud',
        'geometry': {'count': modules, 'azimuthDeg': 180, 'tiltDeg': 15}}]}


class BaseAsbuilt(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=_toit(12))

    def _retoucher(self, modules):
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=_toit(modules))
        self.calepinage.refresh_from_db()

    def _ligne(self):
        ecarts = ecarts_du_calepinage(self.calepinage)
        return next(ligne for ligne in ecarts['pans']
                    if ligne['pan'] == 'Toit Sud')

    def _relever(self, modules_poses, **extra):
        return enregistrer_pose(self.calepinage, dict(
            {'pan': 'Toit Sud', 'modules_poses': modules_poses,
             'releve_le': RELEVE_LE}, **extra), user=self.user)


class PrevuFigeTest(BaseAsbuilt):

    def test_retoucher_apres_releve_ne_change_pas_l_ecart_passe(self):
        self._relever(12)
        pose = PoseReelle.objects.get(calepinage=self.calepinage)
        self.assertEqual(pose.modules_prevus, 12)
        self.assertEqual(pose.prevu_source, 'calepinage')

        self._retoucher(14)

        ligne = self._ligne()
        self.assertEqual(ligne['prevu'], 12)
        self.assertEqual(ligne['ecart'], 0)
        self.assertTrue(ligne['prevu_fige'])
        self.assertEqual(ligne['prevu_actuel'], 14)
        self.assertTrue(ligne['conception_modifiee'])
        # La porte GET pose-reelle/ sert les mêmes clés (contrat ACAL16).
        servie = etat_pose_reelle(self.calepinage)['lignes'][0]
        self.assertEqual((servie['modules_prevus'], servie['ecart'],
                          servie['prevu_fige'], servie['prevu_actuel'],
                          servie['conception_modifiee']),
                         (12, 0, True, 14, True))

    def test_pdf_asbuilt_dit_conception_modifiee_et_porte_la_date(self):
        self._relever(12)
        self._retoucher(14)

        html = html_du_document_asbuilt(self.calepinage, photos=[])

        self.assertIn('Prévu au relevé (date)', html)
        self.assertIn('12 (au relevé du %s)' % RELEVE_LE, html)
        self.assertIn(MENTION_CONCEPTION_MODIFIEE, html)
        self.assertIn('prévu actuel : 14', html)

    def test_releve_ancien_sans_prevu_fige_reste_vivant(self):
        PoseReelle.objects.create(
            company=self.company, calepinage=self.calepinage, pan='Toit Sud',
            modules_poses=12, releve_le=datetime.date(2026, 9, 1))
        self._retoucher(14)

        ligne = self._ligne()
        self.assertFalse(ligne['prevu_fige'])
        self.assertEqual(ligne['prevu'], 14)
        self.assertEqual(ligne['ecart'], -2)
        self.assertFalse(ligne['conception_modifiee'])

    def test_modules_poses_modifie_refige_le_prevu(self):
        self._relever(12)
        self._retoucher(14)

        # Correction du seul texte : le prévu figé ne bouge pas.
        self._relever(12, ecarts_position='Rangée 2 décalée')
        self.assertEqual(PoseReelle.objects.get(
            calepinage=self.calepinage).modules_prevus, 12)

        # Le nombre posé change : le prévu est re-figé sur la conception.
        self._relever(13)
        self.assertEqual(PoseReelle.objects.get(
            calepinage=self.calepinage).modules_prevus, 14)
        ligne = self._ligne()
        self.assertEqual((ligne['prevu'], ligne['ecart']), (14, -1))
        self.assertFalse(ligne['conception_modifiee'])


class MemeSourceTest(BaseApiCalepinage):

    def test_planche_et_tableau_partagent_la_meme_source(self):
        accepte = copy.deepcopy(LAYOUT_PLANCHE)
        courant = copy.deepcopy(LAYOUT_PLANCHE)
        geometrie = courant['zones'][0]['geometry']
        geometrie['panels'].append({'cx': 6.0, 'cy': 1.0})
        geometrie['count'] = 3
        devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL248', statut=Devis.Statut.ACCEPTE,
            roof_layout=accepte)
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=devis,
            titre='Hangar', roof_layout=courant)

        document = _construire_document(calepinage, photos=[])

        # Le tableau compte la conception que le chantier a reçue (2) …
        self.assertEqual(document['ecarts']['total_prevu'], 2)
        # … et la planche en regard dessine CETTE conception, pas l'autre.
        attendu = planche_svg_ou_vide(calepinage, roof_layout=accepte)
        autre = planche_svg_ou_vide(calepinage)
        self.assertTrue(attendu)
        self.assertNotEqual(attendu, autre)
        self.assertEqual(document['svg_planche'], attendu)
