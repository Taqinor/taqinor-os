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

    def test_partage_booleen_strict(self):
        # api-fuzz #956 : ``0`` n'est pas un booléen JSON → 400.
        req = self.factory.post(
            '/dashboards/', {'titre': 'D', 'partage': 0}, format='json')
        force_authenticate(req, user=self.user)
        resp = DashboardViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('partage', resp.data)

    def test_texte_chaine_stricte_post_put_patch(self):
        # CI #985 (api-fuzz) — ``"description": 0`` était converti en "0"
        # (200) alors que le schéma déclare une chaîne : 400 nommant le champ.
        dash = Dashboard.objects.create(
            company=self.company, owner=self.user, titre='Fuzz')
        corps = {'titre': '0', 'description': 0, 'layout': {},
                 'partage': False}
        for methode, action, chemin, kwargs in (
                ('post', 'create', '/dashboards/', {}),
                ('put', 'update', f'/dashboards/{dash.pk}/', {'pk': dash.pk}),
                ('patch', 'partial_update', f'/dashboards/{dash.pk}/',
                 {'pk': dash.pk})):
            with self.subTest(methode=methode):
                req = getattr(self.factory, methode)(
                    chemin, corps, format='json')
                force_authenticate(req, user=self.user)
                resp = DashboardViewSet.as_view({methode: action})(
                    req, **kwargs)
                self.assertEqual(resp.status_code,
                                 status.HTTP_400_BAD_REQUEST)
                self.assertIn('description', resp.data)
        req = self.factory.post('/dashboards/', {'titre': 7}, format='json')
        force_authenticate(req, user=self.user)
        resp = DashboardViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('titre', resp.data)
        dash.refresh_from_db()
        self.assertEqual(dash.description, '')

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

    def _role(self, nom, perms):
        from django.apps import apps as django_apps
        Role = django_apps.get_model('roles', 'Role')  # ENF20 : aucune arête core -> apps.roles
        role = Role.objects.create(company=self.company, nom=nom, permissions=list(perms))
        return User.objects.create_user(
            username=f'{nom}-{role.pk}', password='x', company=self.company, role=role)

    def _appel(self, vue, methode, action, user, corps=None, pk=None):
        req = getattr(self.factory, methode)('/x/', corps or {}, format='json')
        force_authenticate(req, user=user)
        kwargs = {'pk': pk} if pk else {}
        return vue.as_view({methode: action})(req, **kwargs).status_code

    def test_viewer_n_ecrit_ni_tableau_ni_requete(self):
        """APUB13 — les rôles LIVRÉS lecture seule (Viewer, Utilisateur) ne
        créent, ne modifient ni ne suppriment un tableau ou une requête ; ils
        exécutent toujours ``run/`` ; le Commercial crée."""
        from importlib import import_module
        from core import data_explorer
        from core.models import SavedQuery
        from core.views import SavedQueryViewSet
        reg = import_module('apps.roles.permissions_registre')
        data_explorer.register_dataset(
            'apub13_societes', 'Sociétés', ['id', 'nom'],
            lambda company, user: Company.objects.filter(pk=company.pk))
        dash = Dashboard.objects.create(
            company=self.company, owner=self.user, titre='Partagé', partage=True)
        requete = SavedQuery.objects.create(
            company=self.company, owner=self.user, titre='Q', dataset='apub13_societes',
            spec={'select': ['nom']}, partage=True)
        appel = self._appel
        for nom, perms in (('viewer', reg.VIEWER_PERMISSIONS),
                           ('utilisateur', reg.UTILISATEUR_PERMISSIONS)):
            lecteur = self._role(nom, perms)
            for vue, obj, corps in (
                    (DashboardViewSet, dash, {'titre': 'Pirate'}),
                    (SavedQueryViewSet, requete, {'titre': 'Pirate', 'dataset': 'x'})):
                with self.subTest(role=nom, vue=vue.__name__):
                    self.assertEqual(appel(vue, 'post', 'create', lecteur, corps), 403)
                    self.assertEqual(
                        appel(vue, 'patch', 'partial_update', lecteur, corps, obj.pk), 403)
                    self.assertEqual(appel(vue, 'delete', 'destroy', lecteur, pk=obj.pk), 403)
            self.assertEqual(appel(SavedQueryViewSet, 'post', 'run', lecteur, pk=requete.pk), 200)
        dash.refresh_from_db()
        requete.refresh_from_db()
        self.assertEqual((dash.titre, requete.titre), ('Partagé', 'Q'))
        self.assertFalse(Dashboard.objects.filter(titre='Pirate').exists())
        self.assertFalse(SavedQuery.objects.filter(titre='Pirate').exists())
        vendeur = self._role('commercial', reg.COMMERCIAL_PERMISSIONS)
        self.assertEqual(appel(DashboardViewSet, 'post', 'create', vendeur, {'titre': 'C'}), 201)
        self.assertEqual(appel(SavedQueryViewSet, 'post', 'create', vendeur,
                               {'titre': 'C', 'dataset': 'apub13_societes'}), 201)
