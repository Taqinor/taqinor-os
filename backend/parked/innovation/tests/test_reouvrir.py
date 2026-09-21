"""Tests de la ré-ouverture par l'auteur (NTIDE17 — « auteur peut modifier »).

Couvre : l'auteur ré-ouvre depuis fermée/examinée (retour à ouvert), un tiers
(même Directeur/Responsable) ne peut pas ré-ouvrir à la place de l'auteur,
verrouillage après retenue/réalisée, chatter journalisé, isolation
multi-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ReouvrirIdeeTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-reo-a', 'A')
        self.co_b = make_company('innov-reo-b', 'B')
        self.author = make_user(self.co_a, 'innov-reo-author')
        self.other = make_user(self.co_a, 'innov-reo-other')
        self.resp_a = make_user(self.co_a, 'innov-reo-resp', role='responsable')
        self.user_b = make_user(self.co_b, 'innov-reo-b')

    def _make(self, **kw):
        defaults = {'company': self.co_a, 'titre': 'Une idée', 'auteur': self.author}
        defaults.update(kw)
        return Idee.objects.create(**defaults)

    def test_author_reopens_from_fermee(self):
        idee = self._make(statut=Idee.Statut.FERMEE)
        resp = auth(self.author).post(f'{self.BASE}{idee.id}/reouvrir/')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.OUVERT)

    def test_author_reopens_from_examinee(self):
        idee = self._make(statut=Idee.Statut.EXAMINEE)
        resp = auth(self.author).post(f'{self.BASE}{idee.id}/reouvrir/')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.OUVERT)

    def test_locked_after_retenue(self):
        idee = self._make(statut=Idee.Statut.RETENUE)
        resp = auth(self.author).post(f'{self.BASE}{idee.id}/reouvrir/')
        self.assertEqual(resp.status_code, 400)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.RETENUE)

    def test_locked_after_realisee(self):
        idee = self._make(statut=Idee.Statut.REALISEE)
        resp = auth(self.author).post(f'{self.BASE}{idee.id}/reouvrir/')
        self.assertEqual(resp.status_code, 400)

    def test_non_author_refused(self):
        idee = self._make(statut=Idee.Statut.FERMEE)
        resp = auth(self.other).post(f'{self.BASE}{idee.id}/reouvrir/')
        self.assertEqual(resp.status_code, 400)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.FERMEE)

    def test_responsable_who_is_not_author_refused(self):
        """Le palier Directeur/Responsable ne contourne PAS la règle « auteur
        uniquement » — la ré-ouverture est une action de l'AUTEUR."""
        idee = self._make(statut=Idee.Statut.FERMEE)
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/reouvrir/')
        self.assertEqual(resp.status_code, 400)

    def test_already_ouvert_refused(self):
        idee = self._make(statut=Idee.Statut.OUVERT)
        resp = auth(self.author).post(f'{self.BASE}{idee.id}/reouvrir/')
        self.assertEqual(resp.status_code, 400)

    def test_reouvrir_logs_chatter(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        idee = self._make(statut=Idee.Statut.FERMEE)
        auth(self.author).post(f'{self.BASE}{idee.id}/reouvrir/')
        ct = ContentType.objects.get_for_model(Idee)
        act = Activity.objects.get(
            content_type=ct, object_id=idee.id, new_value=Idee.Statut.OUVERT)
        self.assertEqual(act.old_value, Idee.Statut.FERMEE)
        self.assertEqual(act.created_by, self.author)

    def test_cross_tenant_404(self):
        idee = self._make(statut=Idee.Statut.FERMEE)
        resp = auth(self.user_b).post(f'{self.BASE}{idee.id}/reouvrir/')
        self.assertEqual(resp.status_code, 404)
