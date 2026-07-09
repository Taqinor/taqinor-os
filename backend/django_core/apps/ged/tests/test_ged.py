"""Tests du module GED (gestion documentaire) — GED1/GED2/GED3.

Couvre :
  * isolation par société (A ne voit/touche pas B) ;
  * société posée côté serveur (jamais lue du corps de requête) ;
  * Cabinet + Folder arborescent avec CHEMIN MATÉRIALISÉ (path) et sous-arbre ;
  * déplacement de dossier (recalcul des chemins, refus de cycle) ;
  * Document + DocumentVersion (numérotation auto, checksum/dedup).
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.records.models import Attachment
from apps.ged import selectors, services
from apps.ged.models import (
    AclGed, ArchivageLegal, ArchivageLegalError, Cabinet, Coffre,
    DemandeApprobation, Document, DocumentChunk, DocumentLien, DocumentTag,
    DocumentTagAssignment, DocumentVersion, Folder, PartageGed,
    PolitiqueRetention, RETENTION_SIGNALER, RETENTION_SUPPRIMER,
)
from apps.roles.models import Role

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class GedBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co_a = make_company('ged-a', 'Ged A')
        cls.co_b = make_company('ged-b', 'Ged B')
        cls.admin_a = make_user(cls.co_a, 'ged-admin-a', 'admin')
        cls.admin_b = make_user(cls.co_b, 'ged-admin-b', 'admin')
        cls.cab_a = Cabinet.objects.create(company=cls.co_a, nom='Administratif')
        cls.cab_b = Cabinet.objects.create(company=cls.co_b, nom='Administratif')


# ── GED1 — squelette + scoping société ──────────────────────────────
class CabinetTests(GedBase):
    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/cabinets/', {
            'nom': 'Technique',
            # Tentative d'injecter une autre société — doit être ignorée.
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cab = Cabinet.objects.get(id=resp.data['id'])
        self.assertEqual(cab.company_id, self.co_a.id)

    def test_tenant_isolation_list(self):
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/cabinets/')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Administratif', noms)
        # Une seule armoire (celle de A) — pas celle de B.
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.cab_a.id, ids)
        self.assertNotIn(self.cab_b.id, ids)

    def test_cannot_retrieve_other_company_cabinet(self):
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/cabinets/{self.cab_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_requires_auth(self):
        resp = APIClient().get('/api/django/ged/cabinets/')
        self.assertIn(resp.status_code, (401, 403))


# ── GED2 — Folder arborescent + chemin matérialisé ──────────────────
class FolderPathTests(GedBase):
    def test_root_folder_path(self):
        f = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Racine')
        f.refresh_from_db()
        self.assertEqual(f.path, f'/{f.pk}/')

    def test_materialized_path_chain(self):
        a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        c = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=b, nom='C')
        a.refresh_from_db()
        b.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual(a.path, f'/{a.pk}/')
        self.assertEqual(b.path, f'/{a.pk}/{b.pk}/')
        self.assertEqual(c.path, f'/{a.pk}/{b.pk}/{c.pk}/')

    def test_descendants_via_path(self):
        a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        c = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=b, nom='C')
        # Soeur d'un autre arbre — ne doit PAS apparaître dans les descendants de A.
        Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Autre')
        a.refresh_from_db()
        desc_ids = set(a.descendants().values_list('id', flat=True))
        self.assertEqual(desc_ids, {b.id, c.id})

    def test_descendants_endpoint(self):
        a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/dossiers/{a.id}/descendants/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([r['id'] for r in resp.data], [b.id])

    def test_create_folder_force_company_and_path(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/dossiers/', {
            'cabinet': self.cab_a.id, 'nom': 'Contrats',
            'company': self.co_b.id,  # injection ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        f = Folder.objects.get(id=resp.data['id'])
        self.assertEqual(f.company_id, self.co_a.id)
        self.assertEqual(f.path, f'/{f.pk}/')

    def test_folder_rejects_foreign_cabinet(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/dossiers/', {
            'cabinet': self.cab_b.id, 'nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_folder_rejects_parent_in_other_cabinet(self):
        cab_a2 = Cabinet.objects.create(company=self.co_a, nom='RH')
        parent = Folder.objects.create(
            company=self.co_a, cabinet=cab_a2, nom='Parent RH')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/dossiers/', {
            'cabinet': self.cab_a.id, 'parent': parent.id, 'nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_folder_tenant_isolation(self):
        Folder.objects.create(company=self.co_b, cabinet=self.cab_b, nom='Secret B')
        mine = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Mien A')
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/dossiers/')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(mine.id, ids)
        self.assertEqual(len(ids), 1)


# ── GED2 — déplacement de dossier (recalcul du chemin) ──────────────
class FolderMoveTests(GedBase):
    def test_move_reparents_and_recomputes_subtree_paths(self):
        a = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        c = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=b, nom='C')
        new_root = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Nouveau')
        services.move_folder(b, new_root)
        b.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual(b.path, f'/{new_root.pk}/{b.pk}/')
        # Le descendant C suit le nouveau préfixe de B.
        self.assertEqual(c.path, f'/{new_root.pk}/{b.pk}/{c.pk}/')

    def test_move_to_root(self):
        a = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        services.move_folder(b, None)
        b.refresh_from_db()
        self.assertIsNone(b.parent_id)
        self.assertEqual(b.path, f'/{b.pk}/')

    def test_move_rejects_cycle(self):
        a = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        a.refresh_from_db()
        # Déplacer A sous son propre descendant B → cycle, refusé.
        with self.assertRaises(ValueError):
            services.move_folder(a, b)

    def test_move_document_service(self):
        f1 = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F1')
        f2 = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F2')
        doc = Document.objects.create(company=self.co_a, folder=f1, nom='D')
        services.move_document(doc, f2)
        doc.refresh_from_db()
        self.assertEqual(doc.folder_id, f2.id)

    def test_move_document_rejects_other_company_folder(self):
        f1 = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F1')
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='F B')
        doc = Document.objects.create(company=self.co_a, folder=f1, nom='D')
        with self.assertRaises(ValueError):
            services.move_document(doc, folder_b)


# ── GED4 — CRUD + déplacement via l'API (scopé société) ─────────────
class GedCrudTests(GedBase):
    """CRUD complet (update/delete) pour dossiers et documents, scopé société."""

    def test_update_folder_scoped(self):
        f = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='Avant')
        api = auth(self.admin_a)
        resp = api.patch(f'/api/django/ged/dossiers/{f.id}/', {
            'nom': 'Après',
            'company': self.co_b.id,  # injection ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        f.refresh_from_db()
        self.assertEqual(f.nom, 'Après')
        self.assertEqual(f.company_id, self.co_a.id)

    def test_cannot_update_other_company_folder(self):
        f_b = Folder.objects.create(company=self.co_b, cabinet=self.cab_b, nom='B')
        api = auth(self.admin_a)
        resp = api.patch(f'/api/django/ged/dossiers/{f_b.id}/', {
            'nom': 'Piraté',
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_delete_folder_scoped(self):
        f = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='Jetable')
        api = auth(self.admin_a)
        resp = api.delete(f'/api/django/ged/dossiers/{f.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Folder.objects.filter(id=f.id).exists())

    def test_cannot_delete_other_company_folder(self):
        f_b = Folder.objects.create(company=self.co_b, cabinet=self.cab_b, nom='B')
        api = auth(self.admin_a)
        resp = api.delete(f'/api/django/ged/dossiers/{f_b.id}/')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Folder.objects.filter(id=f_b.id).exists())

    def test_update_document_scoped(self):
        f = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F')
        doc = Document.objects.create(company=self.co_a, folder=f, nom='Avant')
        api = auth(self.admin_a)
        resp = api.patch(f'/api/django/ged/documents/{doc.id}/', {
            'nom': 'Après',
            'company': self.co_b.id,  # injection ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        doc.refresh_from_db()
        self.assertEqual(doc.nom, 'Après')
        self.assertEqual(doc.company_id, self.co_a.id)

    def test_cannot_update_other_company_document(self):
        f_b = Folder.objects.create(company=self.co_b, cabinet=self.cab_b, nom='F B')
        doc_b = Document.objects.create(company=self.co_b, folder=f_b, nom='B')
        api = auth(self.admin_a)
        resp = api.patch(f'/api/django/ged/documents/{doc_b.id}/', {
            'nom': 'Piraté',
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_delete_document_scoped(self):
        f = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F')
        doc = Document.objects.create(company=self.co_a, folder=f, nom='Jetable')
        api = auth(self.admin_a)
        resp = api.delete(f'/api/django/ged/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 204)
        # GED26 — le DELETE met désormais en corbeille (soft-delete) : la ligne
        # subsiste avec supprime_le posé et disparaît de la liste par défaut.
        doc.refresh_from_db()
        self.assertIsNotNone(doc.supprime_le)


# ── GED4 — déplacement via l'API (action `deplacer`, scopé société) ──
class GedMoveEndpointTests(GedBase):
    def test_move_folder_endpoint_reparents(self):
        a = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        new_root = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Nouveau')
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/dossiers/{b.id}/deplacer/', {
            'parent': new_root.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        b.refresh_from_db()
        self.assertEqual(b.parent_id, new_root.id)
        self.assertEqual(b.path, f'/{new_root.pk}/{b.pk}/')

    def test_move_folder_endpoint_to_root(self):
        a = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/dossiers/{b.id}/deplacer/', {
            'parent': None,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        b.refresh_from_db()
        self.assertIsNone(b.parent_id)
        self.assertEqual(b.path, f'/{b.pk}/')

    def test_move_folder_endpoint_rejects_cycle(self):
        a = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='A')
        b = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, parent=a, nom='B')
        api = auth(self.admin_a)
        # Déplacer A sous son propre descendant B → cycle → 400.
        resp = api.post(f'/api/django/ged/dossiers/{a.id}/deplacer/', {
            'parent': b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_move_folder_endpoint_rejects_other_company_parent(self):
        b_parent = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Parent B')
        a = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='A')
        api = auth(self.admin_a)
        # Le parent appartient à la société B → introuvable côté A → 404.
        resp = api.post(f'/api/django/ged/dossiers/{a.id}/deplacer/', {
            'parent': b_parent.id,
        }, format='json')
        self.assertEqual(resp.status_code, 404)
        a.refresh_from_db()
        self.assertIsNone(a.parent_id)

    def test_cannot_move_other_company_folder(self):
        b_folder = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='B')
        a_target = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Cible A')
        api = auth(self.admin_a)
        # Le dossier source appartient à B → introuvable côté A → 404.
        resp = api.post(f'/api/django/ged/dossiers/{b_folder.id}/deplacer/', {
            'parent': a_target.id,
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_move_document_endpoint(self):
        f1 = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F1')
        f2 = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F2')
        doc = Document.objects.create(company=self.co_a, folder=f1, nom='D')
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/documents/{doc.id}/deplacer/', {
            'folder': f2.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        doc.refresh_from_db()
        self.assertEqual(doc.folder_id, f2.id)
        self.assertEqual(doc.company_id, self.co_a.id)

    def test_move_document_endpoint_rejects_other_company_folder(self):
        f1 = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F1')
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='F B')
        doc = Document.objects.create(company=self.co_a, folder=f1, nom='D')
        api = auth(self.admin_a)
        # Le dossier cible appartient à B → introuvable côté A → 404.
        resp = api.post(f'/api/django/ged/documents/{doc.id}/deplacer/', {
            'folder': folder_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 404)
        doc.refresh_from_db()
        self.assertEqual(doc.folder_id, f1.id)

    def test_cannot_move_other_company_document(self):
        f_b = Folder.objects.create(company=self.co_b, cabinet=self.cab_b, nom='F B')
        doc_b = Document.objects.create(company=self.co_b, folder=f_b, nom='B')
        target_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Cible A')
        api = auth(self.admin_a)
        # Le document source appartient à B → introuvable côté A → 404.
        resp = api.post(f'/api/django/ged/documents/{doc_b.id}/deplacer/', {
            'folder': target_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_move_document_endpoint_requires_folder(self):
        f1 = Folder.objects.create(company=self.co_a, cabinet=self.cab_a, nom='F1')
        doc = Document.objects.create(company=self.co_a, folder=f1, nom='D')
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/documents/{doc.id}/deplacer/', {},
                        format='json')
        self.assertEqual(resp.status_code, 400)


# ── GED3 — Document + DocumentVersion (numérotation, checksum/dedup) ──
class DocumentVersionTests(GedBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Docs A')
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Facture CIN')

    def test_create_document_force_company_and_creator(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'nom': 'Contrat',
            'company': self.co_b.id,  # injection ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = Document.objects.get(id=resp.data['id'])
        self.assertEqual(doc.company_id, self.co_a.id)
        self.assertEqual(doc.created_by_id, self.admin_a.id)

    def test_document_rejects_foreign_folder(self):
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/', {
            'folder': folder_b.id, 'nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_version_number_auto_increments(self):
        api = auth(self.admin_a)
        r1 = api.post('/api/django/ged/versions/', {
            'document': self.doc_a.id, 'file_key': 'attachments/a.pdf',
            'checksum': 'aaa', 'company': self.co_b.id,  # injection ignorée
        }, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r1.data['version'], 1)
        r2 = api.post('/api/django/ged/versions/', {
            'document': self.doc_a.id, 'file_key': 'attachments/b.pdf',
            'checksum': 'bbb',
        }, format='json')
        self.assertEqual(r2.data['version'], 2)
        v = DocumentVersion.objects.get(id=r1.data['id'])
        # company + uploaded_by posés côté serveur.
        self.assertEqual(v.company_id, self.co_a.id)
        self.assertEqual(v.uploaded_by_id, self.admin_a.id)

    def test_version_rejects_foreign_document(self):
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/versions/', {
            'document': doc_b.id, 'file_key': 'attachments/x.pdf',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_checksum_compute_and_dedup(self):
        data = b'hello world'
        cs = services.compute_checksum(data)
        # SHA-256 stable.
        self.assertEqual(len(cs), 64)
        services.add_version(
            self.doc_a, file_key='attachments/h.pdf', company=self.co_a,
            checksum=cs, uploaded_by=self.admin_a)
        # find_duplicate retrouve la version par empreinte (dedup).
        dup = services.find_duplicate(self.co_a, cs)
        self.assertIsNotNone(dup)
        self.assertEqual(dup.checksum, cs)
        # Une société différente ne voit pas l'empreinte de A.
        self.assertIsNone(services.find_duplicate(self.co_b, cs))

    def test_version_tenant_isolation(self):
        services.add_version(
            self.doc_a, file_key='attachments/a.pdf', company=self.co_a,
            checksum='x', uploaded_by=self.admin_a)
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        services.add_version(
            doc_b, file_key='attachments/b.pdf', company=self.co_b,
            checksum='y', uploaded_by=self.admin_b)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/versions/')
        keys = [r['file_key'] for r in rows(resp)]
        self.assertIn('attachments/a.pdf', keys)
        self.assertNotIn('attachments/b.pdf', keys)

    def test_document_serializer_version_summary(self):
        services.add_version(
            self.doc_a, file_key='attachments/a.pdf', company=self.co_a,
            checksum='x', uploaded_by=self.admin_a)
        services.add_version(
            self.doc_a, file_key='attachments/b.pdf', company=self.co_a,
            checksum='y', uploaded_by=self.admin_a)
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc_a.id}/')
        self.assertEqual(resp.data['version_count'], 2)
        self.assertEqual(resp.data['derniere_version'], 2)


# ── GED6 — liaison polymorphe Document ↔ objet métier ────────────────
class DocumentLienTests(GedBase):
    """Lien polymorphe Document ↔ objet métier autorisé (records.ALLOWED_TARGETS).

    Couvre : lier un document à une cible autorisée, reverse-lookup (documents
    pour un objet), isolation multi-tenant, et rejet d'un type de cible non
    autorisé / cible hors société.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Docs A')
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Contrat')
        cls.client_a = Client.objects.create(company=cls.co_a, nom='Client A')

    def test_link_document_to_allowed_target(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/liens/', {
            'document': self.doc_a.id,
            'model': 'crm.client', 'id': self.client_a.id,
            'company': self.co_b.id,  # injection ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['target_model'], 'crm.client')
        self.assertEqual(resp.data['target_id'], self.client_a.id)
        lien = DocumentLien.objects.get(id=resp.data['id'])
        # company + created_by posés côté serveur.
        self.assertEqual(lien.company_id, self.co_a.id)
        self.assertEqual(lien.created_by_id, self.admin_a.id)
        self.assertEqual(lien.document_id, self.doc_a.id)

    def test_link_is_idempotent(self):
        api = auth(self.admin_a)
        payload = {'document': self.doc_a.id,
                   'model': 'crm.client', 'id': self.client_a.id}
        r1 = api.post('/api/django/ged/liens/', payload, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = api.post('/api/django/ged/liens/', payload, format='json')
        # Deuxième POST identique : pas de doublon, 200 (lien existant renvoyé).
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(DocumentLien.objects.filter(
            document=self.doc_a, object_id=self.client_a.id).count(), 1)

    def test_reverse_lookup_documents_for_object_endpoint(self):
        DocumentLien.objects.create(
            company=self.co_a, document=self.doc_a,
            content_type=ContentType.objects.get_for_model(Client),
            object_id=self.client_a.id, created_by=self.admin_a)
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/ged/liens/?model=crm.client&id={self.client_a.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['document'], self.doc_a.id)

    def test_reverse_lookup_selector(self):
        DocumentLien.objects.create(
            company=self.co_a, document=self.doc_a,
            content_type=ContentType.objects.get_for_model(Client),
            object_id=self.client_a.id, created_by=self.admin_a)
        docs = selectors.documents_for_target(self.co_a, self.client_a)
        self.assertEqual([d.id for d in docs], [self.doc_a.id])
        liens = selectors.liens_for_target(self.co_a, self.client_a)
        self.assertEqual(liens.count(), 1)
        # Une autre société ne voit pas le lien.
        self.assertEqual(
            selectors.documents_for_target(self.co_b, self.client_a).count(), 0)

    def test_reject_disallowed_target_type(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/liens/', {
            'document': self.doc_a.id,
            # `authentication.company` n'est pas dans ALLOWED_TARGETS.
            'model': 'authentication.company', 'id': self.co_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(DocumentLien.objects.exists())

    def test_reject_target_in_other_company(self):
        client_b = Client.objects.create(company=self.co_b, nom='Client B')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/liens/', {
            'document': self.doc_a.id,
            'model': 'crm.client', 'id': client_b.id,
        }, format='json')
        # La cible appartient à B → rejetée côté A (jamais de fuite cross-société).
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(DocumentLien.objects.exists())

    def test_reject_other_company_document(self):
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/liens/', {
            'document': doc_b.id,
            'model': 'crm.client', 'id': self.client_a.id,
        }, format='json')
        # Le document appartient à B → introuvable côté A → 404.
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(DocumentLien.objects.exists())

    def test_list_tenant_isolation(self):
        # Lien de A.
        DocumentLien.objects.create(
            company=self.co_a, document=self.doc_a,
            content_type=ContentType.objects.get_for_model(Client),
            object_id=self.client_a.id, created_by=self.admin_a)
        # Lien de B (autre société).
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        client_b = Client.objects.create(company=self.co_b, nom='Client B')
        DocumentLien.objects.create(
            company=self.co_b, document=doc_b,
            content_type=ContentType.objects.get_for_model(Client),
            object_id=client_b.id, created_by=self.admin_b)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/liens/')
        ids = [r['document'] for r in rows(resp)]
        self.assertIn(self.doc_a.id, ids)
        self.assertNotIn(doc_b.id, ids)
        self.assertEqual(len(ids), 1)

    def test_link_document_to_fournisseur(self):
        """DC33 — un document GED peut pointer un fournisseur (ContentType)."""
        from apps.stock.models import Fournisseur
        four = Fournisseur.objects.create(company=self.co_a, nom='Four A')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/liens/', {
            'document': self.doc_a.id,
            'model': 'stock.fournisseur', 'id': four.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lien = DocumentLien.objects.get(id=resp.data['id'])
        self.assertEqual(lien.company_id, self.co_a.id)
        self.assertEqual(lien.object_id, four.id)

    def test_link_document_to_employe(self):
        """DC33 — un document GED peut pointer une fiche employé (ContentType)."""
        from apps.rh.models import DossierEmploye
        emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='M-001', nom='Doe', prenom='Jane')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/liens/', {
            'document': self.doc_a.id,
            'model': 'rh.dossieremploye', 'id': emp.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lien = DocumentLien.objects.get(id=resp.data['id'])
        self.assertEqual(lien.company_id, self.co_a.id)
        self.assertEqual(lien.object_id, emp.id)


