"""NTIDE3 — note manuelle de chatter sur une idée (action ``noter``).

L'endpoint ``historique/{id}`` existait déjà (timeline chatter générique
``records.Activity``, ARC8) mais aucune action ``noter`` n'existait sur
``IdeeViewSet`` — seule ``CampagneInnovationViewSet`` (NTIDE33) en avait une.
Ce test prouve, même patron que ``test_ntide33_campagne_chatter.py`` :
l'action ajoute une note MANUELLE (utilisateur réel, société posée serveur)
au chatter générique, exige un ``body`` non vide, et reste ouverte à « tout
utilisateur connecté » comme le reste de la boîte à idées (NTIDE4/22).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import services
from apps.innovation.models import Idee
from apps.records.models import Activity
from apps.records.services import chatter_qs

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NoterIdeeServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('innov-ntide3-svc', 'NTIDE3 Svc')
        self.auteur = make_user(self.co, 'ntide3-svc-auteur')
        self.idee = Idee.objects.create(
            company=self.co, auteur=self.auteur, titre='Export PDF')

    def test_noter_idee_ecrit_une_note_manuelle(self):
        services.noter_idee(self.idee, self.auteur, 'À prioriser.')
        entries = chatter_qs(self.idee, company=self.co)
        self.assertTrue(
            entries.filter(kind=Activity.Kind.NOTE, body='À prioriser.',
                           created_by=self.auteur).exists())


class NoterIdeeApiTests(TestCase):
    BASE = '/api/django/innovation/idees'

    def setUp(self):
        self.co = make_company('innov-ntide3-api', 'NTIDE3 Api')
        # role_legacy='normal' — le plus limité : « logged-in users only »
        # (NTIDE4) doit couvrir aussi la note manuelle.
        self.user = make_user(self.co, 'ntide3-api-user')
        self.idee = Idee.objects.create(
            company=self.co, auteur=self.user, titre='Export PDF')

    def test_noter_endpoint_ajoute_une_note_manuelle(self):
        resp = auth(self.user).post(
            f'{self.BASE}/{self.idee.id}/noter/',
            {'body': 'Doublon possible avec #42.'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        entries = chatter_qs(self.idee, company=self.co)
        self.assertTrue(
            entries.filter(kind=Activity.Kind.NOTE,
                           body='Doublon possible avec #42.',
                           created_by=self.user).exists())

    def test_noter_requires_body(self):
        resp = auth(self.user).post(
            f'{self.BASE}/{self.idee.id}/noter/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_noter_apparait_dans_historique(self):
        auth(self.user).post(
            f'{self.BASE}/{self.idee.id}/noter/',
            {'body': 'Vue en réunion produit.'}, format='json')
        resp = auth(self.user).get(f'{self.BASE}/{self.idee.id}/historique/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            any(row.get('body') == 'Vue en réunion produit.'
                for row in resp.data))

    def test_isolation_societe(self):
        autre_co = make_company('innov-ntide3-autre', 'Autre')
        autre_user = make_user(autre_co, 'ntide3-autre-user')
        resp = auth(autre_user).post(
            f'{self.BASE}/{self.idee.id}/noter/',
            {'body': 'Tentative hors société.'}, format='json')
        self.assertEqual(resp.status_code, 404)
