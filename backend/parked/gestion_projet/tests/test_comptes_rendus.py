"""Tests des comptes-rendus de réunion de chantier (PROJ32).

Couvre : création avec ``company`` ET ``redacteur`` posés côté serveur (jamais
du corps) ; filtres ``?projet`` / ``?chantier`` ; scoping multi-société ; 404
cross-tenant implicite via isolation ; accès Administrateur/Responsable (403
pour ``normal``).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import CompteRenduReunion, Projet

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


class CompteRenduApiTests(TestCase):
    BASE = '/api/django/gestion-projet/comptes-rendus/'

    def setUp(self):
        self.co_a = make_company('gp-cr-a', 'A')
        self.co_b = make_company('gp-cr-b', 'B')
        self.user_a = make_user(self.co_a, 'cr-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')

    def test_creation_company_et_redacteur_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'titre': 'Réunion S12',
            'date_reunion': '2026-03-20',
            'decisions': 'Valider la pose des panneaux.',
            # redacteur posté faux — doit être ignoré (posé serveur).
            'redacteur': 99999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cr = CompteRenduReunion.objects.get(id=resp.data['id'])
        self.assertEqual(cr.company_id, self.co_a.id)
        self.assertEqual(cr.redacteur_id, self.user_a.id)

    def test_filtre_chantier(self):
        CompteRenduReunion.objects.create(
            company=self.co_a, projet=self.projet, titre='C1',
            date_reunion=date(2026, 1, 1), chantier_id=10)
        CompteRenduReunion.objects.create(
            company=self.co_a, projet=self.projet, titre='C2',
            date_reunion=date(2026, 1, 2), chantier_id=20)
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}?chantier=10')
        self.assertEqual(resp.status_code, 200)
        titres = [c['titre'] for c in rows(resp)]
        self.assertEqual(titres, ['C1'])

    def test_scoping_isolation(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        CompteRenduReunion.objects.create(
            company=self.co_b, projet=autre, titre='B',
            date_reunion=date(2026, 1, 1))
        CompteRenduReunion.objects.create(
            company=self.co_a, projet=self.projet, titre='A',
            date_reunion=date(2026, 1, 1))
        api = auth(self.user_a)
        resp = api.get(self.BASE)
        self.assertEqual(len(rows(resp)), 1)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'cr-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)