# ── GED7 — import des records.Attachment existants dans la GED ──────
class MigrateAttachmentsToGedTests(GedBase):
    """GED7 — `migrate_attachments_to_ged` : import idempotent des pièces jointes.

    Couvre : création de Document réutilisant le file_key (aucun fichier
    recopié), pose du DocumentLien quand la cible est autorisée, idempotence
    (re-lancer ne duplique rien), isolation multi-tenant, originaux intacts,
    cabinet/dossier d'atterrissage par défaut, et le mode --dry-run.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.client_a = Client.objects.create(company=cls.co_a, nom='Client A')
        cls.client_b = Client.objects.create(company=cls.co_b, nom='Client B')
        ct_client = ContentType.objects.get_for_model(Client)
        # Pièce jointe de A ciblant un client autorisé (→ doit donner un lien).
        cls.att_a = Attachment.objects.create(
            company=cls.co_a, content_type=ct_client,
            object_id=cls.client_a.id, file_key='co_a/keyA.pdf',
            filename='contrat-a.pdf', size=1234, mime='application/pdf',
            uploaded_by=cls.admin_a)
        # Pièce jointe de B (autre société) ciblant son propre client.
        cls.att_b = Attachment.objects.create(
            company=cls.co_b, content_type=ct_client,
            object_id=cls.client_b.id, file_key='co_b/keyB.pdf',
            filename='contrat-b.pdf', size=99, mime='application/pdf',
            uploaded_by=cls.admin_b)

    def _run(self, **kwargs):
        from django.core.management import call_command
        call_command('migrate_attachments_to_ged', **kwargs)

    def test_import_creates_document_reusing_file_key(self):
        self._run(company='ged-a')
        doc = Document.objects.get(company=self.co_a, nom='contrat-a.pdf')
        # Document atterri dans le cabinet/dossier d'import par défaut.
        self.assertEqual(doc.folder.cabinet.nom, 'Importé')
        self.assertEqual(doc.folder.nom, 'Pièces jointes importées')
        version = doc.versions.get()
        # RÉUTILISE la clé MinIO d'origine — aucun fichier recopié.
        self.assertEqual(version.file_key, self.att_a.file_key)
        self.assertEqual(version.version, 1)
        self.assertEqual(version.filename, 'contrat-a.pdf')
        self.assertEqual(version.size, 1234)
        self.assertEqual(version.company_id, self.co_a.id)

    def test_import_creates_documentlien_for_targeted_attachment(self):
        self._run(company='ged-a')
        doc = Document.objects.get(company=self.co_a, nom='contrat-a.pdf')
        liens = selectors.documents_for_target(self.co_a, self.client_a)
        self.assertIn(doc.id, [d.id for d in liens])
        lien = DocumentLien.objects.get(document=doc)
        self.assertEqual(lien.company_id, self.co_a.id)
        self.assertEqual(lien.object_id, self.client_a.id)

    def test_import_is_idempotent_no_duplicates(self):
        self._run()  # toutes sociétés
        self._run()  # re-lancement
        self._run()
        # Un seul document par pièce jointe, un seul lien — jamais de doublon.
        self.assertEqual(
            Document.objects.filter(company=self.co_a).count(), 1)
        self.assertEqual(
            DocumentVersion.objects.filter(file_key='co_a/keyA.pdf').count(), 1)
        self.assertEqual(
            DocumentLien.objects.filter(object_id=self.client_a.id).count(), 1)
        # Le cabinet/dossier d'import n'est créé qu'une fois.
        self.assertEqual(
            Cabinet.objects.filter(company=self.co_a, nom='Importé').count(), 1)
        self.assertEqual(
            Folder.objects.filter(
                company=self.co_a, nom='Pièces jointes importées').count(), 1)

    def test_multi_tenant_isolation(self):
        self._run()  # toutes sociétés
        # Chaque pièce jointe atterrit dans SA société, jamais cross-société.
        doc_a = Document.objects.get(company=self.co_a, nom='contrat-a.pdf')
        doc_b = Document.objects.get(company=self.co_b, nom='contrat-b.pdf')
        self.assertEqual(doc_a.company_id, self.co_a.id)
        self.assertEqual(doc_b.company_id, self.co_b.id)
        self.assertEqual(doc_a.versions.get().file_key, 'co_a/keyA.pdf')
        self.assertEqual(doc_b.versions.get().file_key, 'co_b/keyB.pdf')
        # Le cabinet « Importé » de A ne contient pas le document de B.
        self.assertEqual(doc_a.folder.cabinet.company_id, self.co_a.id)
        self.assertNotEqual(doc_a.folder.cabinet_id, doc_b.folder.cabinet_id)

    def test_company_scope_limits_import(self):
        self._run(company='ged-a')
        # Seule la société A est importée.
        self.assertTrue(Document.objects.filter(company=self.co_a).exists())
        self.assertFalse(Document.objects.filter(company=self.co_b).exists())

    def test_originals_untouched(self):
        self._run()
        # Les pièces jointes d'origine ne sont ni supprimées ni modifiées.
        self.att_a.refresh_from_db()
        self.att_b.refresh_from_db()
        self.assertEqual(Attachment.objects.count(), 2)
        self.assertEqual(self.att_a.file_key, 'co_a/keyA.pdf')
        self.assertEqual(self.att_a.filename, 'contrat-a.pdf')

    def test_no_lien_for_disallowed_target(self):
        # Pièce jointe ciblant un type NON autorisé (authentication.company).
        ct_company = ContentType.objects.get_for_model(Company)
        Attachment.objects.create(
            company=self.co_a, content_type=ct_company,
            object_id=self.co_a.id, file_key='co_a/misc.pdf',
            filename='divers.pdf', size=10, mime='application/pdf',
            uploaded_by=self.admin_a)
        self._run(company='ged-a')
        # Le document existe mais sans lien (cible non autorisée).
        doc = Document.objects.get(company=self.co_a, nom='divers.pdf')
        self.assertEqual(DocumentLien.objects.filter(document=doc).count(), 0)

    def test_no_lien_when_target_object_gone(self):
        # La cible existe au moment de l'import puis disparaît : pas de lien
        # bancal. On simule en supprimant le client après création de la pièce.
        ct_client = ContentType.objects.get_for_model(Client)
        Attachment.objects.create(
            company=self.co_a, content_type=ct_client,
            object_id=999999, file_key='co_a/orphan.pdf',
            filename='orphelin.pdf', size=10, mime='application/pdf',
            uploaded_by=self.admin_a)
        self._run(company='ged-a')
        doc = Document.objects.get(company=self.co_a, nom='orphelin.pdf')
        # Aucun lien vers un objet inexistant.
        self.assertEqual(DocumentLien.objects.filter(document=doc).count(), 0)

    def test_dry_run_writes_nothing(self):
        self._run(company='ged-a', dry_run=True)
        self.assertFalse(Document.objects.filter(company=self.co_a).exists())
        self.assertFalse(DocumentVersion.objects.exists())
        self.assertFalse(DocumentLien.objects.exists())
        self.assertFalse(
            Cabinet.objects.filter(company=self.co_a, nom='Importé').exists())


# ── GED8 — Coffre-fort par employé/client (ACL propriétaire + admin) ──
class CoffreAclTests(GedBase):
    """Vérifie l'ACL du coffre-fort : un employé ne voit QUE son coffre, un
    admin voit tous ceux de sa société, et un document placé dans un coffre est
    invisible des autres. Société toujours posée côté serveur."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Deux employés non-admin de la société A + un client.
        cls.emp1 = make_user(cls.co_a, 'ged-emp1', 'normal')
        cls.emp2 = make_user(cls.co_a, 'ged-emp2', 'normal')
        cls.client_a = Client.objects.create(
            company=cls.co_a, nom='Client A', email='ca@example.com')
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Racine')
        # Coffre de emp1.
        cls.coffre1 = Coffre.objects.create(
            company=cls.co_a, nom='Coffre emp1', proprietaire=cls.emp1)
        # Document dans le coffre de emp1.
        cls.doc_secret = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, coffre=cls.coffre1,
            nom='Bulletin de paie emp1')
        # Document hors coffre (visible de tous).
        cls.doc_public = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Note de service')

    def test_owner_sees_own_coffre(self):
        api = auth(self.emp1)
        resp = api.get('/api/django/ged/coffres/')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.coffre1.id, ids)

    def test_non_owner_employee_cannot_see_coffre(self):
        api = auth(self.emp2)
        # emp2 n'est pas propriétaire : ni en liste…
        resp = api.get('/api/django/ged/coffres/')
        self.assertEqual(rows(resp), [])
        # …ni en lecture directe (404, pas dans le queryset).
        resp = api.get(f'/api/django/ged/coffres/{self.coffre1.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_admin_sees_all_company_coffres(self):
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/coffres/')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.coffre1.id, ids)

    def test_document_in_coffre_hidden_from_non_owner(self):
        api = auth(self.emp2)
        resp = api.get('/api/django/ged/documents/')
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.doc_secret.id, ids)
        self.assertIn(self.doc_public.id, ids)
        # Lecture directe du doc secret : 404.
        resp = api.get(f'/api/django/ged/documents/{self.doc_secret.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_owner_sees_document_in_own_coffre(self):
        api = auth(self.emp1)
        resp = api.get('/api/django/ged/documents/')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.doc_secret.id, ids)

    def test_admin_sees_document_in_coffre(self):
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc_secret.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_cross_company_coffre_isolation(self):
        # Admin B ne voit aucun coffre de A.
        api = auth(self.admin_b)
        resp = api.get('/api/django/ged/coffres/')
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.coffre1.id, ids)

    def test_create_coffre_forces_company_and_owner_xor(self):
        api = auth(self.admin_a)
        # Sans propriétaire ni client → 400.
        resp = api.post('/api/django/ged/coffres/', {
            'nom': 'Vide', 'company': self.co_b.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        # Les deux propriétaires → 400.
        resp = api.post('/api/django/ged/coffres/', {
            'nom': 'Deux', 'proprietaire': self.emp1.id,
            'client': self.client_a.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        # Un employé seul → 201, société forcée à A.
        resp = api.post('/api/django/ged/coffres/', {
            'nom': 'OK emp', 'proprietaire': self.emp2.id,
            'company': self.co_b.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        coffre = Coffre.objects.get(id=resp.data['id'])
        self.assertEqual(coffre.company_id, self.co_a.id)
        self.assertEqual(coffre.proprietaire_id, self.emp2.id)

    def test_cannot_drop_document_in_others_coffre(self):
        # Un responsable (droit d'écrire) qui n'est PAS propriétaire du coffre
        # de emp1 ne peut pas y déposer un document : rejet ACL en 400.
        resp_user = make_user(self.co_a, 'ged-resp2', 'responsable')
        api = auth(resp_user)
        resp = api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'coffre': self.coffre1.id,
            'nom': 'Intrusion'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_coffre_documents_action(self):
        api = auth(self.emp1)
        resp = api.get(f'/api/django/ged/coffres/{self.coffre1.id}/documents/')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data]
        self.assertIn(self.doc_secret.id, ids)


# ── GED9 — Taxonomie de tags documentaires ───────────────────────────
class DocumentTagTaxonomyTests(GedBase):
    """Vérifie la taxonomie hiérarchique de tags : création scopée société,
    parent même-société, garde anti-cycle, application/retrait sur un document,
    chemin lisible et filtre par tag (+ descendants)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Racine')
        cls.doc = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Contrat X')

    def test_create_tag_forces_company(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/tags/', {
            'nom': 'Juridique', 'slug': 'juridique',
            'company': self.co_b.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        tag = DocumentTag.objects.get(id=resp.data['id'])
        self.assertEqual(tag.company_id, self.co_a.id)

    def test_hierarchy_and_chemin(self):
        racine = DocumentTag.objects.create(
            company=self.co_a, nom='Juridique', slug='juridique')
        enfant = DocumentTag.objects.create(
            company=self.co_a, nom='Contrats', slug='contrats', parent=racine)
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/tags/{enfant.id}/')
        self.assertEqual(resp.data['chemin'], 'Juridique / Contrats')

    def test_parent_other_company_rejected(self):
        tag_b = DocumentTag.objects.create(
            company=self.co_b, nom='Etranger', slug='etranger')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/tags/', {
            'nom': 'Sous', 'slug': 'sous', 'parent': tag_b.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_cycle_rejected(self):
        a = DocumentTag.objects.create(company=self.co_a, nom='A', slug='a')
        b = DocumentTag.objects.create(
            company=self.co_a, nom='B', slug='b', parent=a)
        api = auth(self.admin_a)
        # Tenter de mettre A sous B (son descendant) → cycle → 400.
        resp = api.patch(f'/api/django/ged/tags/{a.id}/',
                         {'parent': b.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_tagger_and_detagger_document(self):
        tag = DocumentTag.objects.create(
            company=self.co_a, nom='Important', slug='important')
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/documents/{self.doc.id}/tagger/',
                        {'tag': tag.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(DocumentTagAssignment.objects.filter(
            document=self.doc, tag=tag).exists())
        tag_ids = [t['id'] for t in resp.data['tags']]
        self.assertIn(tag.id, tag_ids)
        # Idempotent : 2e tagger → 200, toujours un seul lien.
        resp = api.post(f'/api/django/ged/documents/{self.doc.id}/tagger/',
                        {'tag': tag.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(DocumentTagAssignment.objects.filter(
            document=self.doc, tag=tag).count(), 1)
        # detagger.
        resp = api.post(f'/api/django/ged/documents/{self.doc.id}/detagger/',
                        {'tag': tag.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(DocumentTagAssignment.objects.filter(
            document=self.doc, tag=tag).exists())

    def test_cannot_tag_other_company_tag(self):
        tag_b = DocumentTag.objects.create(
            company=self.co_b, nom='B', slug='b')
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/documents/{self.doc.id}/tagger/',
                        {'tag': tag_b.id}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_filter_documents_by_tag(self):
        tag = DocumentTag.objects.create(
            company=self.co_a, nom='T', slug='t')
        services.assign_tag(self.doc, tag)
        other = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Sans tag')
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/?tag={tag.id}')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.doc.id, ids)
        self.assertNotIn(other.id, ids)

    def test_tag_documents_action_with_descendants(self):
        parent = DocumentTag.objects.create(
            company=self.co_a, nom='P', slug='p')
        child = DocumentTag.objects.create(
            company=self.co_a, nom='C', slug='c', parent=parent)
        doc_child = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Doc enfant')
        services.assign_tag(doc_child, child)
        api = auth(self.admin_a)
        # Sans descendants : le doc du sous-tag n'apparaît pas.
        resp = api.get(f'/api/django/ged/tags/{parent.id}/documents/')
        ids = [r['id'] for r in resp.data]
        self.assertNotIn(doc_child.id, ids)
        # Avec descendants : il apparaît.
        resp = api.get(
            f'/api/django/ged/tags/{parent.id}/documents/?descendants=1')
        ids = [r['id'] for r in resp.data]
        self.assertIn(doc_child.id, ids)

    def test_tag_isolation_list(self):
        DocumentTag.objects.create(company=self.co_b, nom='B', slug='b')
        DocumentTag.objects.create(company=self.co_a, nom='A', slug='a')
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/tags/')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('A', noms)
        self.assertNotIn('B', noms)


# ── GED10 — Métadonnées typées configurables (réutilise customfields) ─
class DocumentCustomDataTests(GedBase):
    """Vérifie que les documents portent des métadonnées typées validées contre
    les définitions `customfields` du module « document » : champ obligatoire,
    type cohérent, choix borné, clés inconnues écartées, et isolation société."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.customfields.models import CustomFieldDef
        cls.CFD = CustomFieldDef
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Racine')
        # Une définition obligatoire (texte) + une de choix sur le module doc.
        cls.CFD.objects.create(
            company=cls.co_a, module='document', code='reference',
            libelle='Référence', type='text', obligatoire=True)
        cls.CFD.objects.create(
            company=cls.co_a, module='document', code='confidentialite',
            libelle='Confidentialité', type='choice',
            options=['public', 'interne', 'secret'])

    def test_create_document_with_valid_custom_data(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'nom': 'Contrat',
            'custom_data': {'reference': 'DOC-001',
                            'confidentialite': 'interne'},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = Document.objects.get(id=resp.data['id'])
        self.assertEqual(doc.custom_data['reference'], 'DOC-001')
        self.assertEqual(doc.custom_data['confidentialite'], 'interne')

    def test_missing_required_field_rejected(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'nom': 'Sans ref',
            'custom_data': {'confidentialite': 'public'},
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_invalid_choice_rejected(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'nom': 'Doc',
            'custom_data': {'reference': 'R', 'confidentialite': 'inconnu'},
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unknown_keys_are_dropped(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'nom': 'Doc',
            'custom_data': {'reference': 'R', 'inexistant': 'x'},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = Document.objects.get(id=resp.data['id'])
        self.assertNotIn('inexistant', doc.custom_data)

    def test_custom_data_isolated_by_company(self):
        # Une définition obligatoire de A ne s'applique PAS à B (qui n'en a pas).
        api = auth(self.admin_b)
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Racine B')
        resp = api.post('/api/django/ged/documents/', {
            'folder': folder_b.id, 'nom': 'Doc B', 'custom_data': {},
        }, format='json')
        # Aucun champ obligatoire pour B → accepté.
        self.assertEqual(resp.status_code, 201, resp.data)


# ── GED11 — Recherche plein-texte Postgres (SearchVector + GIN) ───────
class DocumentFullTextSearchTests(GedBase):
    """Vérifie la recherche plein-texte : le tsvector est alimenté à la
    création/màj, l'endpoint /recherche matche nom/description/OCR, classe par
    pertinence, respecte l'ACL coffre-fort et l'isolation société."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Racine')

    def test_search_matches_name(self):
        api = auth(self.admin_a)
        api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id,
            'nom': 'Contrat de maintenance photovoltaïque'}, format='json')
        api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'nom': 'Facture eau'}, format='json')
        resp = api.get('/api/django/ged/documents/recherche/?q=maintenance')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Contrat de maintenance photovoltaïque', noms)
        self.assertNotIn('Facture eau', noms)

    def test_search_matches_description(self):
        api = auth(self.admin_a)
        api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'nom': 'Doc',
            'description': 'onduleur Huawei trois phases'}, format='json')
        resp = api.get('/api/django/ged/documents/recherche/?q=onduleur')
        self.assertEqual(len(rows(resp)), 1)

    def test_search_matches_ocr_text(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Scan')
        services.set_ocr_text(doc, 'numéro de série panneau JA Solar 555W')
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/documents/recherche/?q=panneau')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(doc.id, ids)

    def test_empty_query_returns_nothing(self):
        Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Quelque chose')
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/documents/recherche/?q=')
        self.assertEqual(rows(resp), [])

    def test_search_respects_company_isolation(self):
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Racine B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Secret maintenance B')
        services.update_search_vector(doc_b)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/documents/recherche/?q=maintenance')
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(doc_b.id, ids)

    def test_search_respects_coffre_acl(self):
        emp = make_user(self.co_a, 'ged-fts-emp', 'normal')
        coffre = Coffre.objects.create(
            company=self.co_a, nom='Coffre', proprietaire=self.admin_a)
        secret = Document.objects.create(
            company=self.co_a, folder=self.folder_a, coffre=coffre,
            nom='dossier maintenance confidentiel')
        services.update_search_vector(secret)
        # L'employé non-propriétaire ne le trouve pas.
        api = auth(emp)
        resp = api.get('/api/django/ged/documents/recherche/?q=maintenance')
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(secret.id, ids)
        # Le propriétaire (admin) le trouve.
        api2 = auth(self.admin_a)
        resp2 = api2.get('/api/django/ged/documents/recherche/?q=maintenance')
        ids2 = [r['id'] for r in rows(resp2)]
        self.assertIn(secret.id, ids2)

    def test_update_reindexes(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id, 'nom': 'Ancien titre'}, format='json')
        doc_id = resp.data['id']
        api.patch(f'/api/django/ged/documents/{doc_id}/',
                  {'nom': 'Nouveau libellé batterie'}, format='json')
        resp = api.get('/api/django/ged/documents/recherche/?q=batterie')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(doc_id, ids)


# ── GED12 — Index OCR + recherche sémantique (pgvector, key-gated no-op) ──
class DocumentSemanticSearchTests(GedBase):
    """Vérifie le comportement KEY-GATED de la recherche sémantique : sans clé
    d'embedding, `index_embedding` est un no-op (embedding reste NULL) et la
    recherche sémantique dégrade proprement sur le plein-texte GED11. Avec un
    provider simulé, l'embedding est posé et la recherche cosinus s'active."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Racine')

    def test_embedding_disabled_by_default(self):
        self.assertFalse(services.embedding_enabled())

    def test_index_embedding_is_noop_without_key(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Doc')
        self.assertFalse(services.index_embedding(doc))
        doc.refresh_from_db()
        self.assertIsNone(doc.embedding)

    def test_compute_embedding_noop_without_key(self):
        self.assertIsNone(services.compute_embedding('un texte quelconque'))

    def test_semantique_endpoint_falls_back_to_fulltext(self):
        api = auth(self.admin_a)
        api.post('/api/django/ged/documents/', {
            'folder': self.folder_a.id,
            'nom': 'Contrat maintenance onduleur'}, format='json')
        resp = api.get('/api/django/ged/documents/semantique/?q=maintenance')
        self.assertEqual(resp.status_code, 200)
        # Sans clé : mode plein-texte, et le doc matche par plein-texte.
        self.assertEqual(resp.data['mode'], 'plein-texte')
        noms = [r['nom'] for r in resp.data['results']]
        self.assertIn('Contrat maintenance onduleur', noms)

    def test_semantique_respects_company_isolation_in_fallback(self):
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Racine B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Secret maintenance B')
        services.update_search_vector(doc_b)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/documents/semantique/?q=maintenance')
        ids = [r['id'] for r in resp.data['results']]
        self.assertNotIn(doc_b.id, ids)

    def test_set_ocr_text_triggers_embedding_index(self):
        # set_ocr_text indexe l'OCR (plein-texte) + tente l'embedding (no-op).
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Scan')
        services.set_ocr_text(doc, 'panneau monocristallin 555W')
        doc.refresh_from_db()
        self.assertEqual(doc.texte_ocr, 'panneau monocristallin 555W')
        # Embedding reste NULL (no-op sans clé).
        self.assertIsNone(doc.embedding)

    def test_semantic_search_uses_cosine_when_enabled(self):
        # Provider simulé : on active le flag + on monkeypatch compute_embedding.
        from unittest import mock
        from django.test import override_settings
        from apps.ged import services as svc

        def fake_embed(text):
            # Embedding trivial : vecteur orienté par la présence d'un mot-clé.
            base = [0.0] * 1024
            if 'solaire' in (text or '').lower():
                base[0] = 1.0
            else:
                base[1] = 1.0
            return base

        doc_solaire = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Étude solaire')
        doc_autre = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Facture eau')
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch.object(svc, 'compute_embedding', side_effect=fake_embed):
            # Indexe les deux documents.
            self.assertTrue(svc.index_embedding(doc_solaire))
            self.assertTrue(svc.index_embedding(doc_autre))
            doc_solaire.refresh_from_db()
            self.assertIsNotNone(doc_solaire.embedding)
            # Recherche sémantique : "centrale solaire" doit ramener l'étude
            # solaire en tête (distance cosinus minimale).
            results = list(selectors.semantic_search_documents(
                self.admin_a, 'centrale solaire'))
            self.assertEqual(results[0].id, doc_solaire.id)


# ── FG352 — RAG / DocQA : indexation par fragments + récupération (no-op) ──
class DocQaRagTests(GedBase):
    """FG352 — Vérifie le RAG/DocQA : le découpage (langchain-textsplitters ou
    repli) produit des fragments cohérents ; sans clé d'embedding, l'indexation
    par fragments est un no-op (aucun `DocumentChunk`) et la récupération renvoie
    vide ; avec un provider simulé, les fragments sont embeddés et la
    récupération top-k cosinus s'active et reste bornée par société + ACL."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Manuels')

    # — Découpage —
    def test_chunk_text_empty_returns_empty(self):
        self.assertEqual(services.chunk_text(''), [])
        self.assertEqual(services.chunk_text('   '), [])
        self.assertEqual(services.chunk_text(None), [])

    def test_chunk_text_splits_long_text(self):
        # Texte > chunk_size → plusieurs fragments non vides.
        text = 'Onduleur. ' * 300  # ~3000 caractères
        chunks = services.chunk_text(text, chunk_size=500, chunk_overlap=50)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.strip() for c in chunks))
        # Chaque fragment respecte (à peu près) la taille demandée.
        self.assertTrue(all(len(c) <= 600 for c in chunks))

    def test_chunk_text_short_text_single_chunk(self):
        chunks = services.chunk_text('Manuel court onduleur 5kW')
        self.assertEqual(chunks, ['Manuel court onduleur 5kW'])

    # — Indexation no-op sans clé —
    def test_index_chunks_is_noop_without_key(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Manuel pompe')
        services.set_ocr_text(doc, 'Texte du manuel ' * 100)
        self.assertEqual(services.index_document_chunks(doc), 0)
        self.assertEqual(DocumentChunk.objects.filter(document=doc).count(), 0)

    def test_retrieve_chunks_empty_without_key(self):
        self.assertEqual(
            selectors.retrieve_chunks(self.admin_a, 'comment câbler ?'), [])

    def test_docqa_endpoint_disabled_without_key(self):
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/documents/docqa/?q=onduleur')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['enabled'])
        self.assertEqual(resp.data['results'], [])

    # — Avec un provider simulé (clé présente) —
    def _fake_embed(self, text):
        # Vecteur 1024 orienté par la présence d'un mot-clé (déterministe).
        base = [0.0] * 1024
        low = (text or '').lower()
        if 'pompe' in low or 'pompage' in low:
            base[0] = 1.0
        elif 'onduleur' in low:
            base[1] = 1.0
        else:
            base[2] = 1.0
        return base

    def test_index_and_retrieve_with_stub_embedder(self):
        from unittest import mock
        from django.test import override_settings
        from apps.ged import services as svc

        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Manuel pompe solaire')
        # Texte assez long pour produire plusieurs fragments.
        texte = ('La pompe solaire de pompage agricole. ' * 60
                 + 'Branchement onduleur réseau. ' * 60)
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch.object(svc, 'compute_embedding',
                                  side_effect=self._fake_embed):
            svc.set_ocr_text(doc, texte)
            n = svc.index_document_chunks(doc)
            self.assertGreater(n, 1)
            chunks = DocumentChunk.objects.filter(document=doc)
            self.assertEqual(chunks.count(), n)
            # Chaque fragment porte la company du document + un embedding.
            self.assertTrue(all(c.company_id == self.co_a.id for c in chunks))
            self.assertTrue(all(c.embedding is not None for c in chunks))
            # Récupération : « pompage » doit ramener un fragment « pompe » en
            # tête (distance cosinus minimale).
            results = selectors.retrieve_chunks(
                self.admin_a, 'pompage agricole', limit=3)
            self.assertTrue(results)
            self.assertIn('pompe', results[0].texte.lower())

    def test_index_chunks_is_idempotent(self):
        from unittest import mock
        from django.test import override_settings
        from apps.ged import services as svc

        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Manuel onduleur')
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch.object(svc, 'compute_embedding',
                                  side_effect=self._fake_embed):
            svc.set_ocr_text(doc, 'Onduleur hybride. ' * 100)
            n1 = svc.index_document_chunks(doc)
            n2 = svc.index_document_chunks(doc)
            self.assertEqual(n1, n2)
            # Pas de doublons : exactement n fragments après ré-indexation.
            self.assertEqual(
                DocumentChunk.objects.filter(document=doc).count(), n2)

    def test_retrieve_chunks_company_isolated(self):
        from unittest import mock
        from django.test import override_settings
        from apps.ged import services as svc

        # Document chez la société B avec des fragments embeddés.
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Manuels B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Secret pompe B')
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch.object(svc, 'compute_embedding',
                                  side_effect=self._fake_embed):
            svc.set_ocr_text(doc_b, 'pompe solaire confidentielle ' * 80)
            svc.index_document_chunks(doc_b)
            # L'admin de A ne doit JAMAIS voir les fragments de B.
            results = selectors.retrieve_chunks(self.admin_a, 'pompe', limit=10)
            doc_ids = {c.document_id for c in results}
            self.assertNotIn(doc_b.id, doc_ids)


# ── U14 — Upload « en un appel » (document + version 1) via televerser ──
class DocumentUploadTests(GedBase):
    """L'action multipart `documents/televerser/` crée le document ET sa
    première version en un seul appel, en RÉUTILISANT `records.storage`
    (mocké ici pour ne pas toucher MinIO). Company/créateur/uploader posés
    côté serveur ; dossier cible borné à la société (isolation préservée).
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Docs A')

    def _file(self, name='contrat.pdf'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(
            name, b'%PDF-1.4 fake', content_type='application/pdf')

    def _fake_store(self, filename='contrat.pdf'):
        # store_attachment renvoie (meta, None) en succès — on évite MinIO.
        return ({
            'file_key': f'attachments/{filename}',
            'filename': filename,
            'size': 12,
            'mime': 'application/pdf',
        }, None)

    def test_upload_creates_document_and_version(self):
        from unittest import mock
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.store_attachment',
                        return_value=self._fake_store()):
            resp = api.post('/api/django/ged/documents/televerser/', {
                'folder': self.folder_a.id,
                'nom': 'Contrat CIN',
                'file': self._file(),
                # Tentative d'injecter une autre société — doit être ignorée.
                'company': self.co_b.id,
            }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = Document.objects.get(id=resp.data['id'])
        self.assertEqual(doc.nom, 'Contrat CIN')
        self.assertEqual(doc.folder_id, self.folder_a.id)
        # company + created_by posés côté serveur (jamais du corps).
        self.assertEqual(doc.company_id, self.co_a.id)
        self.assertEqual(doc.created_by_id, self.admin_a.id)
        # Version 1 créée, file_key issu de records.storage, uploader serveur.
        version = doc.versions.get()
        self.assertEqual(version.version, 1)
        self.assertEqual(version.file_key, 'attachments/contrat.pdf')
        self.assertEqual(version.company_id, self.co_a.id)
        self.assertEqual(version.uploaded_by_id, self.admin_a.id)
        self.assertEqual(resp.data['version_count'], 1)

    def test_upload_defaults_name_to_filename(self):
        from unittest import mock
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.store_attachment',
                        return_value=self._fake_store('photo.pdf')):
            resp = api.post('/api/django/ged/documents/televerser/', {
                'folder': self.folder_a.id, 'file': self._file('photo.pdf'),
            }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = Document.objects.get(id=resp.data['id'])
        # Sans `nom` saisi, on retombe sur le nom du fichier stocké.
        self.assertEqual(doc.nom, 'photo.pdf')

    def test_upload_requires_file(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/televerser/', {
            'folder': self.folder_a.id, 'nom': 'Sans fichier',
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('file', [d.nom for d in Document.objects.all()])

    def test_upload_requires_folder(self):
        from unittest import mock
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.store_attachment',
                        return_value=self._fake_store()):
            resp = api.post('/api/django/ged/documents/televerser/', {
                'file': self._file(),
            }, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_upload_rejects_other_company_folder(self):
        from unittest import mock
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.store_attachment',
                        return_value=self._fake_store()):
            resp = api.post('/api/django/ged/documents/televerser/', {
                'folder': folder_b.id, 'file': self._file(),
            }, format='multipart')
        # Dossier d'une autre société → 404 (jamais de fuite cross-société).
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            Document.objects.filter(folder=folder_b).exists())

    def test_upload_propagates_store_error(self):
        from unittest import mock
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.store_attachment',
                        return_value=(None, 'Format non supporté.')):
            resp = api.post('/api/django/ged/documents/televerser/', {
                'folder': self.folder_a.id, 'file': self._file('x.txt'),
            }, format='multipart')
        self.assertEqual(resp.status_code, 400)
        # Aucun document créé si le stockage échoue.
        self.assertFalse(
            Document.objects.filter(folder=self.folder_a).exists())


# ── GED14 — Aperçu inline multi-format (proxy même-origine) ──────────
class DocumentVersionAperuTests(GedBase):
    """GED14 — L'action `apercu` relaie le contenu MinIO via Django (même
    origine) pour un affichage inline dans le navigateur.

    Couvre :
    - aperçu inline d'un PDF (Content-Disposition: inline)
    - aperçu inline d'une image (image/png)
    - aperçu inline d'un texte (text/plain)
    - type non-inline (application/zip) → Content-Disposition: attachment
    - objet MinIO manquant → 404
    - isolation multi-tenant : une version d'une autre société renvoie 404
    - authentification requise
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Docs A')
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Contrat')
        cls.version_a = services.add_version(
            cls.doc_a, file_key='attachments/contrat.pdf',
            company=cls.co_a, filename='contrat.pdf', size=100,
            mime='application/pdf', uploaded_by=cls.admin_a)

    def _url(self, version_id):
        return f'/api/django/ged/versions/{version_id}/apercu/'

    def test_apercu_pdf_inline(self):
        """Un PDF est servi avec Content-Disposition: inline."""
        from unittest import mock
        fake_content = b'%PDF-1.4 fake'
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake_content, None)):
            resp = api.get(self._url(self.version_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('inline', resp['Content-Disposition'])
        self.assertIn('contrat.pdf', resp['Content-Disposition'])
        self.assertEqual(resp['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(resp.content, fake_content)

    def test_apercu_lecture_seule_role_autorise(self):
        """Régression GED14 : un rôle LECTURE SEULE (non-responsable) qui peut
        déjà list/retrieve doit AUSSI pouvoir prévisualiser (200, pas 403) —
        ``apercu`` est une action de lecture (IsAnyRole)."""
        from unittest import mock
        viewer = make_user(self.co_a, 'ged-viewer-a', role='normal')
        fake_content = b'%PDF-1.4 fake'
        api = auth(viewer)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake_content, None)):
            resp = api.get(self._url(self.version_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('inline', resp['Content-Disposition'])

    def test_apercu_image_inline(self):
        """Une image est servie avec Content-Disposition: inline."""
        from unittest import mock
        folder_a = self.folder_a
        doc = Document.objects.create(
            company=self.co_a, folder=folder_a, nom='Photo')
        version_img = services.add_version(
            doc, file_key='attachments/photo.png', company=self.co_a,
            filename='photo.png', size=50, mime='image/png',
            uploaded_by=self.admin_a)
        fake_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 10
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake_png, None)):
            resp = api.get(self._url(version_img.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/png')
        self.assertIn('inline', resp['Content-Disposition'])

    def test_apercu_text_inline(self):
        """Un fichier texte est servi avec Content-Disposition: inline."""
        from unittest import mock
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Notes')
        version_txt = services.add_version(
            doc, file_key='attachments/notes.txt', company=self.co_a,
            filename='notes.txt', size=20, mime='text/plain',
            uploaded_by=self.admin_a)
        fake_text = b'Contenu textuel'
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake_text, None)):
            resp = api.get(self._url(version_txt.id))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/plain', resp['Content-Type'])
        self.assertIn('inline', resp['Content-Disposition'])

    def test_apercu_non_inline_type_becomes_attachment(self):
        """Un type non-inline (ex. application/zip) est servi en attachment."""
        from unittest import mock
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Archive')
        version_zip = services.add_version(
            doc, file_key='attachments/archive.zip', company=self.co_a,
            filename='archive.zip', size=1000, mime='application/zip',
            uploaded_by=self.admin_a)
        fake_zip = b'PK\x03\x04'
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake_zip, None)):
            resp = api.get(self._url(version_zip.id))
        self.assertEqual(resp.status_code, 200)
        # Pas de type inline → attachment (téléchargement forcé).
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertNotIn('inline', resp['Content-Disposition'])

    def test_apercu_missing_object_returns_404(self):
        """MinIO renvoie une erreur → 404."""
        from unittest import mock
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(None, 'Fichier introuvable.')):
            resp = api.get(self._url(self.version_a.id))
        self.assertEqual(resp.status_code, 404)

    def test_apercu_tenant_isolation(self):
        """Une version d'une autre société n'est pas accessible (404)."""
        from unittest import mock
        # Version appartenant à la société B.
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        version_b = services.add_version(
            doc_b, file_key='attachments/b.pdf', company=self.co_b,
            filename='b.pdf', size=10, mime='application/pdf',
            uploaded_by=self.admin_b)
        # L'admin de la société A ne peut pas accéder à la version de B.
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(b'%PDF-', None)) as m:
            resp = api.get(self._url(version_b.id))
        # 404 : la version de B est hors du queryset scopé A.
        self.assertEqual(resp.status_code, 404)
        # fetch_attachment ne doit JAMAIS être appelé (scoping DB, pas applicatif).
        m.assert_not_called()

    def test_apercu_requires_authentication(self):
        """Sans token, l'aperçu renvoie 401/403."""
        resp = APIClient().get(self._url(self.version_a.id))
        self.assertIn(resp.status_code, (401, 403))


# ── GED15 — Versionnage + historique + restauration de version ────────
class DocumentVersionHistoryRestoreTests(GedBase):
    """GED15 — Historique de versions d'un Document et restauration non-destructive.

    Couvre :
    - L'endpoint `historique` renvoie les versions scopées société (ACL coffre).
    - La restauration crée une nouvelle version (plus ancien contenu, numéro max+1).
    - L'historique est préservé après restauration (toutes les versions visibles).
    - `restored_from` et `restored_from_version` sont exposés en lecture seule.
    - Un non-propriétaire / cross-société ne peut pas restaurer (404/403).
    - La version source doit appartenir au document cible (rejet 404).
    - Isolation société : l'historique et la restauration sont bornés à la société.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Docs A')
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Contrat')
        # Crée deux versions initiales.
        cls.v1 = services.add_version(
            cls.doc_a, file_key='docs/v1.pdf', company=cls.co_a,
            filename='v1.pdf', size=100, mime='application/pdf',
            checksum='aaa', uploaded_by=cls.admin_a)
        cls.v2 = services.add_version(
            cls.doc_a, file_key='docs/v2.pdf', company=cls.co_a,
            filename='v2.pdf', size=200, mime='application/pdf',
            checksum='bbb', uploaded_by=cls.admin_a)

    # ── historique ──────────────────────────────────────────────────

    def test_historique_returns_all_versions_newest_first(self):
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc_a.id}/historique/')
        self.assertEqual(resp.status_code, 200, resp.data)
        versions = resp.data
        # Deux versions, v2 (numéro 2) d'abord car ordre décroissant.
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]['version'], 2)
        self.assertEqual(versions[1]['version'], 1)

    def test_historique_exposes_restored_from_null_for_normal_versions(self):
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc_a.id}/historique/')
        for v in resp.data:
            self.assertIsNone(v['restored_from'])
            self.assertIsNone(v['restored_from_version'])

    def test_historique_company_scoped(self):
        """Un document d'une autre société renvoie 404 à l'admin de la société A."""
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        services.add_version(
            doc_b, file_key='docs/b.pdf', company=self.co_b,
            filename='b.pdf', size=10, mime='application/pdf',
            checksum='zz', uploaded_by=self.admin_b)
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{doc_b.id}/historique/')
        self.assertEqual(resp.status_code, 404)

    def test_historique_requires_auth(self):
        resp = APIClient().get(
            f'/api/django/ged/documents/{self.doc_a.id}/historique/')
        self.assertIn(resp.status_code, (401, 403))

    def test_historique_read_role_allowed(self):
        """Tout rôle authentifié peut lire l'historique (IsAnyRole)."""
        viewer = make_user(self.co_a, 'ged15-viewer', 'normal')
        api = auth(viewer)
        resp = api.get(f'/api/django/ged/documents/{self.doc_a.id}/historique/')
        self.assertEqual(resp.status_code, 200)

    def test_historique_respects_coffre_acl(self):
        """Un document dans un coffre n'est visible qu'au propriétaire/admin."""
        emp = make_user(self.co_a, 'ged15-emp', 'normal')
        coffre = Coffre.objects.create(
            company=self.co_a, nom='Coffre', proprietaire=self.admin_a)
        doc_secret = Document.objects.create(
            company=self.co_a, folder=self.folder_a, coffre=coffre,
            nom='Doc coffre')
        services.add_version(
            doc_secret, file_key='docs/secret.pdf', company=self.co_a,
            filename='secret.pdf', size=50, mime='application/pdf',
            checksum='cc', uploaded_by=self.admin_a)
        # Non-propriétaire → 404.
        api_emp = auth(emp)
        resp = api_emp.get(
            f'/api/django/ged/documents/{doc_secret.id}/historique/')
        self.assertEqual(resp.status_code, 404)
        # Propriétaire → 200.
        api_owner = auth(self.admin_a)
        resp = api_owner.get(
            f'/api/django/ged/documents/{doc_secret.id}/historique/')
        self.assertEqual(resp.status_code, 200)

    # ── restaurer ───────────────────────────────────────────────────

    def test_restaurer_creates_new_version_copying_source(self):
        """Restaurer v1 crée une v3 avec le même contenu que v1."""
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/restaurer/',
            {'version': self.v1.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        v3 = resp.data
        self.assertEqual(v3['version'], 3)
        self.assertEqual(v3['file_key'], 'docs/v1.pdf')
        self.assertEqual(v3['filename'], 'v1.pdf')
        self.assertEqual(v3['checksum'], 'aaa')
        # restored_from pointe vers v1.
        self.assertEqual(v3['restored_from'], self.v1.id)
        self.assertEqual(v3['restored_from_version'], 1)

    def test_restaurer_preserves_full_history(self):
        """Après restauration, toutes les versions initiales sont encore présentes."""
        api = auth(self.admin_a)
        api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/restaurer/',
            {'version': self.v1.id}, format='json')
        # L'historique doit contenir 3 versions (v1, v2, v3-restaurée).
        resp = api.get(f'/api/django/ged/documents/{self.doc_a.id}/historique/')
        self.assertEqual(len(resp.data), 3)
        # v1 et v2 sont intactes.
        nums = [v['version'] for v in resp.data]
        self.assertIn(1, nums)
        self.assertIn(2, nums)
        self.assertIn(3, nums)

    def test_restaurer_service_sets_restored_from_in_db(self):
        """La nouvelle version pointe bien vers la version source en DB."""
        new_v = services.restore_version(
            self.doc_a, self.v1, uploaded_by=self.admin_a)
        new_v.refresh_from_db()
        self.assertEqual(new_v.restored_from_id, self.v1.id)
        self.assertEqual(new_v.file_key, self.v1.file_key)
        self.assertEqual(new_v.version, 3)

    def test_restaurer_service_rejects_wrong_document(self):
        """La version source doit appartenir au même document."""
        folder_a2 = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Docs A2')
        other_doc = Document.objects.create(
            company=self.co_a, folder=folder_a2, nom='Autre')
        other_v = services.add_version(
            other_doc, file_key='docs/other.pdf', company=self.co_a,
            filename='other.pdf', size=10, mime='application/pdf',
            checksum='oth', uploaded_by=self.admin_a)
        with self.assertRaises(ValueError):
            services.restore_version(self.doc_a, other_v, uploaded_by=self.admin_a)

    def test_restaurer_endpoint_rejects_other_company_document(self):
        """Un document d'une autre société renvoie 404 (jamais de fuite cross)."""
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        v_b = services.add_version(
            doc_b, file_key='docs/b.pdf', company=self.co_b,
            filename='b.pdf', size=10, mime='application/pdf',
            checksum='zz', uploaded_by=self.admin_b)
        api = auth(self.admin_a)
        # Tente de restaurer un document B — doit échouer en 404.
        resp = api.post(
            f'/api/django/ged/documents/{doc_b.id}/restaurer/',
            {'version': v_b.id}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_restaurer_endpoint_rejects_other_document_version(self):
        """La version source d'un autre document renvoie 404."""
        folder_a2 = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Docs A2')
        other_doc = Document.objects.create(
            company=self.co_a, folder=folder_a2, nom='Autre')
        other_v = services.add_version(
            other_doc, file_key='docs/other.pdf', company=self.co_a,
            filename='other.pdf', size=10, mime='application/pdf',
            checksum='oth', uploaded_by=self.admin_a)
        api = auth(self.admin_a)
        # Tente de restaurer le document A à une version appartenant à `other_doc`.
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/restaurer/',
            {'version': other_v.id}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_restaurer_requires_responsable_or_admin(self):
        """Un utilisateur normal (non responsable/admin) ne peut pas restaurer."""
        viewer = make_user(self.co_a, 'ged15-normal', 'normal')
        api = auth(viewer)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/restaurer/',
            {'version': self.v1.id}, format='json')
        self.assertIn(resp.status_code, (403, 401))
        # Aucune nouvelle version créée.
        self.assertEqual(self.doc_a.versions.count(), 2)

    def test_restaurer_requires_version_id(self):
        """Un body sans `version` renvoie 400."""
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/restaurer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_restaurer_uploaded_by_set_server_side(self):
        """L'auteur de la restauration est posé côté serveur (jamais du corps)."""
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/restaurer/',
            {'version': self.v1.id, 'uploaded_by': 9999}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        v3 = DocumentVersion.objects.get(id=resp.data['id'])
        # L'uploader est l'admin, pas l'id fourni.
        self.assertEqual(v3.uploaded_by_id, self.admin_a.id)

    def test_multiple_restores_increment_version_correctly(self):
        """Des restaurations successives incrémentent le numéro correctement."""
        api = auth(self.admin_a)
        r1 = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/restaurer/',
            {'version': self.v1.id}, format='json')
        self.assertEqual(r1.data['version'], 3)
        r2 = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/restaurer/',
            {'version': self.v2.id}, format='json')
        self.assertEqual(r2.data['version'], 4)
        self.assertEqual(self.doc_a.versions.count(), 4)


# ── GED16 — Check-out / check-in (verrouillage optimiste) ───────────
class CheckoutCheckinTests(GedBase):
    """Tests du verrouillage optimiste (GED16).

    Couvre :
      * checkout pose le verrou (company-scopé) ;
      * un second utilisateur ne peut pas extraire un document déjà verrouillé ;
      * un second utilisateur ne peut pas ajouter de version sur un doc verrouillé ;
      * le détenteur du verrou peut relâcher (check-in) ;
      * un admin peut forcer le check-in (force-release) ;
      * un non-détenteur non-admin ne peut pas relâcher ;
      * l'état du verrou est exposé dans la réponse ;
      * cross-société rejetée.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom="GED16-docs")
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom="Doc verrouillable")
        # Deuxième utilisateur dans la société A (non-admin).
        cls.user_a2 = make_user(cls.co_a, 'ged16-user2', 'responsable')

    # ── service : checkout ────────────────────────────────────────────

    def test_checkout_service_locks_document(self):
        """checkout_document pose locked_by + locked_at côté serveur."""
        doc = services.checkout_document(self.doc_a, self.admin_a)
        doc.refresh_from_db()
        self.assertEqual(doc.locked_by_id, self.admin_a.id)
        self.assertIsNotNone(doc.locked_at)
        self.assertTrue(doc.is_locked)

    def test_checkout_service_idempotent_same_user(self):
        """Un re-checkout par le même utilisateur est silencieusement idempotent."""
        services.checkout_document(self.doc_a, self.admin_a)
        # Doit ne pas lever et garder le même verrou.
        doc2 = services.checkout_document(self.doc_a, self.admin_a)
        doc2.refresh_from_db()
        self.assertEqual(doc2.locked_by_id, self.admin_a.id)

    def test_checkout_service_rejects_other_user(self):
        """checkout_document lève PermissionError si verrouillé par autrui."""
        services.checkout_document(self.doc_a, self.admin_a)
        with self.assertRaises(PermissionError):
            services.checkout_document(self.doc_a, self.user_a2)

    def test_checkout_service_rejects_other_company(self):
        """checkout_document lève PermissionError si document d'une autre société."""
        with self.assertRaises(PermissionError):
            services.checkout_document(self.doc_a, self.admin_b)

    # ── service : checkin ────────────────────────────────────────────

    def test_checkin_service_releases_lock(self):
        """checkin_document libère le verrou (locked_by → None)."""
        services.checkout_document(self.doc_a, self.admin_a)
        doc = services.checkin_document(self.doc_a, self.admin_a)
        doc.refresh_from_db()
        self.assertIsNone(doc.locked_by_id)
        self.assertIsNone(doc.locked_at)
        self.assertFalse(doc.is_locked)

    def test_checkin_service_idempotent_on_free_document(self):
        """checkin sur un document libre est silencieusement idempotent."""
        doc = services.checkin_document(self.doc_a, self.admin_a)
        doc.refresh_from_db()
        self.assertIsNone(doc.locked_by_id)

    def test_checkin_service_admin_can_force_release(self):
        """Un admin peut libérer le verrou posé par un autre utilisateur."""
        services.checkout_document(self.doc_a, self.user_a2)
        doc = services.checkin_document(self.doc_a, self.admin_a)
        doc.refresh_from_db()
        self.assertIsNone(doc.locked_by_id)

    def test_checkin_service_rejects_non_locker_non_admin(self):
        """Un utilisateur normal non-détenteur ne peut pas libérer le verrou."""
        services.checkout_document(self.doc_a, self.admin_a)
        with self.assertRaises(PermissionError):
            services.checkin_document(self.doc_a, self.user_a2)

    # ── service : assert_not_locked_by_other ─────────────────────────

    def test_assert_not_locked_passes_when_free(self):
        """assert_not_locked_by_other ne lève rien sur un document libre."""
        services.assert_not_locked_by_other(self.doc_a, self.admin_a)

    def test_assert_not_locked_passes_for_locker(self):
        """assert_not_locked_by_other ne lève rien pour le détenteur du verrou."""
        services.checkout_document(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        services.assert_not_locked_by_other(self.doc_a, self.admin_a)

    def test_assert_not_locked_raises_for_other_user(self):
        """assert_not_locked_by_other lève PermissionError pour un autre."""
        services.checkout_document(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        with self.assertRaises(PermissionError):
            services.assert_not_locked_by_other(self.doc_a, self.user_a2)

    # ── API : check-out endpoint ──────────────────────────────────────

    def test_checkout_endpoint_locks_and_returns_state(self):
        """POST check-out renvoie 200 avec is_locked=True et locked_by renseigné."""
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-out/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['is_locked'])
        self.assertEqual(resp.data['locked_by'], self.admin_a.id)
        self.assertIsNotNone(resp.data['locked_at'])
        self.assertEqual(resp.data['locked_by_nom'], self.admin_a.username)

    def test_checkout_endpoint_conflict_when_locked_by_other(self):
        """POST check-out renvoie 409 si déjà extrait par un autre utilisateur."""
        services.checkout_document(self.doc_a, self.admin_a)
        api = auth(self.user_a2)
        resp = api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-out/')
        self.assertEqual(resp.status_code, 409, resp.data)

    def test_checkout_endpoint_idempotent_same_user(self):
        """POST check-out par le même utilisateur renvoie 200 (idempotent)."""
        api = auth(self.admin_a)
        api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-out/')
        resp = api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-out/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['is_locked'])

    def test_checkout_endpoint_rejects_other_company(self):
        """POST check-out sur un document d'une autre société renvoie 404."""
        api = auth(self.admin_b)
        resp = api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-out/')
        self.assertEqual(resp.status_code, 404)

    def test_checkout_endpoint_requires_auth(self):
        """POST check-out sans authentification renvoie 401/403."""
        resp = APIClient().post(
            f'/api/django/ged/documents/{self.doc_a.id}/check-out/')
        self.assertIn(resp.status_code, (401, 403))

    # ── API : check-in endpoint ───────────────────────────────────────

    def test_checkin_endpoint_releases_lock(self):
        """POST check-in libère le verrou, renvoie 200 avec is_locked=False."""
        services.checkout_document(self.doc_a, self.admin_a)
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-in/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['is_locked'])
        self.assertIsNone(resp.data['locked_by'])

    def test_checkin_endpoint_admin_force_release(self):
        """POST check-in par un admin libère le verrou posé par un autre."""
        services.checkout_document(self.doc_a, self.user_a2)
        self.doc_a.refresh_from_db()
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-in/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['is_locked'])

    def test_checkin_endpoint_forbidden_for_non_locker(self):
        """POST check-in par un non-détenteur non-admin renvoie 403."""
        services.checkout_document(self.doc_a, self.admin_a)
        api = auth(self.user_a2)
        resp = api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-in/')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_checkin_endpoint_rejects_other_company(self):
        """POST check-in sur un document d'une autre société renvoie 404."""
        api = auth(self.admin_b)
        resp = api.post(f'/api/django/ged/documents/{self.doc_a.id}/check-in/')
        self.assertEqual(resp.status_code, 404)

    # ── Rejet d'une nouvelle version sur document verrouillé ─────────

    def test_add_version_via_api_rejected_when_locked_by_other(self):
        """POST /versions/ est rejeté (403) si le document est extrait par autrui."""
        services.checkout_document(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        api = auth(self.user_a2)
        resp = api.post('/api/django/ged/versions/', {
            'document': self.doc_a.id,
            'file_key': 'docs/intrus.pdf',
            'filename': 'intrus.pdf',
            'size': 1,
            'mime': 'application/pdf',
        }, format='json')
        self.assertIn(resp.status_code, (403, 409), resp.data)
        # Aucune version créée.
        self.assertEqual(self.doc_a.versions.count(), 0)

    def test_add_version_allowed_for_locker(self):
        """Le détenteur du verrou peut toujours ajouter une version."""
        services.checkout_document(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/versions/', {
            'document': self.doc_a.id,
            'file_key': 'docs/v1.pdf',
            'filename': 'v1.pdf',
            'size': 100,
            'mime': 'application/pdf',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.doc_a.versions.count(), 1)

    def test_add_version_allowed_when_document_free(self):
        """Un document libre accepte une nouvelle version de n'importe quel auteur."""
        api = auth(self.user_a2)
        resp = api.post('/api/django/ged/versions/', {
            'document': self.doc_a.id,
            'file_key': 'docs/libre.pdf',
            'filename': 'libre.pdf',
            'size': 50,
            'mime': 'application/pdf',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    # ── État du verrou dans le serializer ────────────────────────────

    def test_document_detail_exposes_lock_state(self):
        """GET /documents/<id>/ expose locked_by, locked_at, is_locked."""
        services.checkout_document(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc_a.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['is_locked'])
        self.assertEqual(resp.data['locked_by'], self.admin_a.id)
        self.assertIsNotNone(resp.data['locked_at'])

    def test_document_detail_lock_free_when_not_checked_out(self):
        """GET /documents/<id>/ renvoie is_locked=False sur un doc libre."""
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc_a.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['is_locked'])
        self.assertIsNone(resp.data['locked_by'])


# ── GED17 — Cycle de vie documentaire (machine à états) ─────────────
class CycleDeVieTests(GedBase):
    """Tests du cycle de vie documentaire (GED17).

    Couvre :
      * un document naît « brouillon » ;
      * une transition autorisée avance le statut ;
      * une transition NON autorisée est refusée (400 / ValueError) ;
      * un statut inconnu est rejeté ;
      * isolation par société (on n'avance pas un document d'une autre société) ;
      * le serializer expose statut + transitions autorisées ;
      * filtre ?statut=… .

    Statuts LOCAUX à la GED — jamais le funnel STAGES.py.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom="GED17-docs")
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom="Doc cycle de vie")

    # ── modèle / valeur par défaut ─────────────────────────────────────

    def test_document_starts_brouillon(self):
        """Un document neuf est au statut « brouillon »."""
        from apps.ged.models import LIFECYCLE_BROUILLON
        self.assertEqual(self.doc_a.statut, LIFECYCLE_BROUILLON)
        self.assertEqual(
            self.doc_a.transitions_autorisees, ['revue'])

    # ── service : transitions ──────────────────────────────────────────

    def test_service_valid_transition_advances(self):
        """change_lifecycle_status applique une transition autorisée."""
        from apps.ged.models import LIFECYCLE_REVUE
        doc = services.change_lifecycle_status(
            self.doc_a, LIFECYCLE_REVUE, user=self.admin_a)
        doc.refresh_from_db()
        self.assertEqual(doc.statut, LIFECYCLE_REVUE)

    def test_service_full_happy_path(self):
        """Parcours complet brouillon→revue→approuvé→archivé→obsolète."""
        from apps.ged.models import (
            LIFECYCLE_APPROUVE, LIFECYCLE_ARCHIVE, LIFECYCLE_OBSOLETE,
            LIFECYCLE_REVUE,
        )
        for cible in (LIFECYCLE_REVUE, LIFECYCLE_APPROUVE,
                      LIFECYCLE_ARCHIVE, LIFECYCLE_OBSOLETE):
            services.change_lifecycle_status(
                self.doc_a, cible, user=self.admin_a)
            self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, LIFECYCLE_OBSOLETE)

    def test_service_rejects_invalid_transition(self):
        """Une transition NON permise (brouillon→approuvé) lève ValueError."""
        from apps.ged.models import LIFECYCLE_APPROUVE
        with self.assertRaises(ValueError):
            services.change_lifecycle_status(
                self.doc_a, LIFECYCLE_APPROUVE, user=self.admin_a)
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'brouillon')

    def test_service_rejects_unknown_status(self):
        """Un statut hors vocabulaire est rejeté (ValueError)."""
        with self.assertRaises(ValueError):
            services.change_lifecycle_status(
                self.doc_a, 'nimporte', user=self.admin_a)

    def test_service_rejects_same_status_noop(self):
        """Avancer vers le statut courant n'est pas une transition valide."""
        with self.assertRaises(ValueError):
            services.change_lifecycle_status(
                self.doc_a, 'brouillon', user=self.admin_a)

    def test_service_rejects_other_company(self):
        """change_lifecycle_status refuse un document d'une autre société."""
        with self.assertRaises(PermissionError):
            services.change_lifecycle_status(
                self.doc_a, 'revue', user=self.admin_b)

    # ── endpoint ───────────────────────────────────────────────────────

    def test_endpoint_advances_status(self):
        """POST cycle-vie avance le statut et renvoie le nouvel état."""
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/cycle-vie/',
            {'statut': 'revue'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'revue')
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'revue')

    def test_endpoint_rejects_invalid_transition(self):
        """POST cycle-vie refuse une transition non permise (400)."""
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/cycle-vie/',
            {'statut': 'archive'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'brouillon')

    def test_endpoint_requires_statut(self):
        """POST cycle-vie sans statut renvoie 400."""
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/cycle-vie/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_endpoint_cannot_touch_other_company_document(self):
        """Un admin de B ne peut pas avancer un document de A (404)."""
        api = auth(self.admin_b)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/cycle-vie/',
            {'statut': 'revue'}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'brouillon')

    def test_endpoint_requires_auth(self):
        """POST cycle-vie sans authentification est refusé."""
        resp = APIClient().post(
            f'/api/django/ged/documents/{self.doc_a.id}/cycle-vie/',
            {'statut': 'revue'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    # ── serializer / filtre ────────────────────────────────────────────

    def test_serializer_exposes_status_and_transitions(self):
        """GET /documents/<id>/ expose statut, statut_display, transitions."""
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc_a.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'brouillon')
        self.assertEqual(resp.data['statut_display'], 'Brouillon')
        self.assertEqual(resp.data['transitions_autorisees'], ['revue'])

    def test_status_is_read_only_on_patch(self):
        """Un PATCH direct ne peut pas muter le statut (action dédiée seule)."""
        api = auth(self.admin_a)
        resp = api.patch(
            f'/api/django/ged/documents/{self.doc_a.id}/',
            {'statut': 'approuve'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'brouillon')

    def test_filter_by_statut(self):
        """?statut=revue ne renvoie que les documents à ce statut."""
        services.change_lifecycle_status(
            self.doc_a, 'revue', user=self.admin_a)
        Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom="Encore brouillon")
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/documents/?statut=revue')
        self.assertEqual(resp.status_code, 200, resp.data)
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Doc cycle de vie', noms)
        self.assertNotIn('Encore brouillon', noms)


# ── GED18 — Workflow d'approbation / revue documentaire ─────────────
class DemandeApprobationTests(GedBase):
    """Tests du workflow d'approbation/revue (GED18).

    Couvre :
      * lancer une revue crée une demande « en_attente » + met le doc en revue ;
      * approuver fait avancer le doc « revue → approuvé » (réutilise GED17) ;
      * rejeter renvoie le doc « revue → brouillon » ;
      * une 2e demande en attente est refusée (garde duplication) ;
      * décider une demande déjà décidée est refusé (garde illégale) ;
      * isolation par société (service + endpoints 404/403) ;
      * approbateur d'une autre société refusé ;
      * endpoints demander-revue / approuver / rejeter / liste demandes.

    Statuts LOCAUX à la GED — jamais le funnel STAGES.py.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom="GED18-docs")
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom="Doc à valider")
        cls.folder_b = Folder.objects.create(
            company=cls.co_b, cabinet=cls.cab_b, nom="GED18-docs-B")
        cls.doc_b = Document.objects.create(
            company=cls.co_b, folder=cls.folder_b, nom="Doc B")

    # ── service : lancer une revue ─────────────────────────────────────

    def test_request_review_creates_pending_and_moves_to_review(self):
        """request_review crée une demande en_attente et met le doc en revue."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        self.assertEqual(demande.statut, 'en_attente')
        self.assertEqual(demande.company_id, self.co_a.id)
        self.assertEqual(demande.demandeur_id, self.admin_a.id)
        self.assertTrue(demande.is_pending)
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'revue')

    def test_request_review_with_assigned_approver(self):
        """L'approbateur assigné est posé côté serveur sur la demande."""
        demande = services.request_review(
            self.doc_a, user=self.admin_a, approbateur=self.admin_a)
        self.assertEqual(demande.approbateur_id, self.admin_a.id)

    def test_request_review_rejects_duplicate_pending(self):
        """Une 2e demande alors qu'une est en attente lève ValueError."""
        services.request_review(self.doc_a, user=self.admin_a)
        with self.assertRaises(ValueError):
            services.request_review(self.doc_a, user=self.admin_a)
        self.assertEqual(
            DemandeApprobation.objects.filter(document=self.doc_a).count(), 1)

    def test_request_review_rejects_cross_company_approver(self):
        """Un approbateur d'une autre société est refusé (ValueError)."""
        with self.assertRaises(ValueError):
            services.request_review(
                self.doc_a, user=self.admin_a, approbateur=self.admin_b)

    def test_request_review_rejects_other_company_user(self):
        """Lancer une revue sur le doc d'une autre société → PermissionError."""
        with self.assertRaises(PermissionError):
            services.request_review(self.doc_a, user=self.admin_b)

    # ── service : approbation / rejet ──────────────────────────────────

    def test_approve_advances_document_to_approuve(self):
        """approve_demande avance le doc « revue → approuvé » (réutilise GED17)."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        dem = services.approve_demande(
            demande, user=self.admin_a, commentaire="OK pour moi")
        self.assertEqual(dem.statut, 'approuve')
        self.assertEqual(dem.approbateur_id, self.admin_a.id)
        self.assertIsNotNone(dem.decision_le)
        self.assertEqual(dem.commentaire, "OK pour moi")
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'approuve')

    def test_reject_returns_document_to_brouillon(self):
        """reject_demande renvoie le doc « revue → brouillon »."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        dem = services.reject_demande(
            demande, user=self.admin_a, commentaire="À corriger")
        self.assertEqual(dem.statut, 'rejete')
        self.assertIsNotNone(dem.decision_le)
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'brouillon')

    def test_cannot_decide_already_decided(self):
        """Décider deux fois la même demande lève ValueError."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        services.approve_demande(demande, user=self.admin_a)
        demande.refresh_from_db()
        with self.assertRaises(ValueError):
            services.reject_demande(demande, user=self.admin_a)
        with self.assertRaises(ValueError):
            services.approve_demande(demande, user=self.admin_a)

    def test_approve_rejects_other_company_user(self):
        """Approuver une demande d'une autre société → PermissionError."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        with self.assertRaises(PermissionError):
            services.approve_demande(demande, user=self.admin_b)

    def test_approve_non_revue_document_records_decision_only(self):
        """Approuver alors que le doc n'est pas « revue » enregistre la décision
        sans toucher au cycle de vie."""
        # Document déjà approuvé (hors revue) : on crée une demande à la main.
        services.change_lifecycle_status(self.doc_a, 'revue', user=self.admin_a)
        services.change_lifecycle_status(
            self.doc_a, 'approuve', user=self.admin_a)
        demande = DemandeApprobation.objects.create(
            company=self.co_a, document=self.doc_a, demandeur=self.admin_a)
        dem = services.approve_demande(demande, user=self.admin_a)
        self.assertEqual(dem.statut, 'approuve')
        self.doc_a.refresh_from_db()
        # Le statut documentaire reste « approuvé » (inchangé, pas d'erreur).
        self.assertEqual(self.doc_a.statut, 'approuve')

    # ── endpoints ──────────────────────────────────────────────────────

    def test_endpoint_demander_revue(self):
        """POST documents/<id>/demander-revue crée la demande + met en revue."""
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/demander-revue/',
            {'commentaire': 'Merci de relire'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'en_attente')
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'revue')

    def test_endpoint_demander_revue_duplicate_400(self):
        """Une 2e demande via l'endpoint renvoie 400."""
        services.request_review(self.doc_a, user=self.admin_a)
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/demander-revue/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_endpoint_demander_revue_other_company_404(self):
        """Lancer une revue sur le doc d'une autre société → 404."""
        api = auth(self.admin_b)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/demander-revue/',
            {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_approuver(self):
        """POST demandes-approbation/<id>/approuver avance le document."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/demandes-approbation/{demande.id}/approuver/',
            {'commentaire': 'Validé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'approuve')
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'approuve')

    def test_endpoint_rejeter(self):
        """POST demandes-approbation/<id>/rejeter renvoie le doc en brouillon."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/demandes-approbation/{demande.id}/rejeter/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'rejete')
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.statut, 'brouillon')

    def test_endpoint_decide_already_decided_400(self):
        """Décider via l'endpoint une demande déjà décidée renvoie 400."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        services.approve_demande(demande, user=self.admin_a)
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/demandes-approbation/{demande.id}/approuver/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_endpoint_decide_other_company_404(self):
        """Un admin de B ne voit pas la demande de A (404 sur l'action)."""
        demande = services.request_review(self.doc_a, user=self.admin_a)
        api = auth(self.admin_b)
        resp = api.post(
            f'/api/django/ged/demandes-approbation/{demande.id}/approuver/',
            {}, format='json')
        self.assertEqual(resp.status_code, 404)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'en_attente')

    def test_demandes_list_tenant_isolation(self):
        """La liste des demandes est bornée à la société de l'utilisateur."""
        services.request_review(self.doc_a, user=self.admin_a)
        services.request_review(self.doc_b, user=self.admin_b)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/demandes-approbation/')
        self.assertEqual(resp.status_code, 200, resp.data)
        doc_ids = {r['document'] for r in rows(resp)}
        self.assertIn(self.doc_a.id, doc_ids)
        self.assertNotIn(self.doc_b.id, doc_ids)

    def test_document_demandes_action(self):
        """GET documents/<id>/demandes liste les demandes du document."""
        services.request_review(self.doc_a, user=self.admin_a)
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/ged/documents/{self.doc_a.id}/demandes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        self.assertEqual(rows(resp)[0]['statut'], 'en_attente')

    def test_filter_en_attente(self):
        """?en_attente=1 ne renvoie que les demandes encore en attente."""
        d1 = services.request_review(self.doc_a, user=self.admin_a)
        services.approve_demande(d1, user=self.admin_a)
        # Nouvelle demande en attente sur le même doc (désormais approuvé).
        d2 = DemandeApprobation.objects.create(
            company=self.co_a, document=self.doc_a, demandeur=self.admin_a)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/demandes-approbation/?en_attente=1')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r['id'] for r in rows(resp)}
        self.assertIn(d2.id, ids)
        self.assertNotIn(d1.id, ids)


# -- GED19 -- ACL par dossier/document (heritage + override) --
class AclGedTests(GedBase):
    """ACL GED19 : heritage depuis le dossier, override sur le document,
    resolution en remontant le chemin, backward-compat sans ACL, scoping
    societe, refuse vs autorise."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user_a = make_user(cls.co_a, 'ged-user-a', 'normal')
        cls.user_a2 = make_user(cls.co_a, 'ged-user-a2', 'normal')
        cls.user_b = make_user(cls.co_b, 'ged-user-b', 'normal')
        cls.root = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Racine')
        cls.sub = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, parent=cls.root, nom='Sous')
        cls.root.refresh_from_db()
        cls.sub.refresh_from_db()
        cls.doc = Document.objects.create(
            company=cls.co_a, folder=cls.sub, nom='Contrat')

    def test_inherited_from_folder(self):
        AclGed.objects.create(
            company=self.co_a, folder=self.root,
            utilisateur=self.user_a, niveau='lecture', herite=True)
        self.assertEqual(selectors.acl_effective(self.doc, self.user_a), 'lecture')
        self.assertEqual(selectors.acl_effective(self.sub, self.user_a), 'lecture')

    def test_document_override_beats_inherited(self):
        AclGed.objects.create(
            company=self.co_a, folder=self.root,
            utilisateur=self.user_a, niveau='lecture', herite=True)
        AclGed.objects.create(
            company=self.co_a, document=self.doc,
            utilisateur=self.user_a, niveau='gestion', herite=True)
        self.assertEqual(selectors.acl_effective(self.doc, self.user_a), 'gestion')

    def test_nearest_folder_wins_walk_up(self):
        AclGed.objects.create(
            company=self.co_a, folder=self.root,
            utilisateur=self.user_a, niveau='lecture', herite=True)
        AclGed.objects.create(
            company=self.co_a, folder=self.sub,
            utilisateur=self.user_a, niveau='ecriture', herite=True)
        self.assertEqual(selectors.acl_effective(self.doc, self.user_a), 'ecriture')

    def test_non_inherited_entry_does_not_propagate(self):
        AclGed.objects.create(
            company=self.co_a, folder=self.root,
            utilisateur=self.user_a, niveau='gestion', herite=False)
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_a))
        self.assertEqual(selectors.acl_effective(self.root, self.user_a), 'gestion')

    def test_role_principal_resolution(self):
        role = Role.objects.create(company=self.co_a, nom='Lecteurs')
        self.user_a.role = role
        self.user_a.save(update_fields=['role'])
        AclGed.objects.create(
            company=self.co_a, folder=self.root,
            role=role, niveau='lecture', herite=True)
        self.assertEqual(selectors.acl_effective(self.doc, self.user_a), 'lecture')
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_a2))

    def test_most_permissive_at_same_scope(self):
        role = Role.objects.create(company=self.co_a, nom='Editeurs')
        self.user_a.role = role
        self.user_a.save(update_fields=['role'])
        AclGed.objects.create(
            company=self.co_a, document=self.doc,
            utilisateur=self.user_a, niveau='lecture', herite=True)
        AclGed.objects.create(
            company=self.co_a, document=self.doc,
            role=role, niveau='ecriture', herite=True)
        self.assertEqual(selectors.acl_effective(self.doc, self.user_a), 'ecriture')

    def test_no_acl_returns_none(self):
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_a))
        self.assertFalse(selectors.acl_governs_target(self.doc))

    def test_admin_always_gestion(self):
        AclGed.objects.create(
            company=self.co_a, document=self.doc,
            utilisateur=self.user_a, niveau='lecture', herite=True)
        self.assertEqual(
            selectors.acl_effective(self.doc, self.admin_a), 'gestion')

    def test_denied_when_governed_and_no_grant(self):
        AclGed.objects.create(
            company=self.co_a, folder=self.root,
            utilisateur=self.user_a, niveau='lecture', herite=True)
        self.assertTrue(selectors.acl_governs_target(self.doc))
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_a2))

    def test_company_scoping(self):
        AclGed.objects.create(
            company=self.co_a, document=self.doc,
            utilisateur=self.user_a, niveau='gestion', herite=True)
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_b))

    def test_visible_backward_compat_no_acl(self):
        visible = selectors.documents_visible_to_user(self.user_a)
        self.assertIn(self.doc.id, set(visible.values_list('id', flat=True)))

    def test_visible_hides_denied_governed_document(self):
        AclGed.objects.create(
            company=self.co_a, folder=self.root,
            utilisateur=self.user_a, niveau='lecture', herite=True)
        vis_ok = selectors.documents_visible_to_user(self.user_a)
        self.assertIn(self.doc.id, set(vis_ok.values_list('id', flat=True)))
        vis_ko = selectors.documents_visible_to_user(self.user_a2)
        self.assertNotIn(self.doc.id, set(vis_ko.values_list('id', flat=True)))

    def test_visible_ungoverned_document_still_shown(self):
        other = Document.objects.create(
            company=self.co_a, folder=self.sub, nom='Libre')
        AclGed.objects.create(
            company=self.co_a, document=self.doc,
            utilisateur=self.user_a, niveau='lecture', herite=True)
        vis = selectors.documents_visible_to_user(self.user_a2)
        ids = set(vis.values_list('id', flat=True))
        self.assertNotIn(self.doc.id, ids)
        self.assertIn(other.id, ids)

    def test_clean_requires_exactly_one_target(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            AclGed(company=self.co_a, utilisateur=self.user_a,
                   niveau='lecture').clean()
        with self.assertRaises(ValidationError):
            AclGed(company=self.co_a, folder=self.root, document=self.doc,
                   utilisateur=self.user_a, niveau='lecture').clean()

    def test_clean_requires_a_principal(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            AclGed(company=self.co_a, document=self.doc,
                   niveau='lecture').clean()

    def test_niveau_codes_fit_max_length(self):
        field = AclGed._meta.get_field('niveau')
        for code, _label in field.choices:
            self.assertLessEqual(len(code), field.max_length)


# ── GED20 — Partage public d'un document par lien tokenisé ────────────
class PartageGedTests(GedBase):
    """GED20 — Lien public tokenisé (expiration / mot de passe / quota).

    Couvre :
    - création d'un partage côté gestion (company + created_by serveur, token
      généré, document company-scopé) ;
    - accès PUBLIC par jeton (sans login) → relaie le document (version courante) ;
    - partage expiré → 410 ;
    - partage révoqué → 404 ;
    - quota épuisé → 410 ;
    - mot de passe manquant/erroné → 403 ; correct → 200 ;
    - le compteur de téléchargements s'incrémente ;
    - le mot de passe n'est jamais renvoyé en clair (write-only + hash) ;
    - isolation multi-tenant côté gestion (A ne voit/partage pas le doc de B) ;
    - le jeton public ne tient compte d'AUCUNE société dans la requête ;
    - jeton long et imprévisible (token_urlsafe).
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Docs A')
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Contrat A')
        cls.version_a = services.add_version(
            cls.doc_a, file_key='attachments/contrat-a.pdf',
            company=cls.co_a, filename='contrat-a.pdf', size=120,
            mime='application/pdf', uploaded_by=cls.admin_a)

    def _public_url(self, token):
        return f'/api/django/ged/public/{token}/'

    def _make_partage(self, **kwargs):
        return services.create_partage(
            document=self.doc_a, company=self.co_a,
            created_by=self.admin_a, **kwargs)

    # ── Gestion (création / révocation) ──────────────────────────────
    def test_create_partage_force_company_and_created_by_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/partages/', {
            'document': self.doc_a.id,
            # Tentative d'injecter une autre société — doit être ignorée.
            'company': self.co_b.id,
            'created_by': self.admin_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        partage = PartageGed.objects.get(id=resp.data['id'])
        self.assertEqual(partage.company_id, self.co_a.id)
        self.assertEqual(partage.created_by_id, self.admin_a.id)
        # Jeton généré côté serveur, jamais accepté du corps.
        self.assertTrue(partage.token)

    def test_create_partage_rejects_cross_tenant_document(self):
        """On ne partage jamais le document d'un autre locataire."""
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/partages/', {
            'document': doc_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_partages_tenant_isolation(self):
        """A ne voit que ses propres partages, jamais ceux de B."""
        mine = self._make_partage()
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        theirs = services.create_partage(
            document=doc_b, company=self.co_b, created_by=self.admin_b)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/partages/')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids)

    def test_cannot_retrieve_other_company_partage(self):
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Docs B')
        doc_b = Document.objects.create(
            company=self.co_b, folder=folder_b, nom='Doc B')
        theirs = services.create_partage(
            document=doc_b, company=self.co_b, created_by=self.admin_b)
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/partages/{theirs.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_password_never_returned_in_clear(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/partages/', {
            'document': self.doc_a.id,
            'password': 'secret-mdp',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # Le mot de passe en clair n'apparaît jamais dans la réponse.
        self.assertNotIn('password', resp.data)
        self.assertNotIn('password_hash', resp.data)
        self.assertTrue(resp.data['has_password'])
        partage = PartageGed.objects.get(id=resp.data['id'])
        # Stocké haché, jamais en clair.
        self.assertNotEqual(partage.password_hash, 'secret-mdp')
        self.assertTrue(partage.check_password('secret-mdp'))

    def test_revoke_via_action(self):
        partage = self._make_partage()
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/partages/{partage.id}/revoquer/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        partage.refresh_from_db()
        self.assertFalse(partage.actif)

    # ── Accès public (token-only) ────────────────────────────────────
    def test_public_access_streams_document(self):
        from unittest import mock
        partage = self._make_partage()
        fake = b'%PDF-1.4 contrat'
        # Aucune authentification : client public anonyme.
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake, None)):
            resp = APIClient().get(self._public_url(partage.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('inline', resp['Content-Disposition'])
        self.assertEqual(resp['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(resp.content, fake)
        # Compteur de téléchargements incrémenté.
        partage.refresh_from_db()
        self.assertEqual(partage.telechargements, 1)

    def test_public_unknown_token_returns_404(self):
        resp = APIClient().get(self._public_url('jeton-inexistant'))
        self.assertEqual(resp.status_code, 404)

    def test_public_revoked_returns_404(self):
        from unittest import mock
        partage = self._make_partage()
        services.revoke_partage(partage)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(b'x', None)) as m:
            resp = APIClient().get(self._public_url(partage.token))
        self.assertEqual(resp.status_code, 404)
        # Le fichier n'est jamais servi pour un lien révoqué.
        m.assert_not_called()

    def test_public_expired_returns_410(self):
        from unittest import mock
        from django.utils import timezone
        from datetime import timedelta
        partage = self._make_partage(
            expires_at=timezone.now() - timedelta(hours=1))
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(b'x', None)) as m:
            resp = APIClient().get(self._public_url(partage.token))
        self.assertEqual(resp.status_code, 410)
        m.assert_not_called()

    def test_public_quota_exhausted_returns_410(self):
        from unittest import mock
        partage = self._make_partage(quota_max=1)
        fake = b'%PDF-'
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake, None)):
            # 1er accès : OK (quota = 1).
            r1 = APIClient().get(self._public_url(partage.token))
            self.assertEqual(r1.status_code, 200)
            # 2e accès : quota épuisé → 410.
            r2 = APIClient().get(self._public_url(partage.token))
        self.assertEqual(r2.status_code, 410)
        partage.refresh_from_db()
        # Le compteur ne dépasse jamais le quota.
        self.assertEqual(partage.telechargements, 1)

    def test_public_wrong_password_returns_403(self):
        from unittest import mock
        partage = self._make_partage(password='mdp-correct')
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(b'x', None)) as m:
            # Sans mot de passe.
            r_none = APIClient().get(self._public_url(partage.token))
            self.assertEqual(r_none.status_code, 403)
            # Mauvais mot de passe.
            r_bad = APIClient().get(
                self._public_url(partage.token) + '?password=faux')
        self.assertEqual(r_bad.status_code, 403)
        m.assert_not_called()
        # Aucun téléchargement comptabilisé sur un échec d'authentification.
        partage.refresh_from_db()
        self.assertEqual(partage.telechargements, 0)

    def test_public_correct_password_streams(self):
        from unittest import mock
        partage = self._make_partage(password='mdp-correct')
        fake = b'%PDF-ok'
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake, None)):
            resp = APIClient().get(
                self._public_url(partage.token) + '?password=mdp-correct')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, fake)

    def test_public_password_via_header(self):
        from unittest import mock
        partage = self._make_partage(password='entete')
        fake = b'%PDF-h'
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake, None)):
            resp = APIClient().get(
                self._public_url(partage.token),
                HTTP_X_PARTAGE_PASSWORD='entete')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, fake)

    def test_public_endpoint_ignores_request_company(self):
        """SÉCURITÉ : le jeton public ne tient compte d'AUCUNE identité ni
        société de la requête — même un utilisateur de B (avec son token JWT)
        obtient le document de A si le jeton de partage est celui de A, et
        seulement parce que le JETON l'autorise."""
        from unittest import mock
        partage = self._make_partage()
        fake = b'%PDF-tenant'
        # Client authentifié EN TANT QUE B : le jeton seul décide.
        api_b = auth(self.admin_b)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake, None)):
            resp = api_b.get(self._public_url(partage.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, fake)

    def test_token_is_unguessable(self):
        """Le jeton est long, URL-safe et imprévisible (token_urlsafe(32))."""
        p1 = self._make_partage()
        p2 = self._make_partage()
        self.assertNotEqual(p1.token, p2.token)
        # token_urlsafe(32) → ~43 caractères ; on exige largement > 30.
        self.assertGreater(len(p1.token), 30)
        # Caractères URL-safe uniquement.
        self.assertRegex(p1.token, r'^[A-Za-z0-9_-]+$')

    def test_password_hash_field_is_long_enough(self):
        """Garde anti-troncature : le hash Django (long) tient dans le champ."""
        from django.contrib.auth.hashers import make_password
        h = make_password('un-mot-de-passe-quelconque')
        partage = self._make_partage()
        partage.password_hash = h
        partage.save()
        partage.refresh_from_db()
        # TextField → aucune troncature, peu importe la longueur du hash.
        self.assertEqual(partage.password_hash, h)

    def test_public_requires_no_auth(self):
        """L'endpoint public est AllowAny : un jeton valide sert sans login."""
        from unittest import mock
        partage = self._make_partage()
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(b'%PDF-', None)):
            resp = APIClient().get(self._public_url(partage.token))
        # Jamais 401/403 pour un jeton valide sans mot de passe.
        self.assertEqual(resp.status_code, 200)


