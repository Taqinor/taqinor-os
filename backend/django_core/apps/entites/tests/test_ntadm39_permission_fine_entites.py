"""NTADM39 — permission fine ``adminops_entites_gerer`` sur les écritures
`Entite` (câblée au fold : la clé est déclarée dans ``apps.adminops`` et le
viewset vit dans ``apps.entites``).

Un rôle CUSTOM (``est_systeme=False``) passant le palier coarse
(``entites_administrer``) mais SANS la clé fine reçoit 403 sur toute écriture ;
avec la clé il écrit ; un rôle SYSTÈME garde son comportement (rétrocompat).
``noter`` (note de chatter ``records``) reste hors du champ de la clé."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/entites/entites/'


def _user_avec_role(company, username, permissions, est_systeme):
    role = Role.objects.create(
        company=company, nom=f'role-{username}',
        permissions=permissions, est_systeme=est_systeme)
    return User.objects.create_user(
        username=username, password='pw', company=company, role=role)


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


class EntitesGererPermissionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTADM39-Entites-Co')

    def test_role_custom_sans_la_cle_refuse_en_ecriture(self):
        user = _user_avec_role(
            self.company, 'ent-sans-cle', ['entites_administrer'],
            est_systeme=False)
        resp = _client(user).post(URL, {'nom': 'Filiale X', 'code': 'FX'})
        self.assertEqual(resp.status_code, 403)

    def test_role_custom_avec_la_cle_ecrit(self):
        user = _user_avec_role(
            self.company, 'ent-avec-cle',
            ['entites_administrer', 'adminops_entites_gerer'],
            est_systeme=False)
        resp = _client(user).post(URL, {'nom': 'Filiale Y', 'code': 'FY'})
        self.assertEqual(resp.status_code, 201)

    def test_role_systeme_sans_la_cle_inchange(self):
        user = _user_avec_role(
            self.company, 'ent-systeme', ['entites_administrer'],
            est_systeme=True)
        resp = _client(user).post(URL, {'nom': 'Filiale Z', 'code': 'FZ'})
        self.assertEqual(resp.status_code, 201)

    def test_lecture_jamais_gardee_par_la_cle(self):
        user = _user_avec_role(
            self.company, 'ent-lecture', ['entites_administrer'],
            est_systeme=False)
        resp = _client(user).get(URL)
        self.assertEqual(resp.status_code, 200)

    def test_noter_hors_du_champ_de_la_cle(self):
        admin = _user_avec_role(
            self.company, 'ent-admin-note',
            ['entites_administrer', 'adminops_entites_gerer'],
            est_systeme=False)
        creation = _client(admin).post(URL, {'nom': 'Filiale N', 'code': 'FN'})
        self.assertEqual(creation.status_code, 201)
        sans_cle = _user_avec_role(
            self.company, 'ent-note-sans-cle', ['entites_administrer'],
            est_systeme=False)
        resp = _client(sans_cle).post(
            f"{URL}{creation.data['id']}/noter/", {'body': 'RAS'})
        self.assertNotEqual(resp.status_code, 403)
