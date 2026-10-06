"""ADOC12 — la checklist ne dit « présente » que pour une pièce réellement
fournie, et un dépôt solde la demande de SA propre exigence.

Rejoue la sonde #8 de l'audit documents (2026-10-05) : une exigence sans
demande ni document → statut « present » (dossier vide).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    Cabinet, DemandeDocument, Document, ExigenceDossier, Folder,
)
from authentication.models import Company

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ChecklistTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc12', defaults={'nom': 'ADOC12'})[0]
        self.admin = User.objects.create_user(
            username='adoc12-admin', password='x', company=self.co,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='Dossier RH')
        self.cin = ExigenceDossier.objects.create(
            company=self.co, folder=self.folder, libelle='CIN')
        self.cnss = ExigenceDossier.objects.create(
            company=self.co, folder=self.folder, libelle='Attestation CNSS')

    def _statuts(self):
        resp = auth(self.admin).get(
            '/api/django/ged/demandes-document/checklist/'
            f'?folder={self.folder.pk}')
        self.assertEqual(resp.status_code, 200, resp.content)
        return {item['exigence']['libelle']: item['statut']
                for item in resp.data}

    def test_exigence_sans_piece_manquante(self):
        self.assertEqual(self._statuts(), {
            'CIN': 'manquant', 'Attestation CNSS': 'manquant'})

    def test_depot_solde_sa_propre_exigence(self):
        demande_cnss = services.creer_demande_document(
            folder=self.folder, company=self.co, libelle='Attestation CNSS',
            exigence=self.cnss, created_by=self.admin)
        demande_cin = services.creer_demande_document(
            folder=self.folder, company=self.co, libelle='CIN',
            exigence=self.cin, created_by=self.admin)
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='CIN recto-verso')
        services.matcher_depot_demandes(doc)
        demande_cin.refresh_from_db()
        demande_cnss.refresh_from_db()
        self.assertEqual(demande_cin.statut, 'soldee')
        self.assertEqual(demande_cin.document_id, doc.pk)
        self.assertEqual(demande_cnss.statut, 'en_attente')
        self.assertIsNone(demande_cnss.document_id)
        self.assertEqual(self._statuts(), {
            'CIN': 'present', 'Attestation CNSS': 'manquant'})
        self.assertEqual(
            DemandeDocument.objects.filter(statut='soldee').count(), 1)
