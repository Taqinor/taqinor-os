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
    Cabinet, Coffre, Document, DocumentLien, DocumentTag,
    DocumentTagAssignment, DocumentVersion, Folder,
)

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
    def setUp(self):
        self.co_a = make_company('ged-a', 'Ged A')
        self.co_b = make_company('ged-b', 'Ged B')
        self.admin_a = make_user(self.co_a, 'ged-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'ged-admin-b', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Administratif')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Administratif')


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
        self.assertFalse(Document.objects.filter(id=doc.id).exists())


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
    def setUp(self):
        super().setUp()
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Docs A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Facture CIN')

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

    def setUp(self):
        super().setUp()
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Docs A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat')
        self.client_a = Client.objects.create(company=self.co_a, nom='Client A')

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


# ── GED7 — import des records.Attachment existants dans la GED ──────
class MigrateAttachmentsToGedTests(GedBase):
    """GED7 — `migrate_attachments_to_ged` : import idempotent des pièces jointes.

    Couvre : création de Document réutilisant le file_key (aucun fichier
    recopié), pose du DocumentLien quand la cible est autorisée, idempotence
    (re-lancer ne duplique rien), isolation multi-tenant, originaux intacts,
    cabinet/dossier d'atterrissage par défaut, et le mode --dry-run.
    """

    def setUp(self):
        super().setUp()
        self.client_a = Client.objects.create(company=self.co_a, nom='Client A')
        self.client_b = Client.objects.create(company=self.co_b, nom='Client B')
        ct_client = ContentType.objects.get_for_model(Client)
        # Pièce jointe de A ciblant un client autorisé (→ doit donner un lien).
        self.att_a = Attachment.objects.create(
            company=self.co_a, content_type=ct_client,
            object_id=self.client_a.id, file_key='co_a/keyA.pdf',
            filename='contrat-a.pdf', size=1234, mime='application/pdf',
            uploaded_by=self.admin_a)
        # Pièce jointe de B (autre société) ciblant son propre client.
        self.att_b = Attachment.objects.create(
            company=self.co_b, content_type=ct_client,
            object_id=self.client_b.id, file_key='co_b/keyB.pdf',
            filename='contrat-b.pdf', size=99, mime='application/pdf',
            uploaded_by=self.admin_b)

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

    def setUp(self):
        super().setUp()
        # Deux employés non-admin de la société A + un client.
        self.emp1 = make_user(self.co_a, 'ged-emp1', 'normal')
        self.emp2 = make_user(self.co_a, 'ged-emp2', 'normal')
        self.client_a = Client.objects.create(
            company=self.co_a, nom='Client A', email='ca@example.com')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Racine')
        # Coffre de emp1.
        self.coffre1 = Coffre.objects.create(
            company=self.co_a, nom='Coffre emp1', proprietaire=self.emp1)
        # Document dans le coffre de emp1.
        self.doc_secret = Document.objects.create(
            company=self.co_a, folder=self.folder_a, coffre=self.coffre1,
            nom='Bulletin de paie emp1')
        # Document hors coffre (visible de tous).
        self.doc_public = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Note de service')

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

    def setUp(self):
        super().setUp()
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Racine')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat X')

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

    def setUp(self):
        super().setUp()
        from apps.customfields.models import CustomFieldDef
        self.CFD = CustomFieldDef
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Racine')
        # Une définition obligatoire (texte) + une de choix sur le module doc.
        self.CFD.objects.create(
            company=self.co_a, module='document', code='reference',
            libelle='Référence', type='text', obligatoire=True)
        self.CFD.objects.create(
            company=self.co_a, module='document', code='confidentialite',
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

    def setUp(self):
        super().setUp()
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Racine')

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

    def setUp(self):
        super().setUp()
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Racine')

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


# ── U14 — Upload « en un appel » (document + version 1) via televerser ──
class DocumentUploadTests(GedBase):
    """L'action multipart `documents/televerser/` crée le document ET sa
    première version en un seul appel, en RÉUTILISANT `records.storage`
    (mocké ici pour ne pas toucher MinIO). Company/créateur/uploader posés
    côté serveur ; dossier cible borné à la société (isolation préservée).
    """
    def setUp(self):
        super().setUp()
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Docs A')

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

    def setUp(self):
        super().setUp()
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Docs A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat')
        self.version_a = services.add_version(
            self.doc_a, file_key='attachments/contrat.pdf',
            company=self.co_a, filename='contrat.pdf', size=100,
            mime='application/pdf', uploaded_by=self.admin_a)

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

    def setUp(self):
        super().setUp()
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Docs A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat')
        # Crée deux versions initiales.
        self.v1 = services.add_version(
            self.doc_a, file_key='docs/v1.pdf', company=self.co_a,
            filename='v1.pdf', size=100, mime='application/pdf',
            checksum='aaa', uploaded_by=self.admin_a)
        self.v2 = services.add_version(
            self.doc_a, file_key='docs/v2.pdf', company=self.co_a,
            filename='v2.pdf', size=200, mime='application/pdf',
            checksum='bbb', uploaded_by=self.admin_a)

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