# ── GED21 — Filigrane & contrôle de diffusion ───────────────────────────────
class WatermarkServiceTests(TestCase):
    """GED21 — `services.apply_watermark` / `watermark_label` (unitaire).

    Couvre :
    - le filigrane PDF appelle PyMuPDF quand il est présent (helper patché) ;
    - le filigrane image appelle Pillow quand il est présent (helper patché) ;
    - DÉGRADE PROPREMENT : sans la lib (import patché en ImportError), on
      renvoie les octets d'origine + watermarked=False, sans lever ;
    - un type non pris en charge (texte/zip) est renvoyé inchangé ;
    - un contenu/texte vide laisse les octets inchangés ;
    - l'étiquette de confidentialité est bien construite côté serveur.
    """

    def test_apply_watermark_pdf_uses_pdf_helper(self):
        from unittest import mock
        out = b'%PDF-filigrane'
        with mock.patch('apps.ged.services._watermark_pdf',
                        return_value=(out, True)) as m:
            data, marked = services.apply_watermark(
                b'%PDF-1.4 src', 'application/pdf', 'CONFIDENTIEL')
        m.assert_called_once()
        self.assertTrue(marked)
        self.assertEqual(data, out)

    def test_apply_watermark_image_uses_image_helper(self):
        from unittest import mock
        out = b'\x89PNG-filigrane'
        with mock.patch('apps.ged.services._watermark_image',
                        return_value=(out, True)) as m:
            data, marked = services.apply_watermark(
                b'\x89PNG src', 'image/png', 'CONFIDENTIEL')
        m.assert_called_once()
        self.assertTrue(marked)
        self.assertEqual(data, out)

    def test_apply_watermark_unsupported_type_unchanged(self):
        """Un type non filigranable (texte/zip) est renvoyé tel quel."""
        src = b'contenu texte'
        data, marked = services.apply_watermark(
            src, 'text/plain', 'CONFIDENTIEL')
        self.assertFalse(marked)
        self.assertEqual(data, src)
        src2 = b'PK\x03\x04'
        data2, marked2 = services.apply_watermark(
            src2, 'application/zip', 'CONFIDENTIEL')
        self.assertFalse(marked2)
        self.assertEqual(data2, src2)

    def test_apply_watermark_empty_inputs_unchanged(self):
        self.assertEqual(
            services.apply_watermark(b'', 'application/pdf', 'X'), (b'', False))
        self.assertEqual(
            services.apply_watermark(b'%PDF', 'application/pdf', ''),
            (b'%PDF', False))

    def test_pdf_degrades_when_pymupdf_absent(self):
        """Sans PyMuPDF (`fitz` introuvable), on renvoie l'original sans lever."""
        from unittest import mock
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == 'fitz':
                raise ImportError('PyMuPDF non installé')
            return real_import(name, *args, **kwargs)

        src = b'%PDF-1.4 original'
        with mock.patch.object(builtins, '__import__', side_effect=fake_import):
            data, marked = services._watermark_pdf(src, 'CONFIDENTIEL')
        # Dégrade : octets d'origine, jamais d'exception.
        self.assertFalse(marked)
        self.assertEqual(data, src)

    def test_image_degrades_when_pillow_absent(self):
        """Sans Pillow (PIL introuvable), on renvoie l'original sans lever."""
        from unittest import mock
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == 'PIL' or name.startswith('PIL.'):
                raise ImportError('Pillow non installé')
            return real_import(name, *args, **kwargs)

        src = b'\x89PNG original'
        with mock.patch.object(builtins, '__import__', side_effect=fake_import):
            data, marked = services._watermark_image(src, 'CONFIDENTIEL')
        self.assertFalse(marked)
        self.assertEqual(data, src)

    def test_watermark_label_built_server_side(self):
        co = make_company('wm-label', 'Société Label')
        user = make_user(co, 'wm-user', 'admin')
        label = services.watermark_label(company=co, user=user)
        self.assertIn('CONFIDENTIEL', label)
        self.assertIn('Société Label', label)
        self.assertIn('wm-user', label)
        # Aucun segment vide quand société/utilisateur manquent.
        bare = services.watermark_label()
        self.assertTrue(bare.startswith('CONFIDENTIEL'))


