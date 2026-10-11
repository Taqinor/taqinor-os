"""ADOC68 — Le PDF signé est produit UNE fois à la complétion (aplati +
scellé), stocké comme version figée référencée par la demande et servi tel
quel par pdf-signe ; les champs d'une demande close ne se modifient plus et
aucune version ne s'ajoute pendant une signature en attente.

Sources réelles : services GED, vues publiques et authentifiées, stockage
MinIO de test réel ; aucun mock interne.
"""
import hashlib

import fitz

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    CHAMP_TYPE_TEXTE, Cabinet, ChampSignature, Document, Folder,
)

User = get_user_model()


def _vrai_pdf():
    """Vrai PDF d'une page (que `fitz.open` accepte), contrairement à un
    faux en-tête : la branche « version aplatie ajoutée » est ainsi prise."""
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), 'Contrat ADOC68')
    octets = doc.tobytes()
    doc.close()
    return octets


def _texte_pdf(octets):
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        return ''.join(page.get_text() for page in doc)
    finally:
        doc.close()


CONTENU = _vrai_pdf()


def _sha(octets):
    return hashlib.sha256(octets).hexdigest()


class SignatureFigeeBase(TestCase):
    def setUp(self):
        self.co_a, _ = Company.objects.get_or_create(
            slug='adoc68-a', defaults={'nom': 'Adoc68 A'})
        self.admin = User.objects.create_user(
            username='adoc68-admin', password='x', company=self.co_a,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co_a, nom='Admin')
        folder = Folder.objects.create(
            company=self.co_a, cabinet=cab, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=folder, nom='Contrat ADOC68')
        key, _meta = services._store_bytes(CONTENU, mime='application/pdf')
        services.add_version(
            self.doc, file_key=key, company=self.co_a, filename='c.pdf',
            size=len(CONTENU), mime='application/pdf',
            checksum=_sha(CONTENU))
        self.demande = services.demander_signature(
            self.doc, signataire_nom='Client', signataire_email='c@x.ma',
            company=self.co_a)
        self.champ = ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, requis=True)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.anon = APIClient()

    def _signer(self):
        resp = self.anon.post(
            f'/api/django/ged/signature/{self.demande.token}/', {
                'action': 'signer', 'consentement': True,
                'signature_texte': 'Client',
                'valeurs_champs': {str(self.champ.id): 'ORIGINAL'}},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.demande.refresh_from_db()

    def _pdf_signe(self):
        resp = self.api.get(
            f'/api/django/ged/demandes-signature/{self.demande.pk}/pdf-signe/')
        self.assertEqual(resp.status_code, 200)
        return resp.content

    def _poster_version(self, octets):
        # ASEC37 — la version arrive comme fichier téléversé (multipart).
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.api.post('/api/django/ged/versions/', {
            'document': self.doc.pk,
            'file': SimpleUploadedFile(
                'v.pdf', octets, content_type='application/pdf')},
            format='multipart')


class SignatureFigeeTests(SignatureFigeeBase):
    def test_champ_non_modifiable_apres_signature(self):
        self._signer()
        resp = self.api.patch(
            f'/api/django/ged/champs-signature/{self.champ.pk}/',
            {'valeur': 'FALSIFIE'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.champ.refresh_from_db()
        self.assertEqual(self.champ.valeur, 'ORIGINAL')
        self.assertEqual(self.api.delete(
            f'/api/django/ged/champs-signature/{self.champ.pk}/').status_code,
            409)

    def test_version_refusee_pendant_signature(self):
        resp = self._poster_version(b'%PDF-1.4\n%autre\n' + b'X' * 50)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(self.doc.versions.count(), 1)

    def test_nouvelle_version_refusee_pendant_signature(self):
        """ADOC175 — l'action « Nouvelle version » est gardée comme `versions`."""
        from unittest import mock
        from django.core.files.uploadedfile import SimpleUploadedFile
        url = f'/api/django/ged/documents/{self.doc.pk}/nouvelle-version/'
        octets = b'%PDF-1.4\n%autre\n' + b'X' * 50
        with mock.patch('apps.ged.views.store_attachment') as stocke:
            resp = self.api.post(url, {'file': SimpleUploadedFile(
                'v.pdf', octets, content_type='application/pdf')},
                format='multipart')
            self.assertEqual(resp.status_code, 409, resp.data)
            self.assertIn('signature est en cours', resp.data['detail'])
            stocke.assert_not_called()
        self.assertEqual(self.doc.versions.count(), 1)

    def test_generer_refuse_pendant_signature(self):
        """ADOC178 (sonde C-ADOC-VER-006) — « Générer depuis un modèle »
        après modification du modèle ne versionne pas un document dont une
        signature est en attente (409, même refus que ADOC175) ; une fois la
        demande close, la régénération ajoute v2."""
        from apps.ged.models import ModeleDocument, SIGNATURE_ANNULE
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Attestation',
            corps_html='<p>Attestation {{ nom }}</p>')
        url = f'/api/django/ged/modeles-document/{modele.pk}/generer/'
        corps = {'contexte': {'nom': 'ALPHA'}}
        resp = self.api.post(url, corps, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        genere = Document.objects.get(pk=resp.data['document'])
        demande = services.demander_signature(
            genere, signataire_nom='Client', signataire_email='c@x.ma',
            company=self.co_a)
        modele.corps_html = '<p>Attestation corrigée {{ nom }}</p>'
        modele.save()
        resp = self.api.post(url, corps, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['detail'], (
            "Une demande de signature est en cours sur ce document : "
            "aucune nouvelle version tant qu'elle n'est pas close."))
        self.assertEqual(genere.versions.count(), 1)
        demande.statut = SIGNATURE_ANNULE
        demande.save(update_fields=['statut'])
        resp = self.api.post(url, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['document'], genere.pk)
        self.assertEqual(genere.versions.count(), 2)

    def test_editeur_office_refuse_pendant_signature(self):
        with self.settings(GED_OFFICE_URL='http://office.test'):
            with self.assertRaises(services.SignatureEnCoursError):
                services.sauvegarder_depuis_editeur_office(
                    self.doc, contenu_bytes=b'%PDF-1.4\n%o\n' + b'Z' * 50,
                    user=self.admin, filename='o.pdf')
        self.assertEqual(self.doc.versions.count(), 1)

    def test_pdf_signe_stable_apres_nouvelle_version(self):
        self._signer()
        self.assertIsNotNone(self.demande.version_signee_id)
        avant = self._pdf_signe()
        self.assertEqual(_sha(avant), self.demande.hash_contenu)
        self.assertEqual(
            _sha(avant), self.demande.version_signee.checksum)
        # Après signature, une nouvelle version reste permise…
        resp = self._poster_version(b'%PDF-1.4\n%v2\n' + b'Y' * 50)
        self.assertEqual(resp.status_code, 201, resp.data)
        # …mais le PDF signé servi ne change jamais.
        apres = self._pdf_signe()
        self.assertEqual(avant, apres)
        self.demande.refresh_from_db()
        self.assertEqual(_sha(apres), self.demande.hash_contenu)

    def test_version_signee_est_une_nouvelle_version_aplatie(self):
        v1 = self.doc.versions.get()
        self._signer()
        self.assertIsNotNone(self.demande.version_signee_id)
        self.assertNotEqual(self.demande.version_signee_id, v1.pk)
        self.assertEqual(self.doc.versions.count(), 2)
        figee = self.doc.versions.order_by('-version').first()
        self.assertEqual(figee.pk, self.demande.version_signee_id)
        self.assertGreater(figee.version, v1.version)
        self.assertNotEqual(figee.checksum, v1.checksum)
        fige = self._pdf_signe()
        self.assertIn('ORIGINAL', _texte_pdf(fige))
        self.assertNotIn('ORIGINAL', _texte_pdf(CONTENU))

    def test_classement_de_la_version_aplatie(self):
        self._signer()
        fige = self._pdf_signe()
        self.assertNotEqual(_sha(fige), _sha(CONTENU))
        classe = Document.objects.get(
            company=self.co_a, folder__nom='Signés',
            custom_data__source_type='ged.demandesignaturedocument.document')
        derniere = classe.versions.order_by('-version').first()
        self.assertEqual(derniere.checksum, _sha(fige))
        from apps.records.storage import fetch_attachment
        octets, err = fetch_attachment(derniere.file_key)
        self.assertIsNone(err)
        self.assertIn('ORIGINAL', _texte_pdf(octets))
