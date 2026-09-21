"""Tests XPRJ15 — point d'avancement périodique (statut RAG).

Couvre : création + historique par projet, le portefeuille expose la
DERNIÈRE santé (jamais une moyenne ni la première), isolation tenant, et
``auteur``/``company`` posés côté serveur.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import PointAvancement, Projet

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


class PointAvancementTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj15', 'S')
        self.user = make_user(self.co, 'resp-xprj15')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X15', nom='Projet X15')

    def test_creation_auteur_et_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/gestion-projet/points-avancement/', {
            'projet': self.projet.id,
            'sante': PointAvancement.Sante.VERT,
            'avancement_pct': 30,
            'realisations': 'Fondations coulées',
            'date_point': '2026-07-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        point = PointAvancement.objects.get(id=resp.data['id'])
        self.assertEqual(point.company_id, self.co.id)
        self.assertEqual(point.auteur_id, self.user.id)

    def test_historique_par_projet(self):
        PointAvancement.objects.create(
            company=self.co, projet=self.projet, auteur=self.user,
            sante=PointAvancement.Sante.VERT, avancement_pct=10,
            date_point=date(2026, 6, 1))
        PointAvancement.objects.create(
            company=self.co, projet=self.projet, auteur=self.user,
            sante=PointAvancement.Sante.ORANGE, avancement_pct=30,
            date_point=date(2026, 7, 1))
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/points-avancement/'
            f'?projet={self.projet.id}')
        data = rows(resp)
        self.assertEqual(len(data), 2)
        # Le plus récent en premier (ordering par défaut du modèle).
        self.assertEqual(data[0]['sante'], 'orange')

    def test_isolation_tenant(self):
        autre_co = make_company('gp-xprj15-autre', 'Autre')
        autre_user = make_user(autre_co, 'user-autre-x15')
        PointAvancement.objects.create(
            company=self.co, projet=self.projet, auteur=self.user,
            sante=PointAvancement.Sante.ROUGE, avancement_pct=5,
            date_point=date(2026, 7, 1))
        api = auth(autre_user)
        resp = api.get('/api/django/gestion-projet/points-avancement/')
        self.assertEqual(rows(resp), [])

    def test_portefeuille_expose_derniere_sante(self):
        PointAvancement.objects.create(
            company=self.co, projet=self.projet, auteur=self.user,
            sante=PointAvancement.Sante.VERT, avancement_pct=10,
            date_point=date(2026, 6, 1))
        PointAvancement.objects.create(
            company=self.co, projet=self.projet, auteur=self.user,
            sante=PointAvancement.Sante.ROUGE, avancement_pct=40,
            date_point=date(2026, 7, 1))
        data = selectors.tableau_portefeuille(self.co)
        ligne = next(
            p for p in data['projets'] if p['projet_id'] == self.projet.id)
        self.assertEqual(ligne['derniere_sante'], 'rouge')

    def test_portefeuille_sante_none_sans_point(self):
        data = selectors.tableau_portefeuille(self.co)
        ligne = next(
            p for p in data['projets'] if p['projet_id'] == self.projet.id)
        self.assertIsNone(ligne['derniere_sante'])

    def test_portefeuille_endpoint_expose_derniere_sante(self):
        PointAvancement.objects.create(
            company=self.co, projet=self.projet, auteur=self.user,
            sante=PointAvancement.Sante.ORANGE, avancement_pct=20,
            date_point=date(2026, 7, 1))
        api = auth(self.user)
        resp = api.get('/api/django/gestion-projet/projets/portefeuille/')
        self.assertEqual(resp.status_code, 200)
        ligne = next(
            p for p in resp.data['projets']
            if p['projet_id'] == self.projet.id)
        self.assertEqual(ligne['derniere_sante'], 'orange')