class WatermarkApercuTests(GedBase):
    """GED21 — Le filigrane se branche sur l'aperçu authentifié (GED14).

    Couvre :
    - drapeau OFF → flux byte-identique (backward-compat, aucun appel filigrane) ;
    - drapeau ON + lib présente (helper patché) → contenu filigrané servi ;
    - drapeau ON mais lib absente (apply_watermark dégrade) → original servi,
      jamais d'erreur ;
    - une image filigranée est réémise en image/png.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Docs A')
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Contrat')
        cls.version_a = services.add_version(
            cls.doc_a, file_key='attachments/contrat.pdf',
            company=cls.co_a, filename='contrat.pdf', size=100,
            mime='application/pdf', uploaded_by=cls.admin_a)

    def _url(self, version_id):
        return f'/api/django/ged/versions/{version_id}/apercu/'

    def test_flag_off_streams_identical_bytes(self):
        """Drapeau désactivé → flux byte-identique (compat ascendante)."""
        from unittest import mock
        fake = b'%PDF-1.4 original'
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake, None)), \
                mock.patch('apps.ged.services.apply_watermark') as wm:
            resp = api.get(self._url(self.version_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, fake)
        # Jamais filigrané quand le drapeau est faux.
        wm.assert_not_called()

    def test_flag_on_watermarks_pdf(self):
        from unittest import mock
        self.doc_a.watermark_diffusion = True
        self.doc_a.save(update_fields=['watermark_diffusion'])
        src = b'%PDF-1.4 original'
        marked = b'%PDF-1.4 FILIGRANE'
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(src, None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(marked, True)) as wm:
            resp = api.get(self._url(self.version_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, marked)
        wm.assert_called_once()
        # Toujours servi inline (PDF).
        self.assertIn('inline', resp['Content-Disposition'])

    def test_flag_on_but_lib_absent_serves_original(self):
        """Drapeau ON mais filigrane indisponible → original servi, pas d'erreur."""
        from unittest import mock
        self.doc_a.watermark_diffusion = True
        self.doc_a.save(update_fields=['watermark_diffusion'])
        src = b'%PDF-1.4 original'
        api = auth(self.admin_a)
        # apply_watermark dégrade (lib absente) → renvoie l'original, marked=False.
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(src, None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(src, False)):
            resp = api.get(self._url(self.version_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, src)

    def test_watermarked_image_becomes_png(self):
        from unittest import mock
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Photo',
            watermark_diffusion=True)
        version_img = services.add_version(
            doc, file_key='attachments/photo.jpg', company=self.co_a,
            filename='photo.jpg', size=50, mime='image/jpeg',
            uploaded_by=self.admin_a)
        marked_png = b'\x89PNG filigrane'
        api = auth(self.admin_a)
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(b'\xff\xd8 jpeg', None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(marked_png, True)):
            resp = api.get(self._url(version_img.id))
        self.assertEqual(resp.status_code, 200)
        # Réémis en PNG (alpha du filigrane préservé).
        self.assertEqual(resp['Content-Type'], 'image/png')
        self.assertEqual(resp.content, marked_png)


