"""Tests FG160/FG161 — référentiel Poste & Département, cycle de vie/offboarding.

Couvre : la création d'un poste (société posée côté serveur, isolation), le
rattachement d'un employé à un poste de SA société (un poste d'une autre société
est refusé), les nouveaux statuts de cycle de vie (embauché/sorti + motif), et la
checklist d'offboarding (éléments à récupérer, filtre ?recupere=).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh.models import DossierEmploye, ElementSortie, Poste

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
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PosteTests(TestCase):
    BASE = '/api/django/rh/postes/'

    def setUp(self):
        self.co_a = make_company('ref-a', 'A')
        self.co_b = make_company('ref-b', 'B')
        self.user_a = make_user(self.co_a, 'ref-a')
        self.user_b = make_user(self.co_b, 'ref-b')

    def test_create_forces_company(self):
        resp = auth(self.user_a).post(
            self.BASE, {'intitule': 'Technicien pose'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            Poste.objects.get(id=resp.data['id']).company, self.co_a)

    def test_isolation(self):
        Poste.objects.create(company=self.co_a, intitule='Chef chantier')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(len(rows(resp)), 0)

    def test_employe_poste_ref_meme_societe(self):
        poste_b = Poste.objects.create(company=self.co_b, intitule='Commercial')
        # un employé de A ne peut pas pointer un poste de B
        resp = auth(self.user_a).post(
            '/api/django/rh/employes/',
            {'matricule': 'E1', 'nom': 'X', 'prenom': 'Y',
             'poste_ref': poste_b.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('poste_ref', resp.data)

    def test_employe_poste_ref_ok(self):
        poste_a = Poste.objects.create(company=self.co_a, intitule='Soudeur')
        resp = auth(self.user_a).post(
            '/api/django/rh/employes/',
            {'matricule': 'E2', 'nom': 'X', 'prenom': 'Y',
             'poste_ref': poste_a.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        emp = DossierEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(emp.poste_ref_id, poste_a.id)


class CycleVieTests(TestCase):
    def setUp(self):
        self.co = make_company('cv-a', 'A')
        self.user = make_user(self.co, 'cv-a')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='Kasri', prenom='Reda')

    def test_statut_embauche_choice(self):
        resp = auth(self.user).patch(
            f'/api/django/rh/employes/{self.emp.id}/',
            {'statut': DossierEmploye.Statut.EMBAUCHE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.statut, 'embauche')

    def test_offboarding_motif(self):
        resp = auth(self.user).patch(
            f'/api/django/rh/employes/{self.emp.id}/',
            {'statut': DossierEmploye.Statut.SORTI,
             'date_sortie': '2026-07-01',
             'motif_sortie': DossierEmploye.MotifSortie.DEMISSION},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.statut, 'sorti')
        self.assertEqual(self.emp.motif_sortie, 'demission')
        self.assertEqual(str(self.emp.date_sortie), '2026-07-01')


class ElementSortieTests(TestCase):
    BASE = '/api/django/rh/elements-sortie/'

    def setUp(self):
        self.co = make_company('es-a', 'A')
        self.user = make_user(self.co, 'es-a')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='X', prenom='Y')

    def test_create_and_filter_recupere(self):
        api = auth(self.user)
        r1 = api.post(self.BASE, {
            'employe': self.emp.id, 'libelle': 'Badge accès',
            'type_element': 'badge'}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        ElementSortie.objects.create(
            company=self.co, employe=self.emp, libelle='Casque', recupere=True)
        # non-récupérés seulement
        resp = api.get(self.BASE + '?recupere=0')
        libelles = {r['libelle'] for r in rows(resp)}
        self.assertIn('Badge accès', libelles)
        self.assertNotIn('Casque', libelles)
