"""ASEC38 — toutes les actions GED d'écriture passent par l'ACL du document.

Constat C-ASEC-014 : purger et restaurer depuis la corbeille, lier un
document, fusionner vers une cible n'interrogeaient pas l'ACL GED19 — un
utilisateur limité à la LECTURE les exécutait. Attendu : 403 sans effet ;
un rédacteur ACL garde l'accès.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ged.models import AclGed, Cabinet, Document, DocumentLien, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AclEcritureGedTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ASEC38', slug='asec38')
        self.lecteur = User.objects.create_user(
            username='asec38_lecteur', password='x', company=self.co,
            role_legacy='responsable')
        self.redacteur = User.objects.create_user(
            username='asec38_redacteur', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='Racine')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='contrat.pdf')
        self.autre = Document.objects.create(
            company=self.co, folder=self.folder, nom='annexe.pdf')
        AclGed.objects.create(company=self.co, document=self.doc,
                              utilisateur=self.lecteur, niveau='lecture')
        AclGed.objects.create(company=self.co, document=self.doc,
                              utilisateur=self.redacteur, niveau='ecriture')
        self.client_crm = Client.objects.create(company=self.co, nom='Cli')

    def _en_corbeille(self):
        Document.objects.filter(pk=self.doc.pk).update(
            supprime_le=timezone.now())

    def _toujours_en_corbeille(self):
        doc = Document.objects.filter(pk=self.doc.pk).first()
        self.assertIsNotNone(doc)
        self.assertIsNotNone(doc.supprime_le)

    def test_purger_403(self):
        self._en_corbeille()
        r = _api(self.lecteur).post(f'{BASE}documents/{self.doc.pk}/purger/')
        self.assertEqual(r.status_code, 403, r.content)
        self._toujours_en_corbeille()

    def test_restaurer_corbeille_403(self):
        self._en_corbeille()
        r = _api(self.lecteur).post(
            f'{BASE}documents/{self.doc.pk}/restaurer-corbeille/')
        self.assertEqual(r.status_code, 403, r.content)
        self._toujours_en_corbeille()

    def test_lien_403(self):
        r = _api(self.lecteur).post(f'{BASE}liens/', {
            'document': self.doc.pk, 'model': 'crm.client',
            'id': self.client_crm.pk}, format='json')
        self.assertEqual(r.status_code, 403, r.content)
        self.assertFalse(DocumentLien.objects.filter(
            document=self.doc).exists())

    def test_fusionner_403(self):
        r = _api(self.lecteur).post(f'{BASE}documents/fusionner/', {
            'documents': [self.autre.pk, self.doc.pk],
            'cible': self.doc.pk}, format='json')
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(self.doc.versions.count(), 0)

    def test_operations_lot_sans_effet(self):
        r = _api(self.lecteur).post(f'{BASE}documents/operations-lot/', {
            'documents': [self.doc.pk], 'operation': 'corbeille'},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['resultats'], [])
        self.assertEqual(len(r.data['erreurs']), 1)
        self.doc.refresh_from_db()
        self.assertIsNone(self.doc.supprime_le)

    def test_ecrivain_acl_ok(self):
        api = _api(self.redacteur)
        r = api.post(f'{BASE}liens/', {
            'document': self.doc.pk, 'model': 'crm.client',
            'id': self.client_crm.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self._en_corbeille()
        r2 = api.post(f'{BASE}documents/{self.doc.pk}/restaurer-corbeille/')
        self.assertEqual(r2.status_code, 200, r2.content)
        self._en_corbeille()
        r3 = api.post(f'{BASE}documents/{self.doc.pk}/purger/')
        self.assertEqual(r3.status_code, 204, r3.content)
        self.assertFalse(Document.objects.filter(pk=self.doc.pk).exists())