class WatermarkPublicPartageTests(GedBase):
    """GED21 — Le filigrane se branche sur le téléchargement public (GED20).

    Couvre :
    - aucun drapeau → flux byte-identique (compat ascendante) ;
    - `PartageGed.watermark=True` → contenu filigrané servi (helper patché) ;
    - `Document.watermark_diffusion=True` → contenu filigrané même si le
      partage n'est pas marqué ;
    - la société du filigrane vient du DOCUMENT, jamais de la requête publique.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Docs A')
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Contrat A')
        cls.version_a = services.add_version(
            cls.doc_a, file_key='attachments/contrat-a.pdf',
            company=cls.co_a, filename='contrat-a.pdf', size=120,
            mime='application/pdf', uploaded_by=cls.admin_a)

    def _public_url(self, token):
        return f'/api/django/ged/public/{token}/'

    def test_no_flag_streams_identical_bytes(self):
        from unittest import mock
        partage = services.create_partage(
            document=self.doc_a, company=self.co_a, created_by=self.admin_a)
        fake = b'%PDF-1.4 original'
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(fake, None)), \
                mock.patch('apps.ged.services.apply_watermark') as wm:
            resp = APIClient().get(self._public_url(partage.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, fake)
        wm.assert_not_called()

    def test_partage_watermark_flag_watermarks(self):
        from unittest import mock
        partage = services.create_partage(
            document=self.doc_a, company=self.co_a,
            created_by=self.admin_a, watermark=True)
        self.assertTrue(partage.watermark)
        src = b'%PDF-1.4 original'
        marked = b'%PDF-1.4 FILIGRANE'
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(src, None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(marked, True)) as wm:
            resp = APIClient().get(self._public_url(partage.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, marked)
        wm.assert_called_once()

    def test_document_watermark_flag_watermarks_even_unmarked_partage(self):
        from unittest import mock
        self.doc_a.watermark_diffusion = True
        self.doc_a.save(update_fields=['watermark_diffusion'])
        partage = services.create_partage(
            document=self.doc_a, company=self.co_a, created_by=self.admin_a)
        self.assertFalse(partage.watermark)  # partage non marqué…
        src = b'%PDF-1.4 original'
        marked = b'%PDF-1.4 FILIGRANE'
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(src, None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(marked, True)) as wm:
            resp = APIClient().get(self._public_url(partage.token))
        self.assertEqual(resp.status_code, 200)
        # …mais le document l'est → filigrané quand même.
        self.assertEqual(resp.content, marked)
        wm.assert_called_once()

    def test_watermark_label_company_from_document_not_request(self):
        """SÉCURITÉ : la société du filigrane vient du document partagé, jamais
        d'une identité/société de la requête publique."""
        from unittest import mock
        partage = services.create_partage(
            document=self.doc_a, company=self.co_a,
            created_by=self.admin_a, watermark=True)
        captured = {}

        def fake_label(*, company=None, user=None):
            captured['company'] = company
            captured['user'] = user
            return 'CONFIDENTIEL'

        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(b'%PDF-1.4', None)), \
                mock.patch('apps.ged.services.watermark_label',
                           side_effect=fake_label), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(b'%PDF-wm', True)):
            # Même authentifié EN TANT QUE B, c'est la société du document (A).
            resp = auth(self.admin_b).get(self._public_url(partage.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(captured['company'].id, self.co_a.id)
        # L'endpoint public ne passe aucun utilisateur de requête au filigrane.
        self.assertIsNone(captured['user'])


# ── GED22 — Politiques de rétention (durée + action à l'échéance) ─────────
import datetime  # noqa: E402

from django.utils import timezone  # noqa: E402


class RetentionBase(GedBase):
    """Fixtures partagées : un dossier + des documents d'âge maîtrisé.

    `Document.created_at` est `auto_now_add` : pour maîtriser l'âge, on POSE la
    date de création explicitement via un UPDATE en base (qui ne ré-applique pas
    `auto_now_add`)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Dossier A')
        cls.sub_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, parent=cls.folder_a,
            nom='Sous A')

    def make_doc(self, *, folder=None, nom='Doc', age_jours=0,
                 company=None, custom_data=None):
        company = company or self.co_a
        folder = folder or self.folder_a
        doc = Document.objects.create(
            company=company, folder=folder, nom=nom,
            custom_data=custom_data or {})
        if age_jours:
            created = timezone.now() - datetime.timedelta(days=age_jours)
            Document.objects.filter(pk=doc.pk).update(created_at=created)
            doc.refresh_from_db()
        return doc


class PolitiqueRetentionModelTests(RetentionBase):
    def test_default_action_is_signaler_not_destructive(self):
        """Une politique naît « signaler » (consultatif) — jamais destructive."""
        pol = PolitiqueRetention.objects.create(
            company=self.co_a, nom='Standard', duree_conservation_jours=365)
        self.assertEqual(pol.action_echeance, RETENTION_SIGNALER)
        self.assertFalse(pol.is_destructive)

    def test_scope_resolution(self):
        glob = PolitiqueRetention.objects.create(
            company=self.co_a, nom='G', duree_conservation_jours=10)
        cab = PolitiqueRetention.objects.create(
            company=self.co_a, nom='C', duree_conservation_jours=10,
            cabinet=self.cab_a)
        fol = PolitiqueRetention.objects.create(
            company=self.co_a, nom='F', duree_conservation_jours=10,
            folder=self.folder_a)
        typ = PolitiqueRetention.objects.create(
            company=self.co_a, nom='T', duree_conservation_jours=10,
            type_document='contrat')
        self.assertEqual(glob.scope, 'global')
        self.assertEqual(cab.scope, 'cabinet')
        self.assertEqual(fol.scope, 'dossier')
        self.assertEqual(typ.scope, 'type')
        # dossier > cabinet > type > global
        self.assertGreater(fol.scope_rank, cab.scope_rank)
        self.assertGreater(cab.scope_rank, typ.scope_rank)
        self.assertGreater(typ.scope_rank, glob.scope_rank)

    def test_clean_rejects_cabinet_and_folder_together(self):
        from django.core.exceptions import ValidationError
        pol = PolitiqueRetention(
            company=self.co_a, nom='Bad', duree_conservation_jours=10,
            cabinet=self.cab_a, folder=self.folder_a)
        with self.assertRaises(ValidationError):
            pol.clean()


class DocumentsEchusTests(RetentionBase):
    def test_picks_only_overdue_documents(self):
        """Seuls les documents dont l'âge DÉPASSE la durée sont échus."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='30 jours', duree_conservation_jours=30)
        vieux = self.make_doc(nom='Vieux', age_jours=40)
        jeune = self.make_doc(nom='Jeune', age_jours=10)
        echus = selectors.documents_echus(self.co_a)
        ids = [d.id for d, _, _ in echus]
        self.assertIn(vieux.id, ids)
        self.assertNotIn(jeune.id, ids)

    def test_boundary_strictly_greater(self):
        """Âge == durée n'est PAS échu ; âge > durée l'est."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='30', duree_conservation_jours=30)
        pile = self.make_doc(nom='Pile30', age_jours=30)
        un_jour = self.make_doc(nom='31', age_jours=31)
        ids = [d.id for d, _, _ in selectors.documents_echus(self.co_a)]
        self.assertNotIn(pile.id, ids)
        self.assertIn(un_jour.id, ids)

    def test_most_specific_policy_wins(self):
        """Une politique de dossier (plus spécifique) prime sur la globale."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='Global 100', duree_conservation_jours=100)
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='Dossier 10', duree_conservation_jours=10,
            folder=self.folder_a)
        doc = self.make_doc(folder=self.folder_a, nom='D', age_jours=20)
        echus = selectors.documents_echus(self.co_a)
        # 20 j > 10 (dossier) mais < 100 (global) → échu via la politique dossier.
        match = [(d, p, n) for d, p, n in echus if d.id == doc.id]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0][1].nom, 'Dossier 10')

    def test_folder_policy_covers_subtree(self):
        """Une politique de dossier couvre aussi les sous-dossiers (chemin)."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='Dossier 10', duree_conservation_jours=10,
            folder=self.folder_a)
        doc = self.make_doc(folder=self.sub_a, nom='Sub', age_jours=20)
        ids = [d.id for d, _, _ in selectors.documents_echus(self.co_a)]
        self.assertIn(doc.id, ids)

    def test_today_is_injectable(self):
        """Le paramètre `today` est propagé jusqu'au calcul d'âge."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='30', duree_conservation_jours=30)
        doc = self.make_doc(nom='D', age_jours=10)
        # À aujourd'hui : 10 j < 30 → pas échu.
        self.assertEqual(selectors.documents_echus(self.co_a), [])
        # En projetant 60 jours dans le futur : 70 j > 30 → échu.
        futur = timezone.localdate() + datetime.timedelta(days=60)
        ids = [d.id for d, _, _ in selectors.documents_echus(
            self.co_a, today=futur)]
        self.assertIn(doc.id, ids)

    def test_today_accepts_datetime(self):
        """`today` accepte un datetime (ramené à une date)."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='30', duree_conservation_jours=30)
        doc = self.make_doc(nom='D', age_jours=40)
        ids = [d.id for d, _, _ in selectors.documents_echus(
            self.co_a, today=timezone.now())]
        self.assertIn(doc.id, ids)

    def test_inactive_policy_ignored(self):
        """Une politique inactive ne rend aucun document échu."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='Off', duree_conservation_jours=10,
            actif=False)
        self.make_doc(nom='D', age_jours=99)
        self.assertEqual(selectors.documents_echus(self.co_a), [])

    def test_no_policy_means_no_echus(self):
        """Sans aucune politique, aucun document n'est échu (court-circuit)."""
        self.make_doc(nom='D', age_jours=9999)
        self.assertEqual(selectors.documents_echus(self.co_a), [])

    def test_tenant_isolation(self):
        """`documents_echus` ne voit jamais les documents d'une autre société."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='30', duree_conservation_jours=30)
        cab_b = Cabinet.objects.create(company=self.co_b, nom='Cab B')
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=cab_b, nom='Dossier B')
        self.make_doc(company=self.co_b, folder=folder_b,
                      nom='Etranger', age_jours=999)
        echus = selectors.documents_echus(self.co_a)
        self.assertEqual(echus, [])  # aucun doc de A échu, B jamais inclus

    def test_supprimer_action_does_not_delete(self):
        """Même une politique « supprimer » NE supprime jamais passivement."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='Purge', duree_conservation_jours=10,
            action_echeance=RETENTION_SUPPRIMER)
        doc = self.make_doc(nom='D', age_jours=50)
        echus = selectors.documents_echus(self.co_a)
        ids = [d.id for d, _, _ in echus]
        self.assertIn(doc.id, ids)
        # Le document est LISTÉ mais TOUJOURS PRÉSENT — jamais effacé.
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())


