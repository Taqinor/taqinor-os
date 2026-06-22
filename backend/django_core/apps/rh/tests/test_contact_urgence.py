"""Tests FG158 — contact d'urgence & coordonnées personnelles étendues.

Couvre les nouveaux champs de DossierEmploye : personne à prévenir
(nom/lien/téléphone), groupe sanguin (médical/chantier), et coordonnées perso
(adresse/téléphone/e-mail). Tous facultatifs (vides par défaut), acceptés +
persistés à la création, exposés sur la réponse — sans casser l'isolation entre
sociétés ni l'accès Administrateur/Responsable (info médicale/urgence : aucun
élargissement d'accès).
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


class ContactUrgenceTests(TestCase):
    BASE = '/api/django/rh/employes/'

    def setUp(self):
        self.co_a = make_company('rh-urg-a', 'A')
        self.co_b = make_company('rh-urg-b', 'B')
        self.user_a = make_user(self.co_a, 'rh-urg-a')
        self.user_b = make_user(self.co_b, 'rh-urg-b')

    def test_create_accepts_and_persists_emergency_fields(self):
        api = auth(self.user_a)
        payload = {
            'matricule': 'URG001', 'nom': 'Alami', 'prenom': 'Youssef',
            'adresse_perso': '12 rue des Oudayas, Rabat',
            'telephone_perso': '+212600112233',
            'email_perso': 'youssef.perso@example.com',
            'urgence_nom': 'Fatima Alami',
            'urgence_lien': 'Épouse',
            'urgence_telephone': '+212611223344',
            'groupe_sanguin': 'O+',
        }
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = DossierEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(obj.adresse_perso, '12 rue des Oudayas, Rabat')
        self.assertEqual(obj.telephone_perso, '+212600112233')
        self.assertEqual(obj.email_perso, 'youssef.perso@example.com')
        self.assertEqual(obj.urgence_nom, 'Fatima Alami')
        self.assertEqual(obj.urgence_lien, 'Épouse')
        self.assertEqual(obj.urgence_telephone, '+212611223344')
        self.assertEqual(obj.groupe_sanguin, 'O+')
        # Exposés sur la réponse.
        self.assertEqual(resp.data['urgence_nom'], 'Fatima Alami')
        self.assertEqual(resp.data['urgence_telephone'], '+212611223344')
        self.assertEqual(resp.data['groupe_sanguin'], 'O+')
        self.assertEqual(resp.data['email_perso'], 'youssef.perso@example.com')

    def test_emergency_fields_optional_default_blank(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'matricule': 'URG002', 'nom': 'X', 'prenom': 'Y',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = DossierEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(obj.adresse_perso, '')
        self.assertEqual(obj.telephone_perso, '')
        self.assertEqual(obj.email_perso, '')
        self.assertEqual(obj.urgence_nom, '')
        self.assertEqual(obj.urgence_lien, '')
        self.assertEqual(obj.urgence_telephone, '')
        self.assertEqual(obj.groupe_sanguin, '')
        self.assertEqual(resp.data['urgence_nom'], '')
        self.assertEqual(resp.data['groupe_sanguin'], '')

    def test_invalid_email_perso_rejected(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'matricule': 'URGBAD', 'nom': 'X', 'prenom': 'Y',
            'email_perso': 'pas-un-email',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_existing_rows_remain_valid_without_emergency(self):
        obj = DossierEmploye.objects.create(
            company=self.co_a, matricule='LEGACY-URG', nom='N', prenom='P')
        obj.full_clean()  # ne lève pas : tous facultatifs.
        self.assertEqual(obj.urgence_nom, '')
        self.assertEqual(obj.groupe_sanguin, '')

    def test_emergency_isolation_between_companies(self):
        DossierEmploye.objects.create(
            company=self.co_a, matricule='AONLY-URG', nom='N', prenom='P',
            urgence_nom='Contact A', groupe_sanguin='AB-')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refused(self):
        normal = make_user(self.co_a, 'rh-urg-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
