"""Tests FG156 — identité & numéros légaux paie (Maroc) sur DossierEmploye.

Couvre : les nouveaux champs d'identité (CIN/CNSS/CIMR/AMO/RIB), la situation
familiale (choix validés), le nombre d'enfants pour les déductions IR — tous
facultatifs (vides/0 par défaut), acceptés + persistés à la création, et sans
casser l'isolation entre sociétés ni l'accès admin/responsable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh.models import DossierEmploye

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class IdentiteLegaleTests(TestCase):
    BASE = '/api/django/rh/employes/'

    def setUp(self):
        self.co_a = make_company('rh-id-a', 'A')
        self.co_b = make_company('rh-id-b', 'B')
        self.user_a = make_user(self.co_a, 'rh-id-a')
        self.user_b = make_user(self.co_b, 'rh-id-b')

    def test_create_accepts_and_persists_identity_fields(self):
        api = auth(self.user_a)
        payload = {
            'matricule': 'ID001', 'nom': 'Bennani', 'prenom': 'Salma',
            'cin': 'AB123456', 'cnss': '1234567', 'cimr': 'C-998877',
            'amo': 'A-554433', 'rib': '011780000012345678901234',
            'situation_familiale': 'marie', 'nombre_enfants': 3,
        }
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = DossierEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(obj.cin, 'AB123456')
        self.assertEqual(obj.cnss, '1234567')
        self.assertEqual(obj.cimr, 'C-998877')
        self.assertEqual(obj.amo, 'A-554433')
        self.assertEqual(obj.rib, '011780000012345678901234')
        self.assertEqual(
            obj.situation_familiale,
            DossierEmploye.SituationFamiliale.MARIE)
        self.assertEqual(obj.nombre_enfants, 3)
        # Exposés sur la réponse, avec le libellé lisible de la situation.
        self.assertEqual(resp.data['cnss'], '1234567')
        self.assertEqual(resp.data['situation_familiale'], 'marie')
        self.assertEqual(resp.data['situation_familiale_display'], 'Marié(e)')

    def test_identity_fields_optional_default_blank(self):
        api = auth(self.user_a)
        # Corps minimal — aucun champ d'identité légale fourni.
        resp = api.post(self.BASE, {
            'matricule': 'ID002', 'nom': 'X', 'prenom': 'Y',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = DossierEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(obj.cnss, '')
        self.assertEqual(obj.cimr, '')
        self.assertEqual(obj.amo, '')
        self.assertEqual(obj.situation_familiale, '')
        self.assertEqual(obj.nombre_enfants, 0)
        self.assertEqual(resp.data['situation_familiale_display'], '')

    def test_each_situation_familiale_choice_accepted(self):
        api = auth(self.user_a)
        for i, choix in enumerate(DossierEmploye.SituationFamiliale.values):
            resp = api.post(self.BASE, {
                'matricule': f'SF{i:03d}', 'nom': 'X', 'prenom': 'Y',
                'situation_familiale': choix,
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
            self.assertEqual(resp.data['situation_familiale'], choix)

    def test_invalid_situation_familiale_rejected(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'matricule': 'SFBAD', 'nom': 'X', 'prenom': 'Y',
            'situation_familiale': 'pacse',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_negative_nombre_enfants_rejected(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'matricule': 'NEG', 'nom': 'X', 'prenom': 'Y',
            'nombre_enfants': -1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_existing_rows_remain_valid_without_identity(self):
        # Une ligne créée directement (sans champs d'identité) reste valide :
        # les défauts vides/0 ne cassent rien — preuve de la rétro-compatibilité.
        obj = DossierEmploye.objects.create(
            company=self.co_a, matricule='LEGACY', nom='N', prenom='P')
        obj.full_clean()  # ne lève pas : tous facultatifs.
        self.assertEqual(obj.cnss, '')
        self.assertEqual(obj.nombre_enfants, 0)

    def test_identity_isolation_between_companies(self):
        DossierEmploye.objects.create(
            company=self.co_a, matricule='AONLY', nom='N', prenom='P',
            cnss='999', situation_familiale='veuf')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refused(self):
        normal = make_user(self.co_a, 'rh-id-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
