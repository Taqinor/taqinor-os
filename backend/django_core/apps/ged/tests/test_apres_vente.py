"""GED29 — Filage (classement) des PDF après-vente (SAV) générés.

Couvre le service `classer_document_apres_vente` + l'action thin
`documents/classer-apres-vente/` :
  * un PDF après-vente existant (par `file_key`) atterrit dans le cabinet/dossier
    « Après-vente » dédié, AUTO-CRÉÉS s'ils manquent ;
  * idempotence par (`source_type`, `source_id`) — un appel répété pour le MÊME
    objet SAV source ne duplique jamais le document ;
  * isolation société : le classement de A ne touche jamais le référentiel de B
    (cabinets/dossiers homonymes mais distincts, un par société) ;
  * chemin `file_key` (objet déjà en MinIO) vs `contenu_bytes` (octets bruts
    téléversés ici) — les deux déposent une version ;
  * sous-dossier contextuel templaté (jeton `{{ annee }}` résolu, GED28) ;
  * endpoint : société + créateur posés CÔTÉ SERVEUR, idempotence 201 → 200,
    validations (nom / source requis), isolation 404 cross-société sur la lecture.

`/proposal` (moteur premium de devis) n'est JAMAIS sollicité ici — GED29 est une
couche générique de dépôt interne, distincte (rule #4). Le câblage SAV (appel à
l'émission d'un document après-vente) est une tâche FUTURE distincte ; ici on
teste UNIQUEMENT le point d'entrée de réception côté GED.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ApresVenteBase(TestCase):
    def setUp(self):
        self.co_a = make_company('apv-a', 'APV A')
        self.co_b = make_company('apv-b', 'APV B')
        self.admin_a = make_user(self.co_a, 'apv-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'apv-admin-b', 'admin')


class ClasserApresVenteServiceTests(ApresVenteBase):
    """Service `classer_document_apres_vente` (filage côté GED)."""

    def test_file_key_atterrit_dans_le_cabinet_dossier_apres_vente(self):
        # Le cabinet/dossier « Après-vente » n'existent pas encore.
        self.assertFalse(
            Cabinet.objects.filter(
                company=self.co_a, nom='Après-vente').exists())
        doc, created = services.classer_document_apres_vente(
            company=self.co_a, file_key='attachments/sav-rapport.pdf',
            nom='Rapport intervention #42',
            source_type='sav.rapportintervention', source_id=42,
            created_by=self.admin_a)
        self.assertTrue(created)
        # Cabinet + dossier dédiés, auto-créés sous la société.
        self.assertEqual(doc.folder.cabinet.nom, 'Après-vente')
        self.assertEqual(doc.folder.nom, 'Après-vente')
        self.assertEqual(doc.company_id, self.co_a.id)
        self.assertEqual(doc.folder.company_id, self.co_a.id)
        self.assertEqual(doc.folder.cabinet.company_id, self.co_a.id)
        # Version 1 pointe vers la clé fournie (chemin `file_key`).
        version = DocumentVersion.objects.get(document=doc)
        self.assertEqual(version.file_key, 'attachments/sav-rapport.pdf')
        self.assertEqual(version.company_id, self.co_a.id)

    def test_idempotent_par_objet_source(self):
        # Deux dépôts pour le MÊME objet SAV source → un seul document.
        doc1, c1 = services.classer_document_apres_vente(
            company=self.co_a, file_key='attachments/sav1.pdf',
            nom='SAV #7', source_type='sav.ticket', source_id=7,
            created_by=self.admin_a)
        doc2, c2 = services.classer_document_apres_vente(
            company=self.co_a, file_key='attachments/sav1-bis.pdf',
            nom='SAV #7 (réémis)', source_type='sav.ticket', source_id=7,
            created_by=self.admin_a)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(doc1.pk, doc2.pk)
        self.assertEqual(
            Document.objects.filter(
                company=self.co_a,
                custom_data__contains={
                    'source_type': 'sav.ticket', 'source_id': 7}).count(),
            1)

    def test_isolation_societe(self):
        # Même objet source logique côté A et B → deux documents/cabinets distincts.
        doc_a, _ = services.classer_document_apres_vente(
            company=self.co_a, file_key='attachments/a.pdf',
            nom='A', source_type='sav.ticket', source_id=1,
            created_by=self.admin_a)
        doc_b, _ = services.classer_document_apres_vente(
            company=self.co_b, file_key='attachments/b.pdf',
            nom='B', source_type='sav.ticket', source_id=1,
            created_by=self.admin_b)
        self.assertNotEqual(doc_a.pk, doc_b.pk)
        self.assertNotEqual(doc_a.folder.cabinet_id, doc_b.folder.cabinet_id)
        self.assertEqual(doc_a.folder.cabinet.company_id, self.co_a.id)
        self.assertEqual(doc_b.folder.cabinet.company_id, self.co_b.id)

    def test_reutilise_le_cabinet_dossier_existant(self):
        # Provisionnement idempotent : deux dépôts partagent le même dossier.
        doc1, _ = services.classer_document_apres_vente(
            company=self.co_a, file_key='attachments/1.pdf',
            nom='1', source_type='sav.ticket', source_id=10,
            created_by=self.admin_a)
        doc2, _ = services.classer_document_apres_vente(
            company=self.co_a, file_key='attachments/2.pdf',
            nom='2', source_type='sav.ticket', source_id=11,
            created_by=self.admin_a)
        self.assertEqual(doc1.folder_id, doc2.folder_id)
        self.assertEqual(
            Folder.objects.filter(
                company=self.co_a, cabinet__nom='Après-vente',
                nom='Après-vente', parent__isnull=True).count(),
            1)

    def test_sous_dossier_contextuel_par_annee(self):
        # Le dossier peut porter un jeton `{{ annee }}` résolu (GED28).
        doc, _ = services.classer_document_apres_vente(
            company=self.co_a, file_key='attachments/y.pdf',
            nom='Garantie', source_type='sav.garantie', source_id=3,
            dossier='Après-vente {{ annee }}', created_by=self.admin_a)
        annee = timezone.now().year
        self.assertEqual(doc.folder.nom, f'Après-vente {annee}')
        self.assertEqual(doc.folder.cabinet.nom, 'Après-vente')

    def test_contenu_bytes_depose_une_version(self):
        # Chemin `contenu_bytes` : octets bruts stockés ici → version non vide.
        pdf = b'%PDF-1.4\n%fake apres-vente\n'
        doc, created = services.classer_document_apres_vente(
            company=self.co_a, contenu_bytes=pdf,
            nom='Bon SAV', source_type='sav.bon', source_id=99,
            created_by=self.admin_a)
        self.assertTrue(created)
        version = DocumentVersion.objects.get(document=doc)
        # Une clé de stockage a bien été attribuée (octets téléversés).
        self.assertTrue(version.file_key)
        self.assertEqual(doc.folder.cabinet.nom, 'Après-vente')


class ClasserApresVenteEndpointTests(ApresVenteBase):
    """Action thin `POST documents/classer-apres-vente/`."""

    URL = '/api/django/ged/documents/classer-apres-vente/'

    def test_endpoint_classe_et_pose_la_societe_cote_serveur(self):
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'nom': 'Rapport SAV',
            'source_type': 'sav.ticket',
            'source_id': 55,
            'file_key': 'attachments/sav-endpoint.pdf',
        }, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        doc = Document.objects.get(pk=resp.data['id'])
        self.assertEqual(doc.company_id, self.co_a.id)
        self.assertEqual(doc.created_by_id, self.admin_a.id)
        self.assertEqual(doc.folder.cabinet.nom, 'Après-vente')

    def test_endpoint_idempotent_201_puis_200(self):
        api = auth(self.admin_a)
        body = {
            'nom': 'Rapport SAV',
            'source_type': 'sav.ticket',
            'source_id': 77,
            'file_key': 'attachments/x.pdf',
        }
        r1 = api.post(self.URL, body, format='json')
        r2 = api.post(self.URL, body, format='json')
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.data['id'], r2.data['id'])

    def test_endpoint_nom_requis(self):
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'source_type': 'sav.ticket', 'source_id': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_source_requise(self):
        api = auth(self.admin_a)
        resp = api.post(self.URL, {'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_isolation_societe_sur_la_lecture(self):
        # Un document après-vente classé par A n'est pas visible côté B.
        doc, _ = services.classer_document_apres_vente(
            company=self.co_a, file_key='attachments/a.pdf',
            nom='A', source_type='sav.ticket', source_id=2,
            created_by=self.admin_a)
        api_b = auth(self.admin_b)
        resp = api_b.get(f'/api/django/ged/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 404)
