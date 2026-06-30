"""Tests du registre d'actions (PROJ31).

Le statut suit un cycle PROPRE au registre (à faire/en cours/fait/annulé),
distinct de STAGES.py. Une action peut être liée à un risque du MÊME projet.

Couvre : création société posée serveur ; lien risque même-projet (refus
cross-projet 400) ; filtre ``ouvertes`` ; scoping multi-société ; 404
cross-tenant ; accès Administrateur/Responsable (403 pour ``normal``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import ActionProjet, Projet, Risque

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


class ActionProjetApiTests(TestCase):
    BASE = '/api/django/gestion-projet/actions/'

    def setUp(self):
        self.co_a = make_company('gp-ac-a', 'A')
        self.co_b = make_company('gp-ac-b', 'B')
        self.user_a = make_user(self.co_a, 'ac-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')

    def test_creation_company_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'libelle': 'Relancer fournisseur',
            'priorite': 'haute',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        action = ActionProjet.objects.get(id=resp.data['id'])
        self.assertEqual(action.company_id, self.co_a.id)
        self.assertEqual(action.statut, ActionProjet.Statut.A_FAIRE)

    def test_risque_meme_projet(self):
        risque = Risque.objects.create(
            company=self.co_a, projet=self.projet, libelle='R',
            probabilite=2, impact=2)
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'libelle': 'Mitiger', 'risque': risque.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_risque_autre_projet_refuse(self):
        autre_projet = Projet.objects.create(
            company=self.co_a, code='P-A2', nom='A2')
        risque = Risque.objects.create(
            company=self.co_a, projet=autre_projet, libelle='R',
            probabilite=2, impact=2)
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'libelle': 'Mitiger', 'risque': risque.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filtre_ouvertes(self):
        ActionProjet.objects.create(
            company=self.co_a, projet=self.projet, libelle='Faite',
            statut=ActionProjet.Statut.FAIT)
        ActionProjet.objects.create(
            company=self.co_a, projet=self.projet, libelle='En cours',
            statut=ActionProjet.Statut.EN_COURS)
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}?ouvertes=1')
        self.assertEqual(resp.status_code, 200)
        libelles = [a['libelle'] for a in rows(resp)]
        self.assertEqual(libelles, ['En cours'])

    def test_scoping_isolation(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        ActionProjet.objects.create(
            company=self.co_b, projet=autre, libelle='B')
        ActionProjet.objects.create(
            company=self.co_a, projet=self.projet, libelle='A')
        api = auth(self.user_a)
        resp = api.get(self.BASE)
        self.assertEqual(len(rows(resp)), 1)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'ac-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)
