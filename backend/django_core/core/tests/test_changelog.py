"""Tests FG399 — journal des nouveautés (changelog) + suivi de lecture.

Couvre :
  * la liste ne renvoie que les notes publiées aux non-admins, avec drapeau lu ;
  * non_lues compte par utilisateur ;
  * marquer_lu / marquer_tout_lu mettent à jour le suivi ;
  * publication (création) réservée au palier admin.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core.models import ChangelogEntry, ChangelogRead
from core.views import ChangelogViewSet

User = get_user_model()


class ChangelogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.admin = User.objects.create_user(
            username='cl_admin', password='x', role_legacy='admin',
            company=cls.company, is_staff=True)
        cls.user = User.objects.create_user(
            username='cl_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()
        cls.pub = ChangelogEntry.objects.create(
            titre='Nouveauté A', publie=True)
        cls.draft = ChangelogEntry.objects.create(
            titre='Brouillon B', publie=False)

    def _list(self, user):
        req = self.factory.get('/changelog/')
        force_authenticate(req, user=user)
        return ChangelogViewSet.as_view({'get': 'list'})(req)

    def test_list_only_published_for_non_admin(self):
        resp = self._list(self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titres = {e['titre'] for e in resp.data}
        self.assertIn('Nouveauté A', titres)
        self.assertNotIn('Brouillon B', titres)
        # Drapeau lu = False tant que non accusé.
        entry = next(e for e in resp.data if e['titre'] == 'Nouveauté A')
        self.assertFalse(entry['lu'])

    def test_non_lues_count(self):
        req = self.factory.get('/changelog/non_lues/')
        force_authenticate(req, user=self.user)
        resp = ChangelogViewSet.as_view({'get': 'non_lues'})(req)
        self.assertEqual(resp.data['non_lues'], 1)

    def test_marquer_lu(self):
        req = self.factory.post(f'/changelog/{self.pub.pk}/marquer_lu/')
        force_authenticate(req, user=self.user)
        resp = ChangelogViewSet.as_view(
            {'post': 'marquer_lu'})(req, pk=self.pub.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(
            ChangelogRead.objects.filter(
                user=self.user, entry=self.pub).exists())

    def test_marquer_tout_lu(self):
        req = self.factory.post('/changelog/marquer_tout_lu/')
        force_authenticate(req, user=self.user)
        resp = ChangelogViewSet.as_view({'post': 'marquer_tout_lu'})(req)
        self.assertEqual(resp.data['non_lues'], 0)
        self.assertEqual(
            ChangelogRead.objects.filter(user=self.user).count(), 1)

    def test_create_requires_admin(self):
        req = self.factory.post('/changelog/', {'titre': 'X'}, format='json')
        force_authenticate(req, user=self.user)
        resp = ChangelogViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_publish(self):
        req = self.factory.post(
            '/changelog/', {'titre': 'Note', 'publie': True}, format='json')
        force_authenticate(req, user=self.admin)
        resp = ChangelogViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
