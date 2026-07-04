"""XGED8 — Checklist de pièces requises + demandes de documents manquants.

Couvre :
  * un dossier affiche requis/présent/manquant (checklist) ;
  * une demande crée le placeholder puis se solde automatiquement au dépôt
    correspondant (matching par dossier) ;
  * relances incrémentent le compteur ;
  * scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, DEMANDE_DOC_SOLDEE, DemandeDocument, Document, ExigenceDossier,
    Folder,
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


class XGed8Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged8-a', 'Xged8 A')
        self.co_b = make_company('xged8-b', 'Xged8 B')
        self.admin_a = make_user(self.co_a, 'xged8-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='RH')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier Salarié')


class ChecklistTests(XGed8Base):
    def test_checklist_shows_present_and_missing(self):
        exigence = ExigenceDossier.objects.create(
            company=self.co_a, folder=self.folder_a, libelle='CIN')
        services.creer_demande_document(
            folder=self.folder_a, company=self.co_a, libelle='CIN',
            exigence=exigence, created_by=self.admin_a)
        resultat = services.checklist_dossier(self.folder_a)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]['statut'], 'manquant')

    def test_checklist_present_without_pending_demande(self):
        ExigenceDossier.objects.create(
            company=self.co_a, folder=self.folder_a, libelle='Diplôme')
        resultat = services.checklist_dossier(self.folder_a)
        self.assertEqual(resultat[0]['statut'], 'present')


class MatchingTests(XGed8Base):
    def test_deposit_solves_pending_demande(self):
        demande = services.creer_demande_document(
            folder=self.folder_a, company=self.co_a, libelle='CNSS',
            created_by=self.admin_a)
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Attestation CNSS')
        services.matcher_depot_demandes(doc)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DEMANDE_DOC_SOLDEE)
        self.assertEqual(demande.document_id, doc.pk)

    def test_no_pending_demande_no_op(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Divers')
        resultat = services.matcher_depot_demandes(doc)
        self.assertIsNone(resultat)


class RelanceTests(XGed8Base):
    def test_relance_increments_counter(self):
        demande = services.creer_demande_document(
            folder=self.folder_a, company=self.co_a, libelle='Visite médicale',
            utilisateur=self.admin_a, created_by=self.admin_a)
        self.assertEqual(demande.nombre_relances, 0)
        services.relancer_demande_document(demande)
        demande.refresh_from_db()
        self.assertEqual(demande.nombre_relances, 1)
        self.assertIsNotNone(demande.derniere_relance_le)

    def test_relance_no_op_on_solved(self):
        demande = services.creer_demande_document(
            folder=self.folder_a, company=self.co_a, libelle='X')
        demande.statut = DEMANDE_DOC_SOLDEE
        demande.save(update_fields=['statut'])
        services.relancer_demande_document(demande)
        demande.refresh_from_db()
        self.assertEqual(demande.nombre_relances, 0)


class ApiScopingTests(XGed8Base):
    def test_checklist_endpoint(self):
        ExigenceDossier.objects.create(
            company=self.co_a, folder=self.folder_a, libelle='CIN')
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/ged/demandes-document/checklist/?folder={self.folder_a.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_demande_scoped_to_company(self):
        admin_b = make_user(self.co_b, 'xged8-admin-b', 'admin')
        DemandeDocument.objects.create(
            company=self.co_a, folder=self.folder_a, libelle='CIN')
        api_b = auth(admin_b)
        resp = api_b.get('/api/django/ged/demandes-document/')
        self.assertEqual(resp.status_code, 200)
        ids = [d['id'] for d in resp.data.get('results', resp.data)]
        self.assertEqual(ids, [])
