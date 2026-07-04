"""XGED23 — Workflow de disposition fin de rétention avec approbation +
certificat de destruction.

Couvre :
  * un lot échu passe en revue (création d'une DemandeDisposition) ;
  * l'approbation exécute et produit le certificat de destruction ;
  * le rejet CONSERVE tous les documents du lot ;
  * un legal hold exclut le document du lot (création ET exécution) ;
  * isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, CertificatDestruction, DemandeDisposition,
    DemandeDispositionError, Document, Folder, LegalHold,
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


class XGed23Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged23-a', 'Xged23 A')
        self.admin_a = make_user(self.co_a, 'xged23-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Archives')
        self.doc1 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='vieux-devis.pdf')
        self.doc2 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='vieux-bl.pdf')


class ServiceTests(XGed23Base):
    def test_creer_lot_disposition(self):
        demande = services.creer_demande_disposition(
            self.co_a, libelle='Purge 2020', document_ids=[
                self.doc1.pk, self.doc2.pk], user=self.admin_a)
        self.assertEqual(demande.statut, 'en_attente')
        self.assertCountEqual(demande.documents, [self.doc1.pk, self.doc2.pk])

    def test_legal_hold_exclut_document_a_la_creation(self):
        LegalHold.objects.create(
            company=self.co_a, document=self.doc1, place_par=self.admin_a,
            actif=True)
        demande = services.creer_demande_disposition(
            self.co_a, libelle='Purge 2020', document_ids=[
                self.doc1.pk, self.doc2.pk], user=self.admin_a)
        self.assertEqual(demande.documents, [self.doc2.pk])

    def test_creation_vide_si_tout_exclu(self):
        LegalHold.objects.create(
            company=self.co_a, document=self.doc1, place_par=self.admin_a,
            actif=True)
        with self.assertRaises(ValueError):
            services.creer_demande_disposition(
                self.co_a, libelle='Purge 2020',
                document_ids=[self.doc1.pk], user=self.admin_a)

    def test_approbation_puis_execution_detruit_et_certifie(self):
        demande = services.creer_demande_disposition(
            self.co_a, libelle='Purge 2020', document_ids=[
                self.doc1.pk, self.doc2.pk], user=self.admin_a)
        services.approuver_demande_disposition(demande, user=self.admin_a)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'approuvee')

        certificats = services.executer_demande_disposition(
            demande, user=self.admin_a)
        self.assertEqual(len(certificats), 2)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'executee')
        self.assertFalse(Document.objects.filter(pk=self.doc1.pk).exists())
        self.assertFalse(Document.objects.filter(pk=self.doc2.pk).exists())
        self.assertEqual(
            CertificatDestruction.objects.filter(demande=demande).count(), 2)

    def test_rejet_conserve_les_documents(self):
        demande = services.creer_demande_disposition(
            self.co_a, libelle='Purge 2020', document_ids=[
                self.doc1.pk, self.doc2.pk], user=self.admin_a)
        services.rejeter_demande_disposition(demande, user=self.admin_a)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'rejetee')
        self.assertTrue(Document.objects.filter(pk=self.doc1.pk).exists())
        self.assertTrue(Document.objects.filter(pk=self.doc2.pk).exists())

    def test_hold_pose_apres_approbation_protege_a_execution(self):
        demande = services.creer_demande_disposition(
            self.co_a, libelle='Purge 2020', document_ids=[
                self.doc1.pk, self.doc2.pk], user=self.admin_a)
        services.approuver_demande_disposition(demande, user=self.admin_a)
        LegalHold.objects.create(
            company=self.co_a, document=self.doc1, place_par=self.admin_a,
            actif=True)
        certificats = services.executer_demande_disposition(
            demande, user=self.admin_a)
        self.assertEqual(len(certificats), 1)
        self.assertTrue(Document.objects.filter(pk=self.doc1.pk).exists())
        self.assertFalse(Document.objects.filter(pk=self.doc2.pk).exists())

    def test_execution_sans_approbation_leve(self):
        demande = services.creer_demande_disposition(
            self.co_a, libelle='Purge 2020', document_ids=[
                self.doc1.pk], user=self.admin_a)
        with self.assertRaises(DemandeDispositionError):
            services.executer_demande_disposition(demande, user=self.admin_a)

    def test_decision_double_leve(self):
        demande = services.creer_demande_disposition(
            self.co_a, libelle='Purge 2020', document_ids=[
                self.doc1.pk], user=self.admin_a)
        services.approuver_demande_disposition(demande, user=self.admin_a)
        with self.assertRaises(DemandeDispositionError):
            services.approuver_demande_disposition(demande, user=self.admin_a)


class ViewTests(XGed23Base):
    def test_creer_approuver_executer_via_api(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/demandes-disposition/', {
            'libelle': 'Purge 2020', 'action': 'detruire',
            'documents': [self.doc1.pk, self.doc2.pk],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        demande_id = resp.data['id']

        resp2 = api.post(
            f'/api/django/ged/demandes-disposition/{demande_id}/approuver/')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['statut'], 'approuvee')

        resp3 = api.post(
            f'/api/django/ged/demandes-disposition/{demande_id}/executer/')
        self.assertEqual(resp3.status_code, 200, resp3.data)
        self.assertEqual(resp3.data['statut'], 'executee')
        self.assertEqual(len(resp3.data['certificats']), 2)

    def test_isolation_societe(self):
        co_b = make_company('xged23-b', 'Xged23 B')
        admin_b = make_user(co_b, 'xged23-admin-b', 'admin')
        demande = DemandeDisposition.objects.create(
            company=self.co_a, libelle='Purge A', documents=[self.doc1.pk])
        api_b = auth(admin_b)
        resp = api_b.get(f'/api/django/ged/demandes-disposition/{demande.pk}/')
        self.assertEqual(resp.status_code, 404)
