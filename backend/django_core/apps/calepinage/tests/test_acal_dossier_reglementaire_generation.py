# -*- coding: utf-8 -*-
"""ACAL240 — le dossier réglementaire est produit AVEC le gabarit déposé.

LE CONSTAT (C-ACAL-135)
-----------------------
``construire_pack_dossier`` déposait en GED la planche, la note de calcul et
le schéma — mais NI les pages du gabarit déposé par la société, NI les champs
saisis, NI les pièces jointes : le « dossier » remis n'était pas le dossier.
GET ``dossiers-reglementaires/`` ne disait pas non plus quel document GED
avait été produit, ni s'il l'avait été sur une conception depuis modifiée.

Chaîne RÉELLE : dépôt du gabarit, saisie des champs, pièce jointe et
génération par les routes HTTP réelles ; GED réelle en base de test + MinIO
de la CI ; texte extrait du PDF fusionné par PyMuPDF. Seules les pièces
PRODUITES par le module (planche, note, schéma — hors sujet ici, prouvées par
``test_acal_depot_ged_dossiers``) sont rendues par de vrais PDF minimaux.

Run :
    python manage.py test \
        apps.calepinage.tests.test_acal_dossier_reglementaire_generation -v2
"""
from __future__ import annotations

import json
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase

from apps.calepinage.models import (
    Calepinage, DossierReglementaire, GabaritDossierReglementaire,
    ParametresCalepinage,
)
from apps.calepinage.services.reglementaire import enregistrer_champs

from .test_api_liste import BaseApiCalepinage, url_detail

try:
    import fitz
except ImportError:  # pragma: no cover - dépend de l'environnement
    fitz = None

URL_GABARITS = '/api/django/calepinage/gabarits-dossiers/'
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32

CHAMPS = [
    {'code': 'puissance', 'libelle': 'Puissance (kWc)', 'type': 'nombre',
     'obligatoire': True, 'cle_calepinage': 'puissance_kwc'},
    {'code': 'commune', 'libelle': 'Commune du projet', 'type': 'texte',
     'obligatoire': False},
]
PIECES = [{'code': 'plan_masse', 'intitule': 'Plan de masse',
           'obligatoire': False,
           'source_reference': 'Cahier des charges du gestionnaire'}]


def _pdf(*textes):
    document = fitz.open()
    for texte in textes:
        page = document.new_page()
        page.insert_text((72, 72), texte)
    octets = document.tobytes()
    document.close()
    return octets


def _pages(octets):
    document = fitz.open(stream=octets, filetype='pdf')
    try:
        return [page.get_text() for page in document]
    finally:
        document.close()


def _rendus_produits(_calepinage, _company):
    return {'planche': lambda: _pdf('PLANCHE PRODUITE'),
            'note_calcul': lambda: _pdf('NOTE PRODUITE'),
            'schema_unifilaire': lambda: _pdf('SCHEMA PRODUIT')}


class BaseGeneration(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        if fitz is None:
            self.skipTest('PyMuPDF absent de cet environnement')
        ParametresCalepinage.objects.create(company=self.company,
                                            imagerie={'pays': 'ma'})
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout={})
        rendus = mock.patch(
            'apps.calepinage.services.reglementaire._rendus_du_module',
            side_effect=_rendus_produits)
        rendus.start()
        self.addCleanup(rendus.stop)

    def _deposer_gabarit(self):
        reponse = self.api.post(URL_GABARITS, {
            'pays': 'ma', 'code': 'raccordement_bt', 'genre': 'raccordement',
            'intitule': 'Dossier de raccordement BT',
            'pieces_attendues': json.dumps(PIECES),
            'champs': json.dumps(CHAMPS),
            'fichier': SimpleUploadedFile(
                'gabarit.pdf', _pdf('GABARIT ACAL240 PAGE 1',
                                    'GABARIT ACAL240 PAGE 2'),
                content_type='application/pdf'),
        }, format='multipart')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return reponse.data['gabarit']['id']

    def _saisir(self, gabarit_id, champs):
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}champs-dossier/',
            {'gabarit': gabarit_id, 'champs': champs}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def _joindre(self, gabarit_id):
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}joindre-piece/',
            {'gabarit': gabarit_id, 'piece': 'plan_masse',
             'fichier': SimpleUploadedFile(
                 'plan.pdf', _pdf('PIECE JOINTE ACAL240'),
                 content_type='application/pdf')}, format='multipart')
        self.assertEqual(reponse.status_code, 201, reponse.data)

    def _generer(self, gabarit_id):
        return self.api.post(
            f'{url_detail(self.calepinage.pk)}generer-dossier/',
            {'gabarit': gabarit_id}, format='json')

    def _dossier_servi(self, gabarit_id):
        reponse = self.api.get(
            f'{url_detail(self.calepinage.pk)}dossiers-reglementaires/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return next(d for d in reponse.data['dossiers']
                    if d['gabarit_id'] == gabarit_id)

    def _octets_du_document(self, document_id):
        from django.apps import apps as django_apps

        from apps.ged.services import selectors_latest_version
        from apps.records.storage import fetch_attachment

        Document = django_apps.get_model('ged', 'Document')
        document = Document.objects.get(pk=document_id,
                                        company=self.company)
        octets, erreur = fetch_attachment(
            selectors_latest_version(document).file_key)
        self.assertIsNone(erreur)
        return document, octets