class PolitiqueRetentionApiTests(RetentionBase):
    URL = '/api/django/ged/politiques-retention/'

    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'nom': 'Standard',
            'duree_conservation_jours': 365,
            # Tentative d'injecter une autre société — doit être ignorée.
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pol = PolitiqueRetention.objects.get(id=resp.data['id'])
        self.assertEqual(pol.company_id, self.co_a.id)
        self.assertEqual(pol.created_by_id, self.admin_a.id)
        # Défaut consultatif : action « signaler ».
        self.assertEqual(pol.action_echeance, RETENTION_SIGNALER)

    def test_tenant_isolation_list(self):
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='A', duree_conservation_jours=10)
        PolitiqueRetention.objects.create(
            company=self.co_b, nom='B', duree_conservation_jours=10)
        resp = auth(self.admin_a).get(self.URL)
        self.assertEqual(resp.status_code, 200)
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('A', noms)
        self.assertNotIn('B', noms)

    def test_rejects_zero_duration(self):
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'nom': 'Bad', 'duree_conservation_jours': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_rejects_cabinet_and_folder_together(self):
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'nom': 'Bad', 'duree_conservation_jours': 10,
            'cabinet': self.cab_a.id, 'folder': self.folder_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_rejects_cross_company_folder(self):
        cab_b = Cabinet.objects.create(company=self.co_b, nom='Cab B')
        folder_b = Folder.objects.create(
            company=self.co_b, cabinet=cab_b, nom='B')
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'nom': 'X', 'duree_conservation_jours': 10, 'folder': folder_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_write_requires_responsable_role(self):
        """Création refusée (403) à un compte sans rôle d'écriture."""
        viewer = make_user(self.co_a, 'ged22-viewer', 'normal')
        api = auth(viewer)
        resp = api.post(self.URL, {
            'nom': 'NoRights', 'duree_conservation_jours': 10,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_read_allowed_to_any_role(self):
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='A', duree_conservation_jours=10)
        viewer = make_user(self.co_a, 'ged22-viewer2', 'normal')
        resp = auth(viewer).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_echus_endpoint_lists_overdue(self):
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='30', duree_conservation_jours=30)
        doc = self.make_doc(nom='Vieux', age_jours=40)
        resp = auth(self.admin_a).get(self.URL + 'echus/')
        self.assertEqual(resp.status_code, 200, resp.data)
        doc_ids = [row['document'] for row in resp.data]
        self.assertIn(doc.id, doc_ids)
        # Et le document existe toujours — l'endpoint ne supprime rien.
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())


