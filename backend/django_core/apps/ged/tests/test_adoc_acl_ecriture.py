"""ADOC5 — les niveaux ACL « écriture » et « gestion » gouvernent les écritures.

Rejoue les sondes #39/#45 de l'audit documents (2026-10-05) : un responsable
avec une ACL « lecture » renommait (200) et supprimait (204) le document ; un
responsable exclu s'auto-octroyait « gestion » (201) ; un dossier sous ACL
restait listé pour un autre utilisateur.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from authentication.models import Company
from apps.ged.models import AclGed, Cabinet, Document, Folder

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def lignes(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class AclEcritureTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc5', defaults={'nom': 'ADOC5'})[0]
        self.admin = User.objects.create_user(
            username='adoc5-admin', password='x', company=self.co,
            role_legacy='admin')
        self.u = User.objects.create_user(
            username='adoc5-u', password='x', company=self.co,
            role_legacy='responsable')
        self.r = User.objects.create_user(
            username='adoc5-r', password='x', company=self.co,
            role_legacy='responsable')
        self.cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.racine = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Racine')
        self.autre = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Autre')
        self.doc = Document.objects.create(
            company=self.co, folder=self.racine, nom='contrat.pdf')
        self.acl_u = AclGed.objects.create(
            company=self.co, document=self.doc, utilisateur=self.u,
            niveau='lecture')
        self.role_rh = Role.objects.create(company=self.co, nom='RH ADOC5')
        self.dossier_rh = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='RH-SECRET')
        AclGed.objects.create(
            company=self.co, folder=self.dossier_rh, role=self.role_rh,
            niveau='lecture')
        self.doc_rh = Document.objects.create(
            company=self.co, folder=self.dossier_rh, nom='salaires.pdf')

    def test_lecteur_ne_renomme_pas(self):
        api = auth(self.u)
        self.assertEqual(api.get(f'{BASE}documents/{self.doc.pk}/').status_code,
                         200)
        resp = api.patch(f'{BASE}documents/{self.doc.pk}/', {'nom': 'x'},
                         format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn("écriture", str(resp.data['detail']))
        resp = api.post(f'{BASE}documents/{self.doc.pk}/deplacer/',
                        {'folder': self.autre.pk}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        resp = api.post(f'{BASE}versions/', {
            'document': self.doc.pk, 'file_key': 'attachments/v2.pdf',
            'filename': 'v2.pdf'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        resp = api.post(f'{BASE}documents/operations-lot/', {
            'documents': [self.doc.pk], 'operation': 'corbeille'},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['resultats'], [])
        self.assertEqual(len(resp.data['erreurs']), 1)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.nom, 'contrat.pdf')
        self.assertEqual(self.doc.folder_id, self.racine.pk)
        self.assertIsNone(self.doc.supprime_le)
        self.assertEqual(self.doc.versions.count(), 0)

    def test_lecteur_ne_supprime_pas(self):
        resp = auth(self.u).delete(f'{BASE}documents/{self.doc.pk}/')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.doc.refresh_from_db()
        self.assertIsNone(self.doc.supprime_le)

    def test_auto_octroi_refuse(self):
        api = auth(self.r)
        self.assertEqual(
            api.get(f'{BASE}documents/{self.doc_rh.pk}/').status_code, 404)
        avant = AclGed.objects.count()
        resp = api.post(f'{BASE}acls/', {
            'document': self.doc_rh.pk, 'utilisateur': self.r.pk,
            'niveau': 'gestion'}, format='json')
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertEqual(AclGed.objects.count(), avant)
        self.assertEqual(
            api.get(f'{BASE}documents/{self.doc_rh.pk}/').status_code, 404)
        # Un lecteur ne s'élève pas non plus sur une cible qu'il voit.
        resp = auth(self.u).post(f'{BASE}acls/', {
            'document': self.doc.pk, 'utilisateur': self.u.pk,
            'niveau': 'gestion'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        resp = auth(self.u).patch(f'{BASE}acls/{self.acl_u.pk}/',
                                  {'niveau': 'gestion'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.acl_u.refresh_from_db()
        self.assertEqual(self.acl_u.niveau, 'lecture')

    def test_arbre_filtre(self):
        resp = auth(self.r).get(f'{BASE}dossiers/?cabinet={self.cab.pk}')
        noms = [d['nom'] for d in lignes(resp)]
        self.assertNotIn('RH-SECRET', noms)
        self.assertIn('Racine', noms)
        resp = auth(self.admin).get(f'{BASE}dossiers/?cabinet={self.cab.pk}')
        self.assertIn('RH-SECRET', [d['nom'] for d in lignes(resp)])

    def test_ecriture_autorisee(self):
        self.acl_u.niveau = 'ecriture'
        self.acl_u.save()
        resp = auth(self.u).patch(f'{BASE}documents/{self.doc.pk}/',
                                  {'nom': 'renomme.pdf'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.nom, 'renomme.pdf')
        # « écriture » ne suffit pas pour gérer les ACL ; « gestion » oui.
        resp = auth(self.u).post(f'{BASE}acls/', {
            'document': self.doc.pk, 'utilisateur': self.r.pk,
            'niveau': 'lecture'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.acl_u.niveau = 'gestion'
        self.acl_u.save()
        resp = auth(self.u).post(f'{BASE}acls/', {
            'document': self.doc.pk, 'utilisateur': self.r.pk,
            'niveau': 'lecture'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
