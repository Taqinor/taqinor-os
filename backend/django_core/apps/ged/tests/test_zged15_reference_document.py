"""ZGED15 — Numérotation de référence lisible des documents GED (par société
+ mois).

Couvre :
  * un nouveau document reçoit une référence lisible unique par société ;
  * deux créations concurrentes (même mois) ne collisionnent pas (unicité
    en base, sous IntegrityError des couples dupliqués) ;
  * le backfill (migration data 0043) donne des références distinctes aux
    anciens documents ;
  * la référence est cherchable (search_fields) et affichée par le
    serializer ;
  * scoping société (deux sociétés peuvent réutiliser le même numéro).
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.models import Cabinet, Document, Folder

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


class ZGed15Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged15-a', 'Zged15 A')
        self.co_b = make_company('zged15-b', 'Zged15 B')
        self.admin_a = make_user(self.co_a, 'zged15-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'zged15-admin-b', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Admin')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Contrats')


class ModelTests(ZGed15Base):
    def test_nouveau_document_recoit_reference_lisible_unique(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='doc1.pdf')
        self.assertTrue(doc.reference)
        self.assertRegex(doc.reference, r'^DOC-\d{6}-\d{4}$')

    def test_deux_documents_meme_societe_meme_mois_ont_references_distinctes(self):
        doc1 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='doc1.pdf')
        doc2 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='doc2.pdf')
        self.assertNotEqual(doc1.reference, doc2.reference)

    def test_references_scopees_par_societe_meme_numero_reutilisable(self):
        doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='doc-a.pdf')
        doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='doc-b.pdf')
        # Les deux sociétés démarrent leur propre séquence : même suffixe
        # -0001 possible pour chacune, jamais de collision cross-société.
        self.assertTrue(doc_a.reference.endswith('-0001'))
        self.assertTrue(doc_b.reference.endswith('-0001'))

    def test_creation_concurrente_meme_reference_leve_integrity_error(self):
        """Deux documents forcés à porter LA MÊME référence (course simulée,
        en bypassant l'auto-assignation de `save()`) doivent être bloqués par
        la contrainte d'unicité (company, reference) — jamais une collision
        silencieuse, dernier rempart derrière le retry applicatif."""
        Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='doc1.pdf',
            reference='DUP-0001')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                doc2 = Document(
                    company=self.co_a, folder=self.folder_a, nom='doc2.pdf',
                    reference='DUP-0001')
                Model.save(doc2)

    def test_document_lien_sans_fichier_recoit_aussi_une_reference(self):
        from apps.ged.services import creer_document_lien
        doc = creer_document_lien(
            folder=self.folder_a, company=self.co_a,
            nom='lien-externe', url_externe='https://example.com/x',
            created_by=self.admin_a)
        self.assertTrue(doc.reference)


class BackfillTests(TestCase):
    def test_backfill_migration_donne_references_distinctes(self):
        import importlib

        from django.apps import apps as django_apps

        module = importlib.import_module(
            'apps.ged.migrations.0043_zged15_backfill_document_reference')

        co = make_company('zged15-backfill', 'Zged15 Backfill')
        cab = Cabinet.objects.create(company=co, nom='Admin')
        folder = Folder.objects.create(company=co, cabinet=cab, nom='F')
        # Crée des documents puis efface la référence auto-assignée pour
        # simuler des lignes historiques pré-ZGED15 (jamais de référence).
        doc1 = Document.objects.create(company=co, folder=folder, nom='a.pdf')
        doc2 = Document.objects.create(company=co, folder=folder, nom='b.pdf')
        Document.objects.filter(pk__in=[doc1.pk, doc2.pk]).update(reference='')

        module.backfill_references(django_apps, None)

        doc1.refresh_from_db()
        doc2.refresh_from_db()
        self.assertTrue(doc1.reference)
        self.assertTrue(doc2.reference)
        self.assertNotEqual(doc1.reference, doc2.reference)

    def test_backfill_idempotent_ne_retouche_pas_reference_existante(self):
        import importlib

        from django.apps import apps as django_apps

        module = importlib.import_module(
            'apps.ged.migrations.0043_zged15_backfill_document_reference')

        co = make_company('zged15-backfill-idem', 'Zged15 Backfill Idem')
        cab = Cabinet.objects.create(company=co, nom='Admin')
        folder = Folder.objects.create(company=co, cabinet=cab, nom='F')
        doc = Document.objects.create(company=co, folder=folder, nom='a.pdf')
        original_reference = doc.reference

        module.backfill_references(django_apps, None)

        doc.refresh_from_db()
        self.assertEqual(doc.reference, original_reference)


class ApiTests(ZGed15Base):
    def test_reference_visible_et_cherchable_via_api(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='facture-2026.pdf')
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{doc.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['reference'], doc.reference)

        resp_search = api.get(
            '/api/django/ged/documents/', {'search': doc.reference})
        self.assertEqual(resp_search.status_code, 200)
        ids = [d['id'] for d in resp_search.data.get(
            'results', resp_search.data)]
        self.assertIn(doc.pk, ids)

    def test_reference_non_modifiable_par_patch(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='doc.pdf')
        original_reference = doc.reference
        api = auth(self.admin_a)
        resp = api.patch(
            f'/api/django/ged/documents/{doc.pk}/',
            {'reference': 'HACKED-000001'}, format='json')
        self.assertEqual(resp.status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.reference, original_reference)
