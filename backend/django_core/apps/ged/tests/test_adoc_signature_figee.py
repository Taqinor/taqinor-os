"""ADOC68 — Le PDF signé est produit UNE fois à la complétion (aplati +
scellé), stocké comme version figée référencée par la demande et servi tel
quel par pdf-signe ; les champs d'une demande close ne se modifient plus et
aucune version ne s'ajoute pendant une signature en attente.

Sources réelles : services GED, vues publiques et authentifiées, stockage
MinIO de test réel ; aucun mock interne.
"""
import hashlib

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

CONTENU = b'%PDF-1.4\n%adoc68\n' + b'D' * 100


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

    def test_classement_de_la_version_aplatie(self):
        self._signer()
        fige = self._pdf_signe()
        classe = Document.objects.get(
            company=self.co_a, folder__nom='Signés',
            custom_data__source_type='ged.demandesignaturedocument.document')
        self.assertEqual(
            classe.versions.order_by('-version').first().checksum, _sha(fige))
