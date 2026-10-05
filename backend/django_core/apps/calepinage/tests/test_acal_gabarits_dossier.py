# -*- coding: utf-8 -*-
"""ACAL238 — la porte de dépôt des gabarits et la porte joindre-piece.

LE CONSTAT (C-ACAL-135)
-----------------------
``GabaritDossierReglementaire`` n'avait ni sérialiseur, ni route : aucune
société ne pouvait déposer de gabarit, donc ``dossiers-reglementaires/`` ne
proposait jamais rien et aucune pièce ne pouvait être jointe.

Ce qui est prouvé, en base RÉELLE, par la route HTTP réelle : dépôt →
liste → dossier proposé ; pièce obligatoire jointe → dossier générable ;
400 sous le champ NOMMÉ ; même 404 pour l'id d'une autre société et un id
absent ; 409 nommé à la suppression d'un gabarit utilisé ; 403 au simple
lecteur ; journal (auteur, avant, après). Seul l'envoi à MinIO (frontière
réseau) est remplacé : la validation des octets du stockage reste réelle.
"""
from __future__ import annotations

import json
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.calepinage.models import (
    Calepinage, DossierReglementaire, GabaritDossierReglementaire,
    ParametresCalepinage,
)
from apps.calepinage.services.documents.manuel_proprietaire import (
    gabarit_manuel_actif,
)
from apps.records.models import Activity
from apps.roles.models import Role

from .test_api_liste import BaseApiCalepinage, url_detail

URL = '/api/django/calepinage/gabarits-dossiers/'
PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
DOCX = b'PK\x03\x04\x14\x00\x06\x00' + b'\x00' * 32

PIECES = [{'code': 'plan_masse', 'intitule': 'Plan de masse',
           'obligatoire': True,
           'source_reference': 'Cahier des charges du gestionnaire'}]


def _pdf(nom='gabarit.pdf', octets=PDF):
    return SimpleUploadedFile(nom, octets, content_type='application/pdf')