class GenerationDossierTest(BaseGeneration):

    def test_pdf_fusionne_contient_gabarit_et_valeurs_saisies(self):
        gabarit_id = self._deposer_gabarit()
        self._saisir(gabarit_id, {'puissance': '12,5'})
        self._joindre(gabarit_id)

        reponse = self._generer(gabarit_id)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        _document, octets = self._octets_du_document(
            reponse.data['document'])

        pages = _pages(octets)
        # Ordre : gabarit (2 p.) → champs → pièce jointe → pièces produites.
        self.assertEqual(len(pages), 7, pages)
        self.assertIn('GABARIT ACAL240 PAGE 1', pages[0])
        self.assertIn('GABARIT ACAL240 PAGE 2', pages[1])
        self.assertIn('Puissance (kWc)', pages[2])
        self.assertIn('12,5', pages[2])
        self.assertIn('à compléter', pages[2])  # commune : aucune source
        self.assertIn('PIECE JOINTE ACAL240', pages[3])
        self.assertIn('PLANCHE PRODUITE', pages[4])
        self.assertIn('NOTE PRODUITE', pages[5])
        self.assertIn('SCHEMA PRODUIT', pages[6])
        # Aucun montant n'est imprimé par la page des champs.
        self.assertNotIn('MAD', pages[2])
        self.assertNotIn('DH', pages[2])

    def test_document_et_peremption_exposes(self):
        gabarit_id = self._deposer_gabarit()
        self._saisir(gabarit_id, {'puissance': '12,5'})
        avant = self._dossier_servi(gabarit_id)
        self.assertIsNone(avant['document'])
        self.assertIsNone(avant['genere_sur_conception_perimee'])

        reponse = self._generer(gabarit_id)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        document_id = reponse.data['document']

        en_base = DossierReglementaire.objects.get(pk=reponse.data['dossier'])
        self.assertEqual(en_base.document_id, document_id)
        self.assertEqual(len(en_base.genere_empreinte), 64)
        self.assertIsNotNone(en_base.genere_le)

        servi = self._dossier_servi(gabarit_id)
        self.assertEqual(servi['document'], document_id)
        self.assertIs(servi['genere_sur_conception_perimee'], False)
        champ = next(c for c in servi['champs_saisis']
                     if c['code'] == 'puissance')
        self.assertIn('valeur_calepinage', champ)
        self.assertIn('ecart_saisie', champ)

        # Régénérer SANS changement : le MÊME document GED (D-ADOC-2).
        bis = self._generer(gabarit_id)
        self.assertEqual(bis.status_code, 200, bis.data)
        self.assertEqual(bis.data['document'], document_id)

        # La conception change : le dossier généré est signalé périmé.
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            titre='Villa Anfa — retouchée')
        self.assertIs(
            self._dossier_servi(gabarit_id)['genere_sur_conception_perimee'],
            True)

    def test_gabarit_non_pdf_refuse_nomme(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Attachment
        from apps.records.storage import store_attachment

        gabarit_id = self._deposer_gabarit()
        gabarit = GabaritDossierReglementaire.objects.get(pk=gabarit_id)
        donnees, erreur = store_attachment(
            ContentFile(PNG, name='gabarit.png'), company=self.company)
        self.assertIsNone(erreur)
        gabarit.fichier = Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(gabarit),
            object_id=gabarit.pk, **donnees)
        gabarit.save(update_fields=['fichier'])
        self._saisir(gabarit_id, {'puissance': '12,5'})

        reponse = self._generer(gabarit_id)

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(list(reponse.data), ['gabarit'])
        self.assertIn("n'est pas un PDF", reponse.data['gabarit'][0])
        dossier = DossierReglementaire.objects.get(
            calepinage=self.calepinage, gabarit=gabarit)
        self.assertIsNone(dossier.document_id)
        self.assertEqual(dossier.genere_empreinte, '')


class SaisiesConcurrentesTest(TransactionTestCase):
    """Deux copies PÉRIMÉES du même dossier : aucun champ n'est perdu."""

    def test_saisies_concurrentes_ne_perdent_aucun_champ(self):
        from authentication.models import Company

        societe = Company.objects.create(nom='ACAL240', slug='acal240')
        calepinage = Calepinage.objects.create(company=societe,
                                               titre='ACAL240')
        gabarit = GabaritDossierReglementaire.objects.create(
            company=societe, pays='ma', code='dp', intitule='DP',
            champs=[dict(champ) for champ in CHAMPS])
        dossier = DossierReglementaire.objects.create(
            company=societe, calepinage=calepinage, gabarit=gabarit)
        copie_a = DossierReglementaire.objects.get(pk=dossier.pk)
        copie_b = DossierReglementaire.objects.get(pk=dossier.pk)

        enregistrer_champs(copie_a, {'puissance': '12,5'})
        enregistrer_champs(copie_b, {'commune': 'Rabat'})

        dossier.refresh_from_db()
        self.assertEqual(dossier.champs_saisis,
                         {'puissance': 12.5, 'commune': 'Rabat'})
