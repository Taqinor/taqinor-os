"""ZGED1 — Catalogue de rôles signataires réutilisables (couleur + auth
extra + « peut changer de signataire »).

Couvre :
  * un admin crée un rôle « Client » couleur + auth SMS ;
  * l'attacher à un destinataire d'une demande fait hériter couleur/auth ;
  * CRUD scopé société, isolation tenant ;
  * l'ancien champ `role` texte est préservé (rétrocompatibilité).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder, RoleSignataire

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


class ZGed1Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged1-a', 'Zged1 A')
        self.admin_a = make_user(self.co_a, 'zged1-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')


class ServiceTests(ZGed1Base):
    def test_destinataire_herite_couleur_et_auth(self):
        role = RoleSignataire.objects.create(
            company=self.co_a, nom='Client', couleur='#ff0000',
            auth_extra='sms', created_by=self.admin_a)
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'Client A', 'email': 'a@example.com',
                 'role_signataire': role.pk},
            ], company=self.co_a, created_by=self.admin_a)
        signataire = demande.signataires.first()
        self.assertEqual(signataire.role_signataire_id, role.pk)
        self.assertEqual(signataire.role_signataire.couleur, '#ff0000')
        self.assertEqual(signataire.role_signataire.auth_extra, 'sms')
        # Le champ role texte historique reste préservé.
        self.assertEqual(signataire.role, 'signataire')

    def test_sans_role_signataire_reste_retrocompatible(self):
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'Client A', 'email': 'a@example.com'},
            ], company=self.co_a, created_by=self.admin_a)
        signataire = demande.signataires.first()
        self.assertIsNone(signataire.role_signataire_id)
        self.assertEqual(signataire.role, 'signataire')

    def test_role_signataire_autre_societe_ignore_silencieusement(self):
        co_b = make_company('zged1-b', 'Zged1 B')
        role_b = RoleSignataire.objects.create(company=co_b, nom='Client B')
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'Client A', 'email': 'a@example.com',
                 'role_signataire': role_b.pk},
            ], company=self.co_a, created_by=self.admin_a)
        signataire = demande.signataires.first()
        self.assertIsNone(signataire.role_signataire_id)


class ViewTests(ZGed1Base):
    def test_admin_cree_role_couleur_auth_sms(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/roles-signataire/', {
            'nom': 'Client', 'couleur': '#00ff00', 'auth_extra': 'sms',
            'peut_changer_signataire': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['couleur'], '#00ff00')
        self.assertEqual(resp.data['auth_extra'], 'sms')

    def test_isolation_societe(self):
        role_a = RoleSignataire.objects.create(company=self.co_a, nom='Client A')
        co_b = make_company('zged1-b2', 'Zged1 B2')
        admin_b = make_user(co_b, 'zged1-admin-b2', 'admin')
        api_b = auth(admin_b)
        resp = api_b.get(f'/api/django/ged/roles-signataire/{role_a.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_lecture_seule_pour_non_gestionnaire(self):
        RoleSignataire.objects.create(company=self.co_a, nom='Client')
        autre = make_user(self.co_a, 'zged1-autre-a', 'normal')
        api = auth(autre)
        resp = api.get('/api/django/ged/roles-signataire/')
        self.assertEqual(resp.status_code, 200)
        resp2 = api.post(
            '/api/django/ged/roles-signataire/', {'nom': 'Employé'},
            format='json')
        self.assertEqual(resp2.status_code, 403)
