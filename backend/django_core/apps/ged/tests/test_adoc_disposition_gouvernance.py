"""ADOC7 — la destruction par disposition relève de ged_gouvernance.

Rejoue la sonde #51 de l'audit documents (2026-10-05) : un Technicien sans
ged_gouvernance recevait 403 sur `purger` mais créait (201), approuvait (200)
et exécutait (200) une disposition « détruire » d'un document vivant non échu.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    Cabinet, DemandeDisposition, Document, Folder, PolitiqueRetention,
)
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    DIRECTEUR_PERMISSIONS, TECHNICIEN_PERMISSIONS,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/demandes-disposition/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DispositionGouvernanceTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc7', defaults={'nom': 'ADOC7'})[0]

        def user(suffix, perms):
            role = Role.objects.create(
                company=self.co, nom=f'adoc7-{suffix}', permissions=list(perms))
            return User.objects.create_user(
                username=f'adoc7-{suffix}', password='x', company=self.co,
                role=role)

        self.tech = user('tech', TECHNICIEN_PERMISSIONS)
        self.g1 = user('g1', DIRECTEUR_PERMISSIONS)
        self.g2 = user('g2', DIRECTEUR_PERMISSIONS)
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        PolitiqueRetention.objects.create(
            company=self.co, nom='Globale', duree_conservation_jours=30)
        self.vieux = Document.objects.create(
            company=self.co, folder=folder, nom='vieux.pdf')
        Document.objects.filter(pk=self.vieux.pk).update(
            created_at=timezone.now() - timedelta(days=400))
        self.neuf = Document.objects.create(
            company=self.co, folder=folder, nom='neuf.pdf')

    def test_permissions_du_jeu_de_test(self):
        self.assertFalse(self.tech.has_erp_permission('ged_gouvernance'))
        self.assertTrue(self.g1.has_erp_permission('ged_gouvernance'))

    def test_technicien_403(self):
        api = auth(self.tech)
        resp = api.post(BASE, {'libelle': 'x', 'action': 'detruire',
                               'documents': [self.vieux.pk]}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertFalse(DemandeDisposition.objects.exists())
        demande = services.creer_demande_disposition(
            self.co, libelle='x', document_ids=[self.vieux.pk],
            user=self.g1)
        resp = api.post(f'{BASE}{demande.pk}/approuver/')
        self.assertEqual(resp.status_code, 403, resp.content)
        services.approuver_demande_disposition(demande, user=self.g2)
        resp = api.post(f'{BASE}{demande.pk}/executer/')
        self.assertEqual(resp.status_code, 403, resp.content)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'approuvee')
        self.assertTrue(Document.objects.filter(pk=self.vieux.pk).exists())

    def test_non_echu_400(self):
        resp = auth(self.g1).post(BASE, {
            'libelle': 'x', 'action': 'detruire',
            'documents': [self.vieux.pk, self.neuf.pk]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('non échu : neuf.pdf', resp.data['detail'])
        self.assertFalse(DemandeDisposition.objects.exists())
        self.assertTrue(Document.objects.filter(pk=self.neuf.pk).exists())

    def test_auto_approbation_403(self):
        resp = auth(self.g1).post(BASE, {
            'libelle': 'x', 'action': 'detruire',
            'documents': [self.vieux.pk]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        resp = auth(self.g1).post(f'{BASE}{resp.data["id"]}/approuver/')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn('demandeur', resp.data['detail'])
        self.assertEqual(DemandeDisposition.objects.get().statut, 'en_attente')

    def test_chemin_nominal(self):
        resp = auth(self.g1).post(BASE, {
            'libelle': 'x', 'action': 'detruire',
            'documents': [self.vieux.pk]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pk = resp.data['id']
        resp = auth(self.g2).post(f'{BASE}{pk}/approuver/')
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = auth(self.g2).post(f'{BASE}{pk}/executer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(Document.objects.filter(pk=self.vieux.pk).exists())
        self.assertTrue(Document.objects.filter(pk=self.neuf.pk).exists())
