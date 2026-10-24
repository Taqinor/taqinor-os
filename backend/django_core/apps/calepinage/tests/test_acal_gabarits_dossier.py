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
    _gabarit_manuel_actif,
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
        self.assertIsNone(_gabarit_manuel_actif(self.company))
        reponse = self._deposer(code='manuel', genre='manuel',
                                intitule='Manuel du propriétaire',
                                pieces_attendues=json.dumps([]))
        self.assertEqual(reponse.status_code, 201, reponse.data)
        manuel = _gabarit_manuel_actif(self.company)
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

    def test_liste_json_qui_n_est_pas_une_liste_400_nommee(self):
        """CI #1021 api-fuzz (5) — ``champs=0`` / ``champs={}`` en multipart
        étaient ACCEPTÉS (201, liste vide en silence) : refus 400 nommé, rien
        n'est créé."""
        for brut in ('0', '{}', '"texte"'):
            reponse = self._deposer(champs=brut)
            self.assertEqual(reponse.status_code, 400, (brut, reponse.data))
            self.assertIn('liste JSON', reponse.data['champs'])
        # La liste envoyée en PARTIE À NOM DE FICHIER (harnais Schemathesis) :
        # lue puis validée — « 0 » refusé, « [] » accepté.
        fichier_zero = SimpleUploadedFile('champs', b'0', content_type='text/plain')
        reponse = self._deposer(champs=fichier_zero)
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('liste JSON', reponse.data['champs'])
        reponse = self._deposer(pieces_attendues='5')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('pieces_attendues', reponse.data)
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

    def test_bornes_de_colonne_400_nomme_jamais_500(self):
        # CI #993 api-fuzz-pr (Qay0Hc) : un intitulé de 201 caractères en
        # JSON (``fichier`` vide) cassait à l'INSERT (500) — 400 nommé.
        corps = {'pays': 'AA', 'code': '0', 'genre': '0',
                 'intitule': '0' * 201, 'version': '', 'actif': False,
                 'pieces_attendues': [], 'champs': []}
        reponse = self.api.post(URL, corps, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('intitule', reponse.data)
        for champ, valeur in (('pays', 123), ('code', 'pas un slug'),
                              ('intitule', {'a': 1})):
            fautif = dict(corps, intitule='Dossier')
            fautif[champ] = valeur
            refus = self.api.post(URL, fautif, format='json')
            self.assertEqual(refus.status_code, 400, (champ, refus.data))
            self.assertIn(champ, refus.data)
        self.assertFalse(GabaritDossierReglementaire.objects.exists())
        # Le même corps à intitulé borné passe (sans ``fichier``).
        ok = self.api.post(URL, dict(corps, intitule='0' * 200),
                           format='json')
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertIsNone(ok.data['gabarit']['fichiers'])

    def test_schema_publie_genre_vide_accepte(self):
        # CI #997 api-fuzz : ``genre`` vide est accepté par le serveur, le
        # motif publié doit donc l'admettre (sinon « accepted schema-violating »).
        from ..views.gabarits_dossier import _CORPS_GABARIT
        champ = _CORPS_GABARIT.fields['genre']
        self.assertEqual(champ.run_validation(''), '')
        corps = {'pays': 'AA', 'code': 'g-vide', 'genre': '',
                 'intitule': 'Dossier', 'version': ''}
        reponse = self.api.post(URL, corps, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)

    def test_fichier_vide_ou_texte_refuse_400_nomme(self):
        # ENF11 (api-fuzz « accepted schema-violating request », ``fichier=``)
        # — ``fichier`` est un fichier : une valeur de formulaire vide n'est
        # plus ignorée en silence, et rien n'est créé.
        avant = GabaritDossierReglementaire.objects.count()
        corps = {'pays': 'AA', 'code': 'zero', 'intitule': 'Zéro',
                 'fichier': ''}
        reponse = self.api.post(URL, corps, format='multipart')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('fichier', reponse.data)
        self.assertEqual(GabaritDossierReglementaire.objects.count(), avant)
        # corps JSON non objet (null, liste) : 400 nommé, jamais 500
        for brut in ('null', '[]'):
            r = self.api.post(URL, brut, content_type='application/json')
            self.assertEqual(r.status_code, 400, (brut, r.data))
        self.assertEqual(GabaritDossierReglementaire.objects.count(), avant)

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

    def test_actif_en_formulaire_true_false_seulement(self):
        # CI #997 fuzz (2) : ``actif={}`` en multipart était lu « faux » et le
        # dépôt répondait 201 ; seul un booléen (true / false) est admis.
        refus = self._deposer(actif='{}')
        self.assertEqual(refus.status_code, 400, refus.data)
        self.assertIn('actif', refus.data)
        self.assertFalse(GabaritDossierReglementaire.objects.exists())
        ok = self._deposer(actif='False')
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertFalse(ok.data['gabarit']['actif'])

    def test_elements_de_liste_exigent_code_libelle_source_fuzz_997(self):
        # CI #997 api-fuzz (3) : ``champs=[{"x": …}]`` (objet quelconque) était
        # « conforme » au schéma puis refusé 400 « Le champ n°1 doit porter un
        # code » — le schéma exige maintenant ``code`` + ``libelle`` (champ),
        # ``code`` + ``intitule`` + ``source_reference`` (pièce).
        from ..views.gabarits_dossier import _CORPS_GABARIT

        champs = _CORPS_GABARIT.fields
        for liste, requis in (
                ('champs', {'code', 'libelle'}),
                ('pieces_attendues', {'code', 'intitule', 'source_reference'})):
            element = champs[liste].child
            self.assertEqual(
                {nom for nom, f in element.fields.items() if f.required},
                requis, liste)
        for corps in ({'champs': [{'x-schemathesis-additional': [None]}]},
                      {'champs': [{'code': 'a', 'libelle': 5}]},
                      {'champs': [{'code': 'a', 'libelle': 'L', 'type': None}]},
                      {'champs': [{'code': 'a', 'libelle': 'L',
                                   'cle_calepinage': ''}]},
                      {'champs': [{'code': 'a', 'libelle': 'L',
                                   'obligatoire': 1}]},
                      {'pieces_attendues': [dict(PIECES[0], code='a\x00')]},
                      {'pieces_attendues': [dict(PIECES[0],
                                                 obligatoire=None)]},
                      {'intitule': 'Dossier\x00'}):
            refus = self.api.post(URL, dict(
                {'pays': 'ma', 'code': 'r', 'intitule': 'Dossier'}, **corps),
                format='json')
            self.assertEqual(refus.status_code, 400, (corps, refus.data))
        self.assertFalse(GabaritDossierReglementaire.objects.exists())
        conforme = self.api.post(URL, {
            'pays': 'ma', 'code': 'ok', 'intitule': 'Dossier',
            'champs': [{'code': 'a', 'libelle': 'L', 'type': 'nombre',
                        'cle_calepinage': 'adresse', 'obligatoire': True}],
            'pieces_attendues': PIECES}, format='json')
        self.assertEqual(conforme.status_code, 201, conforme.data)

    def test_deux_elements_au_meme_code_409_pas_400(self):
        # Un schéma n'exprime pas l'unicité d'une clé d'objet : un corps
        # conforme au schéma mais en doublon répond 409 (statut attendu des
        # requêtes valides), nommé sous l'élément fautif.
        doublon = [{'code': 'a', 'libelle': 'L'}, {'code': 'a', 'libelle': 'M'}]
        reponse = self.api.post(URL, {
            'pays': 'ma', 'code': 'dbl', 'intitule': 'Dossier',
            'champs': doublon}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('champs[1].code', reponse.data)
        # Un doublon + une autre faute reste un 400 (corps mal formé).
        mixte = self.api.post(URL, {
            'pays': 'x', 'code': 'dbl', 'intitule': 'Dossier',
            'champs': doublon}, format='json')
        self.assertEqual(mixte.status_code, 400, mixte.data)
        self.assertFalse(GabaritDossierReglementaire.objects.exists())
