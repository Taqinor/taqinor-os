"""Tests FG381 — constructeur de dashboards sans-code (CRUD multi-tenant).

Couvre :
  * création : owner=utilisateur courant + company imposée (jamais du corps) ;
  * scoping : on voit ses dashboards perso + les partagés, PAS les perso d'autrui ;
  * isolation société : aucun dashboard d'une autre société ;
  * update ne réécrit pas company/owner ;
  * découplage : aucun import d'app domaine.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core.models import Dashboard
from core.views import DashboardViewSet

User = get_user_model()


class DashboardViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other_co = Company.objects.create(nom='Autre')
        cls.user = User.objects.create_user(
            username='u1', password='x', company=cls.company)
        cls.peer = User.objects.create_user(
            username='u2', password='x', company=cls.company)
        cls.factory = APIRequestFactory()

    def _list(self, user):
        req = self.factory.get('/dashboards/')
        force_authenticate(req, user=user)
        view = DashboardViewSet.as_view({'get': 'list'})
        return view(req)

    def test_create_sets_owner_and_company(self):
        req = self.factory.post(
            '/dashboards/',
            {'titre': 'Mon dash', 'layout': {'widgets': []}}, format='json')
        force_authenticate(req, user=self.user)
        view = DashboardViewSet.as_view({'post': 'create'})
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        dash = Dashboard.objects.get(titre='Mon dash')
        self.assertEqual(dash.company, self.company)
        self.assertEqual(dash.owner, self.user)

    def test_scoping_personal_and_shared(self):
        Dashboard.objects.create(
            company=self.company, owner=self.user, titre='A perso')
        Dashboard.objects.create(
            company=self.company, owner=self.peer, titre='B perso autrui')
        Dashboard.objects.create(
            company=self.company, owner=self.peer, titre='C partagé',
            partage=True)
        resp = self._list(self.user)
        titres = {d['titre'] for d in resp.data}
        self.assertIn('A perso', titres)
        self.assertIn('C partagé', titres)
        self.assertNotIn('B perso autrui', titres)

    def test_company_isolation(self):
        Dashboard.objects.create(
            company=self.other_co, titre='Autre société', partage=True)
        resp = self._list(self.user)
        titres = {d['titre'] for d in resp.data}
        self.assertNotIn('Autre société', titres)

    def test_update_does_not_reassign_owner(self):
        dash = Dashboard.objects.create(
            company=self.company, owner=self.user, titre='X')
        req = self.factory.patch(
            f'/dashboards/{dash.pk}/',
            {'titre': 'X modifié', 'owner': self.peer.pk}, format='json')
        force_authenticate(req, user=self.user)
        view = DashboardViewSet.as_view({'patch': 'partial_update'})
        resp = view(req, pk=dash.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        dash.refresh_from_db()
        self.assertEqual(dash.titre, 'X modifié')
        self.assertEqual(dash.owner, self.user)  # owner inchangé.
