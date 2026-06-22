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
from apps.ged.models import Cabinet, Document, DocumentLien, DocumentVersion, Folder

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
