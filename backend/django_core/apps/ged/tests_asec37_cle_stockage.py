"""ASEC37 — la GED n'accepte plus du client une clé de stockage.

Constat C-ASEC-008 volet GED : ``POST /ged/versions/`` acceptait une
``file_key``/``checksum`` du corps, puis l'aperçu servait les octets de cette
clé — y compris le fichier d'une autre société. Attendu : seule une version
TÉLÉVERSÉE dans la requête est acceptée (clé produite par le serveur sous le
préfixe de la société) ; aucune lecture ne sert une clé portant l'id d'une
autre société ; ``classer-apres-vente`` refuse une clé étrangère ; les clés
plates déjà enregistrées chez A restent lisibles.

MinIO de la pile de test réel ; aucun mock interne.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'
PDF = b'%PDF-1.4\n%asec37\n' + b'A' * 64


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _pdf(nom='v.pdf', octets=PDF):
    return SimpleUploadedFile(nom, octets, content_type='application/pdf')


class CleStockageGedTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ASEC37 A', slug='asec37-a')
        self.b = Company.objects.create(nom='ASEC37 B', slug='asec37-b')
        self.user = User.objects.create_user(
            username='asec37_a', password='x', role_legacy='admin',
            company=self.a)
        cab = Cabinet.objects.create(company=self.a, nom='Cab A')
        self.folder = Folder.objects.create(
            company=self.a, cabinet=cab, nom='Racine A')
        self.doc = Document.objects.create(
            company=self.a, folder=self.folder, nom='Contrat A')
        self.cle_b = f'attachments/{self.b.pk}/secret-b.pdf'
        self.api = _api(self.user)

    def test_file_key_du_corps_ignore(self):
        # Sans fichier téléversé : refus, aucune version.
        r = self.api.post(f'{BASE}versions/', {
            'document': self.doc.pk, 'file_key': self.cle_b,
            'checksum': 'x'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self.doc.versions.count(), 0)
        # Avec un fichier : la clé du corps est ignorée.
        r2 = self.api.post(f'{BASE}versions/', {
            'document': self.doc.pk, 'file': _pdf(),
            'file_key': self.cle_b, 'checksum': 'faux'}, format='multipart')
        self.assertEqual(r2.status_code, 201, r2.content)
        version = DocumentVersion.objects.get(pk=r2.data['id'])
        self.assertNotEqual(version.file_key, self.cle_b)
        self.assertEqual(version.checksum, services.compute_checksum(PDF))
        self.assertFalse(DocumentVersion.objects.filter(
            document=self.doc, file_key=self.cle_b).exists())

    def test_version_legitime_prefixe_societe(self):
        r = self.api.post(f'{BASE}versions/', {
            'document': self.doc.pk, 'file': _pdf()}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        version = DocumentVersion.objects.get(pk=r.data['id'])
        self.assertTrue(
            version.file_key.startswith(f'attachments/{self.a.pk}/'),
            version.file_key)

    def test_apercu_cle_etrangere_refuse(self):
        # Ligne historique injectée avant le correctif (clé de B sur un
        # document de A) : l'aperçu ne sert jamais ces octets.
        version = services.add_version(
            self.doc, file_key=self.cle_b, company=self.a,
            filename='b.pdf', mime='application/pdf', uploaded_by=self.user)
        r = self.api.get(f'{BASE}versions/{version.pk}/apercu/')
        self.assertEqual(r.status_code, 404, r.content)
        self.assertNotIn(b'%PDF', r.content)

    def test_classer_apres_vente_cle_etrangere_refuse(self):
        avant = Document.objects.count()
        for cle in (self.cle_b, 'attachments/jamais-vue-chez-a.pdf'):
            with self.subTest(cle=cle):
                r = self.api.post(f'{BASE}documents/classer-apres-vente/', {
                    'nom': 'Rapport', 'source_type': 'sav.ticket',
                    'source_id': 9, 'file_key': cle}, format='json')
                self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(Document.objects.count(), avant)
        r_ok = self.api.post(f'{BASE}documents/classer-apres-vente/', {
            'nom': 'Rapport', 'source_type': 'sav.ticket', 'source_id': 9,
            'file_key': f'attachments/{self.a.pk}/rapport.pdf'},
            format='json')
        self.assertEqual(r_ok.status_code, 201, r_ok.content)

    def test_depot_lot_cle_etrangere_refuse(self):
        r = self.api.post(f'{BASE}documents/scan-lot/', {
            'folder': self.folder.pk, 'files': [_pdf('s1.pdf')],
            'file_key': self.cle_b}, format='multipart')
        self.assertIn(r.status_code, (200, 201), r.content)
        cles = list(DocumentVersion.objects.filter(
            company=self.a).values_list('file_key', flat=True))
        self.assertTrue(cles)
        self.assertNotIn(self.cle_b, cles)
        for cle in cles:
            self.assertTrue(cle.startswith(f'attachments/{self.a.pk}/'), cle)

    def test_cle_plate_existante_de_A_lisible(self):
        cle_plate, _meta = services._store_bytes(PDF, mime='application/pdf')
        self.assertIsNone(services._RE_CLE_SOCIETE.match(cle_plate))
        version = services.add_version(
            self.doc, file_key=cle_plate, company=self.a,
            filename='plate.pdf', mime='application/pdf',
            uploaded_by=self.user)
        r = self.api.get(f'{BASE}versions/{version.pk}/apercu/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(b''.join(r.streaming_content
                                 if hasattr(r, 'streaming_content')
                                 else [r.content]).startswith(b'%PDF'))
