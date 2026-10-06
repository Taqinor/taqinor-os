"""ACAL72 (C-ACAL-027, C-ACAL-026) — téléverser une image de plan en fond.

``POST calepinages/<pk>/fond-plan/`` (multipart PNG/JPEG + ``base_empreinte``)
range l'image comme ``records.Attachment`` du calepinage et écrit
``underlay = {kind:'plan', attachmentId, opacite:0.6, calage:null}`` par la
primitive de section : ``GET plan-importe/`` (qui ne trouvait jamais de pièce)
sert enfin un fond produit par le module.

Source réelle : ``records.Attachment``, ``views/plan_importe.py`` et le
magasin d'objets de test — aucune simulation.

Test-du-test : ne pas écrire l'underlay dans ``fond_plan`` ⇒ ``GET
plan-importe/`` rend 404 et ``test_televersement_ecrit_underlay_et_plan_importe
_le_sert`` rougit.
"""
from __future__ import annotations

import copy
import struct

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import enregistrer_layout
from apps.records.models import Attachment

from .test_api_liste import BaseApiCalepinage, url_detail

D0 = {'version': 2, 'zones': [{'id': 'z1', 'label': 'Pan',
                               'vertices': [[0, 0], [10, 0], [10, 6]]}]}


def _png(largeur=64, hauteur=48):
    """Un PNG d'ESSAI : signature + bloc IHDR (suffit à la lecture de taille)."""
    return (b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR'
            + struct.pack('>II', largeur, hauteur) + b'\x08\x06\x00\x00\x00')


class FondPlanApiTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL72')
        enregistrer_layout(self.calepinage, copy.deepcopy(D0), user=self.user)
        base = url_detail(self.calepinage.pk)
        self.url = f'{base}fond-plan/'
        self.url_layout = f'{base}layout/'
        self.url_plan = f'{base}plan-importe/'

    def _base(self):
        reponse = self.api.get(self.url_layout)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data['empreinte_document']

    def _televerser(self, contenu=None, nom='plan.png', base=None, api=None):
        corps = {'base_empreinte': base or self._base()}
        if contenu is not None:
            corps['fichier'] = SimpleUploadedFile(nom, contenu)
        return (api or self.api).post(self.url, corps, format='multipart')

    def test_televersement_ecrit_underlay_et_plan_importe_le_sert(self):
        reponse = self._televerser(_png())
        self.assertEqual(reponse.status_code, 200, reponse.data)
        fond = reponse.data['underlay']
        self.assertEqual(fond['kind'], 'plan')
        self.assertEqual(fond['opacite'], 0.6)
        self.assertIsNone(fond['calage'])
        piece = Attachment.objects.get(pk=fond['attachmentId'])
        self.assertEqual(piece.company_id, self.company.pk)
        self.assertEqual(piece.object_id, self.calepinage.pk)

        # Persistance : le document relu porte l'underlay, le plan est servi.
        relu = self.api.get(self.url_layout).data['roof_layout']
        self.assertEqual(relu['underlay'], fond)
        self.assertEqual(relu['zones'], D0['zones'])
        plan = self.api.get(self.url_plan)
        self.assertEqual(plan.status_code, 200, plan.data)
        self.assertEqual(plan.data['attachment'], piece.pk)
        self.assertTrue(plan.data['url'])

    def test_fichier_non_image_400(self):
        avant = self.api.get(self.url_layout).data['roof_layout']
        reponse = self._televerser(b'0\nSECTION\n2\nENTITIES\n0\nEOF\n',
                                   nom='plan.dxf')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('fichier', reponse.data)
        self.assertEqual(self.api.get(self.url_layout).data['roof_layout'],
                         avant)
        self.assertFalse(Attachment.objects.filter(
            object_id=self.calepinage.pk).exists())

    def test_fichier_absent_et_jeton_absent_400(self):
        self.assertIn('fichier', self._televerser(None).data)
        sans_jeton = self.api.post(
            self.url, {'fichier': SimpleUploadedFile('p.png', _png())},
            format='multipart')
        self.assertEqual(sans_jeton.status_code, 400)
        self.assertIn('base_empreinte', sans_jeton.data)

    def test_base_perimee_409_sans_piece(self):
        reponse = self._televerser(_png(), base='0' * 64)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['code'], 'document_modifie')
        self.assertFalse(Attachment.objects.filter(
            object_id=self.calepinage.pk).exists())

    def test_autre_societe_404(self):
        base = self._base()
        reponse = self._televerser(_png(), base=base, api=self.api_autre)
        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(Attachment.objects.filter(
            object_id=self.calepinage.pk).exists())
