"""ADOC14 — l'approbation appartient à l'approbateur désigné et à une version.

Rejoue la sonde #47 de l'audit documents (2026-10-05) : le demandeur (non
approbateur) appelait /approuver/ → [200, 200, 400], la demande et le
document passaient « approuvé » avec un approbateur hors chaîne.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    Cabinet, DemandeApprobation, Document, DocumentActivity, Folder,
    RegleApprobationGed,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ApprobationTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc14', defaults={'nom': 'ADOC14'})[0]
        self.admin = User.objects.create_user(
            username='adoc14-admin', password='x', company=self.co,
            role_legacy='admin')
        self.appr1 = User.objects.create_user(
            username='adoc14-appr1', password='x', company=self.co,
            role_legacy='responsable')
        self.appr2 = User.objects.create_user(
            username='adoc14-appr2', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')
        RegleApprobationGed.objects.create(
            company=self.co, libelle='2 niveaux',
            condition_group={'field': 'nom', 'operator': 'eq',
                             'value': 'Contrat'},
            approbateurs=[self.appr1.pk, self.appr2.pk])
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='Contrat')
        self.v1 = services.add_version(
            self.doc, file_key='attachments/c1.pdf', company=self.co,
            uploaded_by=self.admin)
        self.demande = services.request_review_avec_routage(
            self.doc, user=self.admin)

    def _approuver(self, user):
        return auth(user).post(
            f'{BASE}demandes-approbation/{self.demande.pk}/approuver/')

    def test_demandeur_ne_peut_pas_approuver(self):
        for _ in range(2):
            resp = self._approuver(self.admin)
            self.assertEqual(resp.status_code, 403, resp.content)
            self.assertIn('demandeur', resp.data['detail'])
        self.demande.refresh_from_db()
        self.doc.refresh_from_db()
        self.assertEqual(self.demande.statut, 'en_attente')
        self.assertEqual(self.demande.approbateur_id, self.appr1.pk)
        self.assertEqual(self.doc.statut, 'revue')
        # La demande retient la version relue (posée côté serveur).
        self.assertEqual(self.demande.version_id, self.v1.pk)

    def test_approbateur_hors_etape_403(self):
        resp = self._approuver(self.appr2)
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn('étape', resp.data['detail'])
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.approbateur_id, self.appr1.pk)
        # Chemin nominal : appr1 puis appr2.
        self.assertEqual(self._approuver(self.appr1).status_code, 200)
        self.assertEqual(self._approuver(self.appr2).status_code, 200)
        self.demande.refresh_from_db()
        self.doc.refresh_from_db()
        self.assertEqual(self.demande.statut, 'approuve')
        self.assertEqual(self.doc.statut, 'approuve')

    def test_cycle_vie_vers_approuve_400(self):
        resp = auth(self.appr1).post(
            f'{BASE}documents/{self.doc.pk}/cycle-vie/',
            {'statut': 'approuve'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('demande', resp.data['detail'])
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.statut, 'revue')

    def test_nouvelle_version_repasse_en_revue(self):
        e = Document.objects.create(
            company=self.co, folder=self.folder, nom='E')
        services.add_version(e, file_key='attachments/e1.pdf',
                             company=self.co, uploaded_by=self.admin)
        demande = services.request_review(e, user=self.admin)
        services.approve_demande(demande, user=self.appr1)
        e.refresh_from_db()
        self.assertEqual(e.statut, 'approuve')
        services.add_version(e, file_key='attachments/e2.pdf',
                             company=self.co, uploaded_by=self.appr1)
        e.refresh_from_db()
        self.assertEqual(e.statut, 'revue')
        self.assertTrue(DocumentActivity.objects.filter(
            document=e, message__icontains='approbation à refaire').exists())
        self.assertEqual(
            DemandeApprobation.objects.get(pk=demande.pk).statut, 'approuve')
