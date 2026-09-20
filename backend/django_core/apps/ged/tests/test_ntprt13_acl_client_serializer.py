"""NTPRT13 (complément) — ``AclGedSerializer`` expose le principal ``client``.

``AclGed.client`` (NTPRT13, portail — voir apps/portail) était un champ de
MODÈLE valide (``clean()``/contrainte base ``ged_acl_principal_required_v2``
acceptent déjà un principal ``client`` seul) mais ABSENT de
``AclGedSerializer.Meta.fields`` : aucune API n'aurait permis à un admin
interne de réellement poser un partage client — la fonctionnalité portail
« Mes documents » restait sans écran de gestion. Ce test couvre le
complément : le champ est écrivable, un client d'une autre société est
refusé (même garde que folder/document), et ``niveau``/``herite`` restent
inchangés pour les principaux existants (utilisateur/role).

Run :
    python manage.py test apps.ged.tests.test_ntprt13_acl_client_serializer -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ged.models import AclGed, Cabinet, Document, Folder
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/ged/acls/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AclClientSerializerTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt13-acl-a', 'NTPRT13 ACL A')
        self.admin = make_user(self.company, 'ntprt13-acl-admin')
        cabinet = Cabinet.objects.create(company=self.company, nom='Admin')
        self.folder = Folder.objects.create(
            company=self.company, cabinet=cabinet, nom='Ressources')
        self.document = Document.objects.create(
            company=self.company, folder=self.folder, nom='fiche.pdf')
        self.crm_client = Client.objects.create(
            company=self.company, nom='Client', prenom='NTPRT13',
            email='ntprt13-acl@example.invalid')

    def test_admin_cree_un_partage_client_via_lapi(self):
        resp = auth(self.admin).post(BASE, {
            'document': self.document.id, 'client': self.crm_client.id,
            'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        acl = AclGed.objects.get(id=resp.data['id'])
        self.assertEqual(acl.client_id, self.crm_client.id)
        self.assertEqual(acl.company_id, self.company.id)
        self.assertEqual(resp.data['client_nom'], 'Client')

    def test_client_dune_autre_societe_refuse(self):
        autre = make_company('ntprt13-acl-b', 'NTPRT13 ACL B')
        client_autre = Client.objects.create(
            company=autre, nom='Autre', prenom='X',
            email='ntprt13-acl-b@example.invalid')
        resp = auth(self.admin).post(BASE, {
            'document': self.document.id, 'client': client_autre.id,
            'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_ni_utilisateur_ni_role_ni_client_refuse(self):
        resp = auth(self.admin).post(BASE, {
            'document': self.document.id, 'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