# ── GED23 — Archivage légal à valeur probante (write-once / object-lock) ──────
class ArchivageLegalBase(GedBase):
    """Fixtures : un dossier + un document avec une version (checksum figé).

    Le `checksum` posé sur la version sert de repli au `hash_integrite` quand le
    contenu MinIO n'est pas récupérable en test (degrade path de l'object-lock /
    du recalcul). On force `fetch_attachment` à échouer partout ici pour rester
    déterministe et hermétique au stockage."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cls.cab_a, nom='Dossier A')
        cls.doc_a = Document.objects.create(
            company=cls.co_a, folder=cls.folder_a, nom='Contrat')
        cls.cs = services.compute_checksum(b'contenu probant')
        cls.version_a = services.add_version(
            cls.doc_a, file_key='attachments/contrat.pdf', company=cls.co_a,
            checksum=cls.cs, uploaded_by=cls.admin_a)


def _no_storage(*a, **k):
    """fetch_attachment introuvable → force le repli sur version.checksum."""
    return None, 'Fichier introuvable.'


class ArchivageLegalServiceTests(ArchivageLegalBase):
    def test_archive_records_hash_and_server_side_fields(self):
        """archiver_legalement fige le hash + pose company/archive_par serveur."""
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            arch = services.archiver_legalement(
                self.doc_a, user=self.admin_a, motif='Clôture exercice')
        self.assertEqual(arch.company_id, self.co_a.id)
        self.assertEqual(arch.archive_par_id, self.admin_a.id)
        self.assertEqual(arch.version_id, self.version_a.id)
        # Hash d'intégrité = SHA-256 (repli sur le checksum de la version).
        self.assertEqual(arch.hash_integrite, self.cs)
        self.assertEqual(len(arch.hash_integrite), 64)
        self.assertTrue(self.doc_a.est_archive_legalement)

    def test_archive_recomputes_hash_from_stored_content(self):
        """Quand le contenu est récupérable, le hash est recalculé dessus."""
        from unittest import mock
        contenu = b'octets reellement stockes'
        attendu = services.compute_checksum(contenu)
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(contenu, None)):
            arch = services.archiver_legalement(self.doc_a, user=self.admin_a)
        self.assertEqual(arch.hash_integrite, attendu)

    def test_write_once_blocks_document_edit(self):
        """Un document archivé est IMMUABLE : save() est refusé (write-once)."""
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            services.archiver_legalement(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        self.doc_a.nom = 'Renommé'
        with self.assertRaises(ArchivageLegalError):
            self.doc_a.save()

    def test_write_once_blocks_document_delete(self):
        """Un document archivé ne peut pas être supprimé (write-once)."""
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            services.archiver_legalement(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        with self.assertRaises(ArchivageLegalError):
            self.doc_a.delete()
        self.assertTrue(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_write_once_blocks_new_version(self):
        """On n'ajoute plus de version à un document archivé."""
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            services.archiver_legalement(self.doc_a, user=self.admin_a)
        with self.assertRaises(ArchivageLegalError):
            services.add_version(
                self.doc_a, file_key='attachments/v2.pdf', company=self.co_a,
                uploaded_by=self.admin_a)

    def test_write_once_blocks_version_edit_and_delete(self):
        """Les versions d'un document archivé sont figées (edit + delete)."""
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            services.archiver_legalement(self.doc_a, user=self.admin_a)
        self.version_a.refresh_from_db()
        self.version_a.filename = 'autre.pdf'
        with self.assertRaises(ArchivageLegalError):
            self.version_a.save()
        with self.assertRaises(ArchivageLegalError):
            self.version_a.delete()

    def test_write_once_blocks_lifecycle_and_checkout_and_move(self):
        """Cycle de vie / check-out / déplacement refusés sur un doc archivé."""
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            services.archiver_legalement(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        with self.assertRaises(PermissionError):
            services.change_lifecycle_status(
                self.doc_a, 'revue', user=self.admin_a)
        with self.assertRaises(PermissionError):
            services.checkout_document(self.doc_a, self.admin_a)
        autre = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Autre')
        with self.assertRaises(ValueError):
            services.move_document(self.doc_a, autre)

    def test_archivage_record_is_immutable(self):
        """L'enregistrement ArchivageLegal lui-même est immuable (create-only)."""
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            arch = services.archiver_legalement(self.doc_a, user=self.admin_a)
        arch.motif = 'modifié'
        with self.assertRaises(ArchivageLegalError):
            arch.save()
        with self.assertRaises(ArchivageLegalError):
            arch.delete()

    def test_double_archive_rejected(self):
        """Write-once : un document n'est archivé légalement qu'une seule fois."""
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            services.archiver_legalement(self.doc_a, user=self.admin_a)
            with self.assertRaises(ValueError):
                services.archiver_legalement(self.doc_a, user=self.admin_a)

    def test_cross_company_archive_rejected(self):
        """On n'archive pas le document d'une autre société."""
        with self.assertRaises(PermissionError):
            services.archiver_legalement(self.doc_a, user=self.admin_b)

    def test_object_lock_degrades_gracefully_when_unsupported(self):
        """L'object-lock non supporté NE bloque PAS l'archivage (degrade)."""
        from unittest import mock
        today = timezone.localdate()
        # Le client MinIO lève (object-lock non supporté) → on dégrade.
        fake_client = mock.Mock()
        fake_client.put_object_retention.side_effect = Exception('not supported')
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage), \
                mock.patch('apps.ventes.utils.minio_client.get_minio_client',
                           return_value=fake_client):
            arch = services.archiver_legalement(
                self.doc_a, user=self.admin_a,
                retain_until=today + datetime.timedelta(days=30))
        # L'archivage existe et est valide ; seul le verrou objet a échoué.
        self.assertTrue(self.doc_a.est_archive_legalement)
        self.assertFalse(arch.object_lock_applique)
        # La date de rétention demandée est néanmoins consignée.
        self.assertEqual(arch.object_lock_retain_until,
                         today + datetime.timedelta(days=30))

    def test_object_lock_applied_when_supported(self):
        """Quand le backend supporte l'object-lock, le verrou est marqué posé."""
        from unittest import mock
        today = timezone.localdate()
        fake_client = mock.Mock()
        fake_client.put_object_retention.return_value = {}
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage), \
                mock.patch('apps.ventes.utils.minio_client.get_minio_client',
                           return_value=fake_client):
            arch = services.archiver_legalement(
                self.doc_a, user=self.admin_a,
                retain_until=today + datetime.timedelta(days=10))
        self.assertTrue(arch.object_lock_applique)
        fake_client.put_object_retention.assert_called_once()


