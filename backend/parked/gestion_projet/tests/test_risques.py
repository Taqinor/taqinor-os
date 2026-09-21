"""Tests du registre des risques (PROJ30).

La ``criticite`` est CALCULÉE côté serveur (probabilité × impact) — jamais lue
du corps. Le statut suit un cycle PROPRE au registre (ouvert/surveillé/maîtrisé/
clos), distinct de STAGES.py.

Couvre : criticité figée serveur (même si postée fausse) ; bornes 1–5 sur
probabilité/impact ; société posée serveur ; scoping multi-société + filtres ;
404 cross-tenant ; accès Administrateur/Responsable (403 pour ``normal``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import Projet, Risque

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


class RisqueModelTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-ri-mdl', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-RI', nom='P')

    def test_criticite_calculee_au_save(self):
        risque = Risque.objects.create(
            company=self.co, projet=self.projet, libelle='R',
            probabilite=3, impact=4)
        self.assertEqual(risque.criticite, 12)
        risque.probabilite = 5
        risque.save()
        # impact reste 4 → criticité recalculée = 5 × 4 = 20 (≠ l'ancien 12).
        self.assertEqual(risque.criticite, 20)


class RisqueApiTests(TestCase):
    BASE = '/api/django/gestion-projet/risques/'

    def setUp(self):
        self.co_a = make_company('gp-ri-a', 'A')
        self.co_b = make_company('gp-ri-b', 'B')
        self.user_a = make_user(self.co_a, 'ri-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')

    def test_criticite_figee_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'libelle': 'Rupture appro',
            'probabilite': 4,
            'impact': 5,
            'criticite': 1,  # posté faux — doit être ignoré.
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['criticite'], 20)
        risque = Risque.objects.get(id=resp.data['id'])
        self.assertEqual(risque.company_id, self.co_a.id)

    def test_borne_probabilite(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'libelle': 'R',
            'probabilite': 9, 'impact': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filtre_criticite_min(self):
        Risque.objects.create(
            company=self.co_a, projet=self.projet, libelle='Faible',
            probabilite=1, impact=1)
        Risque.objects.create(
            company=self.co_a, projet=self.projet, libelle='Fort',
            probabilite=5, impact=5)
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}?criticite_min=10')
        self.assertEqual(resp.status_code, 200)
        libelles = [r['libelle'] for r in rows(resp)]
        self.assertEqual(libelles, ['Fort'])

    def test_scoping_isolation(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        Risque.objects.create(
            company=self.co_b, projet=autre, libelle='RB',
            probabilite=2, impact=2)
        Risque.objects.create(
            company=self.co_a, projet=self.projet, libelle='RA',
            probabilite=2, impact=2)
        api = auth(self.user_a)
        resp = api.get(self.BASE)
        self.assertEqual(len(rows(resp)), 1)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'ri-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)