class BaseGabarits(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        ParametresCalepinage.objects.create(company=self.company,
                                            imagerie={'pays': 'ma'})
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        # La frontière RÉSEAU seule : aucun envoi vers MinIO.
        mock.patch('apps.records.storage.get_minio_client').start()
        mock.patch('apps.records.storage.ensure_uploads_bucket').start()
        self.addCleanup(mock.patch.stopall)

    def _deposer(self, api=None, **champs):
        corps = {'pays': 'ma', 'code': 'raccordement_bt',
                 'genre': 'raccordement',
                 'intitule': 'Dossier de raccordement BT',
                 'pieces_attendues': json.dumps(PIECES),
                 'champs': json.dumps([]), 'fichier': _pdf()}
        corps.update(champs)
        return (api or self.api).post(URL, corps, format='multipart')

    def _dossiers(self):
        reponse = self.api.get(
            f'{url_detail(self.calepinage.pk)}dossiers-reglementaires/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data['dossiers']

    def _joindre(self, gabarit_id, **corps):
        return self.api.post(
            f'{url_detail(self.calepinage.pk)}joindre-piece/',
            dict({'gabarit': gabarit_id, 'piece': 'plan_masse'}, **corps),
            format='multipart')


class DepotTest(BaseGabarits):

    def test_depot_gabarit_puis_dossier_liste(self):
        reponse = self._deposer()
        self.assertEqual(reponse.status_code, 201, reponse.data)
        gabarit = reponse.data['gabarit']
        self.assertEqual(gabarit['pieces_attendues'], PIECES)
        self.assertEqual(gabarit['fichiers']['nom'], 'gabarit.pdf')
        self.assertEqual(gabarit['depose_par']['id'], self.user.pk)

        en_base = GabaritDossierReglementaire.objects.get(pk=gabarit['id'])
        self.assertEqual(en_base.company_id, self.company.pk)
        self.assertEqual(en_base.fichier.company_id, self.company.pk)

        liste = self.api.get(URL)
        self.assertEqual(liste.status_code, 200, liste.data)
        self.assertEqual(liste.data['gabarits'], [gabarit])
        detail = self.api.get(f"{URL}{gabarit['id']}/")
        self.assertEqual(detail.data, gabarit)

        dossiers = self._dossiers()
        self.assertEqual(len(dossiers), 1)
        self.assertTrue(dossiers[0]['gabarit']['present'])
        self.assertEqual(dossiers[0]['gabarit_id'], gabarit['id'])

        # Journal : auteur, (rien) avant, après.
        journal = Activity.objects.get(object_id=gabarit['id'],
                                       field='gabarit', kind='creation')
        self.assertEqual(journal.created_by_id, self.user.pk)
        self.assertEqual(json.loads(journal.new_value)['code'],
                         'raccordement_bt')

    def test_modification_journalisee_avant_apres(self):
        gabarit_id = self._deposer().data['gabarit']['id']
        reponse = self.api.patch(f'{URL}{gabarit_id}/',
                                 {'intitule': 'Dossier BT v2',
                                  'actif': False}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['intitule'], 'Dossier BT v2')
        self.assertFalse(self.api.get(f'{URL}{gabarit_id}/').data['actif'])
        journal = Activity.objects.get(object_id=gabarit_id, field='gabarit',
                                       kind='modification')
        self.assertEqual(json.loads(journal.old_value)['intitule'],
                         'Dossier de raccordement BT')
        self.assertEqual(json.loads(journal.new_value)['intitule'],
                         'Dossier BT v2')

    def test_gabarit_manuel_debloque_le_manuel_proprietaire(self):
        self.assertIsNone(gabarit_manuel_actif(self.company))
        reponse = self._deposer(code='manuel', genre='manuel',
                                intitule='Manuel du propriétaire',
                                pieces_attendues=json.dumps([]))
        self.assertEqual(reponse.status_code, 201, reponse.data)
        manuel = gabarit_manuel_actif(self.company)
        self.assertEqual(manuel.pk, reponse.data['gabarit']['id'])
        self.assertTrue(manuel.fichier_present)


class PieceJointeTest(BaseGabarits):

    def test_joindre_piece_obligatoire_rend_le_dossier_generable(self):
        gabarit_id = self._deposer().data['gabarit']['id']
        self.assertFalse(self._dossiers()[0]['peut_generer'])

        reponse = self._joindre(gabarit_id, fichier=_pdf('plan.pdf'))
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(reponse.data['etat'], 'fournie')
        dossier = DossierReglementaire.objects.get(
            calepinage=self.calepinage, gabarit_id=gabarit_id)
        jointe = dossier.pieces_jointes['plan_masse']
        self.assertEqual(jointe['attachment_id'], reponse.data['attachment'])
        self.assertTrue(jointe['depose_le'])

        relu = self._dossiers()[0]
        self.assertTrue(relu['peut_generer'], relu['motif_non_generable'])
        self.assertEqual(relu['pieces'][0]['etat'], 'fournie')

        retrait = self._joindre(gabarit_id, retirer='true')
        self.assertEqual(retrait.status_code, 200, retrait.data)
        self.assertEqual(retrait.data['etat'], 'manquante')
        self.assertFalse(self._dossiers()[0]['peut_generer'])

    def test_piece_inconnue_400_nommee(self):
        gabarit_id = self._deposer().data['gabarit']['id']
        reponse = self._joindre(gabarit_id, piece='plan_x',
                                fichier=_pdf('x.pdf'))
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('plan_x', reponse.data['piece'][0])


class RefusTest(BaseGabarits):

    def test_validation_400_sous_le_champ_nomme(self):
        pieces = PIECES + [{'code': 'cerfa', 'intitule': 'Formulaire',
                            'obligatoire': True}]
        reponse = self._deposer(pieces_attendues=json.dumps(pieces))
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('pieces_attendues[1].source_reference', reponse.data)

        word = self._deposer(fichier=SimpleUploadedFile(
            'gabarit.docx', DOCX,
            content_type='application/vnd.openxmlformats-officedocument'
                         '.wordprocessingml.document'))
        self.assertEqual(word.status_code, 400, word.data)
        self.assertIn('PDF', word.data['fichier'])
        self.assertFalse(GabaritDossierReglementaire.objects.exists())

    def test_id_d_une_autre_societe_meme_message_qu_un_id_absent(self):
        etranger = GabaritDossierReglementaire.objects.create(
            company=self.autre, pays='ma', code='voisin',
            intitule='Gabarit voisin', pieces_attendues=PIECES)
        absent = etranger.pk + 1000
        for verbe in ('get', 'patch', 'delete'):
            chez_autrui = getattr(self.api, verbe)(f'{URL}{etranger.pk}/')
            nulle_part = getattr(self.api, verbe)(f'{URL}{absent}/')
            self.assertEqual(chez_autrui.status_code, 404, verbe)
            self.assertEqual(nulle_part.status_code, 404, verbe)
            # Même message (l'enveloppe ``error`` porte un request_id propre
            # à chaque requête : seul le message est comparé).
            self.assertEqual(chez_autrui.data['detail'],
                             nulle_part.data['detail'], verbe)
        self.assertEqual(self.api.get(URL).data['gabarits'], [])
        self.assertTrue(GabaritDossierReglementaire.objects
                        .filter(pk=etranger.pk).exists())

    def test_suppression_d_un_gabarit_utilise_409_nomme(self):
        gabarit_id = self._deposer().data['gabarit']['id']
        DossierReglementaire.objects.create(
            company=self.company, calepinage=self.calepinage,
            gabarit_id=gabarit_id)
        reponse = self.api.delete(f'{URL}{gabarit_id}/')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('1 dossier', reponse.data['detail'])

        libre = self._deposer(code='libre').data['gabarit']['id']
        self.assertEqual(self.api.delete(f'{URL}{libre}/').status_code, 204)
        self.assertFalse(GabaritDossierReglementaire.objects
                         .filter(pk=libre).exists())

    def test_403_sans_calepinage_gerer(self):
        lecteur = Role.objects.create(
            company=self.company, nom='Lecteur calepinage',
            permissions=['calepinage_voir'])
        self.user_sans.role = lecteur
        self.user_sans.save(update_fields=['role'])
        api = self._client(self.user_sans)
        self.assertEqual(api.get(URL).status_code, 403)
        self.assertEqual(self._deposer(api=api).status_code, 403)
        self.assertFalse(GabaritDossierReglementaire.objects.exists())