class ArchivageLegalApiTests(ArchivageLegalBase):
    URL = '/api/django/ged/archivages-legaux/'

    def _archive_via_service(self):
        from unittest import mock
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            return services.archiver_legalement(self.doc_a, user=self.admin_a)

    def test_create_action_archives_document(self):
        """POST documents/<id>/archiver-legalement/ archive (company serveur)."""
        from unittest import mock
        api = auth(self.admin_a)
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            resp = api.post(
                f'/api/django/ged/documents/{self.doc_a.id}/'
                'archiver-legalement/',
                {'motif': 'Probant', 'company': self.co_b.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        arch = ArchivageLegal.objects.get(id=resp.data['id'])
        self.assertEqual(arch.company_id, self.co_a.id)
        self.assertEqual(arch.archive_par_id, self.admin_a.id)
        self.assertEqual(arch.hash_integrite, self.cs)

    def test_create_viewset_archives_document(self):
        """POST archivages-legaux/ crée (company/archive_par côté serveur)."""
        from unittest import mock
        api = auth(self.admin_a)
        with mock.patch('apps.records.storage.fetch_attachment',
                        side_effect=_no_storage):
            resp = api.post(self.URL, {
                'document': self.doc_a.id,
                'company': self.co_b.id,  # injection ignorée
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        arch = ArchivageLegal.objects.get(id=resp.data['id'])
        self.assertEqual(arch.company_id, self.co_a.id)

    def test_archived_document_edit_returns_403(self):
        """PATCH d'un document archivé renvoie 403 (write-once)."""
        self._archive_via_service()
        resp = auth(self.admin_a).patch(
            f'/api/django/ged/documents/{self.doc_a.id}/',
            {'nom': 'Hack'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_archived_document_delete_returns_403(self):
        """DELETE d'un document archivé renvoie 403 (write-once)."""
        self._archive_via_service()
        resp = auth(self.admin_a).delete(
            f'/api/django/ged/documents/{self.doc_a.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_archived_document_checkout_is_blocked(self):
        """GED23 — check-out d'un document archivé est BLOQUÉ (409 write-once).

        `checkout_document` garde déjà l'archivage et lève `PermissionError`, que
        l'action traduit en 409 avec le message write-once — jamais 200, jamais
        500 : le document immuable ne peut pas être extrait pour modification.
        """
        self._archive_via_service()
        resp = auth(self.admin_a).post(
            f'/api/django/ged/documents/{self.doc_a.id}/check-out/')
        self.assertEqual(resp.status_code, 409, resp.data)

    def test_update_and_delete_not_allowed_on_archivage(self):
        """L'API archivages-legaux n'expose ni update ni delete (immuable)."""
        arch = self._archive_via_service()
        api = auth(self.admin_a)
        r_patch = api.patch(f'{self.URL}{arch.id}/', {'motif': 'x'},
                            format='json')
        self.assertEqual(r_patch.status_code, 405)
        r_del = api.delete(f'{self.URL}{arch.id}/')
        self.assertEqual(r_del.status_code, 405)

    def test_tenant_isolation_list(self):
        arch = self._archive_via_service()
        # Un doc + archivage côté B.
        doc_b = Document.objects.create(
            company=self.co_b, folder=Folder.objects.create(
                company=self.co_b, cabinet=self.cab_b, nom='Dos B'),
            nom='Doc B')
        ArchivageLegal.objects.create(company=self.co_b, document=doc_b)
        resp = auth(self.admin_a).get(self.URL)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(arch.id, ids)
        self.assertNotIn(
            ArchivageLegal.objects.get(document=doc_b).id, ids)

    def test_create_requires_responsable_role(self):
        """Archivage refusé (403) à un compte sans rôle d'écriture."""
        viewer = make_user(self.co_a, 'ged23-viewer', 'normal')
        resp = auth(viewer).post(self.URL, {'document': self.doc_a.id},
                                 format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_read_allowed_to_any_role(self):
        self._archive_via_service()
        viewer = make_user(self.co_a, 'ged23-viewer2', 'normal')
        resp = auth(viewer).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_create_rejects_cross_company_document(self):
        """On n'archive pas le document d'une autre société via l'API."""
        doc_b = Document.objects.create(
            company=self.co_b, folder=Folder.objects.create(
                company=self.co_b, cabinet=self.cab_b, nom='Dos B'),
            nom='Doc B')
        resp = auth(self.admin_a).post(
            self.URL, {'document': doc_b.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
