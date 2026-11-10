"""Tests FG382 — explorateur de données (query builder sans SQL).

Couvre :
  * registre de datasets + liste blanche de champs (champ hors liste rejeté) ;
  * exécution : sélection, filtre, group_by + agrégation ;
  * scoping société porté par le queryset_provider du dataset ;
  * SavedQuery : company/owner imposés côté serveur, visibilité perso/partagé ;
  * découplage : le test enregistre un dataset sur un modèle de FONDATION
    (Company) — aucun import d'app domaine.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import data_explorer
from core.models import SavedQuery
from core.views import SavedQueryViewSet

User = get_user_model()


def _users_dataset_provider(company, user):
    # Queryset déjà scopé société (la sécurité reste chez le fournisseur).
    return User.objects.filter(company=company)


class DataExplorerEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.u1 = User.objects.create_user(
            username='a', password='x', company=cls.company, is_active=True)
        cls.u2 = User.objects.create_user(
            username='b', password='x', company=cls.company, is_active=False)
        User.objects.create_user(
            username='c', password='x', company=cls.other)

    def setUp(self):
        data_explorer.register_dataset(
            'utilisateurs', 'Utilisateurs',
            ['id', 'username', 'is_active'], _users_dataset_provider)

    def test_list_datasets_includes_registered(self):
        names = {d['name'] for d in data_explorer.list_datasets()}
        self.assertIn('utilisateurs', names)

    def test_select_and_filter_scoped(self):
        rows = data_explorer.run_query(
            'utilisateurs', self.company, self.u1,
            {'select': ['username'], 'filters': {'is_active': True}})
        usernames = {r['username'] for r in rows}
        self.assertEqual(usernames, {'a'})  # u2 inactif exclu, autre société hors scope

    def test_group_by_aggregate(self):
        rows = data_explorer.run_query(
            'utilisateurs', self.company, self.u1,
            {'group_by': ['is_active'],
             'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}]})
        by_active = {r['is_active']: r['n'] for r in rows}
        self.assertEqual(by_active.get(True), 1)
        self.assertEqual(by_active.get(False), 1)

    def test_field_not_whitelisted_rejected(self):
        with self.assertRaises(data_explorer.ChampNonAutorise):
            data_explorer.run_query(
                'utilisateurs', self.company, self.u1,
                {'select': ['password']})  # hors liste blanche

    def test_unknown_dataset_raises(self):
        with self.assertRaises(data_explorer.DatasetInconnu):
            data_explorer.run_query('inexistant', self.company, self.u1, {})

    def test_droit_du_module_et_portee_du_lecteur(self):
        """APFS4 (C-APFS-020) — le moteur applique le droit du module du jeu et la
        portée « soi » du lecteur ; un compte hérité (sans rôle fin) voit tout."""
        from django.apps import apps as django_apps
        Role = django_apps.get_model('roles', 'Role')  # ENF20 : aucune arête core -> apps.roles
        data_explorer.register_dataset(
            'apfs4_requetes', 'Requêtes', ['id', 'titre'],
            lambda company, user: SavedQuery.objects.filter(company=company), module='crm')

        def compte(nom, perms):
            role = Role.objects.create(company=self.company, nom=nom, permissions=perms)
            return User.objects.create_user(username=nom, password='x', company=self.company, role=role)
        rh = compte('apfs4-rh', ['rh_voir'])
        lecteur = compte('apfs4-crm', ['crm_voir'])
        soi = compte('apfs4-soi', ['crm_voir', 'records_scope_soi'])
        SavedQuery.objects.create(company=self.company, owner=soi, titre='A moi', dataset='x')
        SavedQuery.objects.create(company=self.company, owner=self.u1, titre='Autre', dataset='x')
        spec = {'select': ['titre']}
        with self.assertRaises(data_explorer.DatasetNonAutorise):
            data_explorer.run_query('apfs4_requetes', self.company, rh, spec)
        titres = lambda u: {r['titre'] for r in data_explorer.run_query(  # noqa: E731
            'apfs4_requetes', self.company, u, spec)}
        self.assertEqual(titres(lecteur), {'A moi', 'Autre'})
        self.assertEqual(titres(soi), {'A moi'})
        self.assertEqual(titres(self.u1), {'A moi', 'Autre'})  # hérité : tout
        # Le HIT du cache BI repasse par le droit du module.
        from core import bi_cache
        with self.assertRaises(data_explorer.DatasetNonAutorise):
            bi_cache.run_query_cache('apfs4_requetes', self.company, rh, spec, ttl=60)


class SavedQueryViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.user = User.objects.create_user(
            username='u1', password='x', company=cls.company)
        cls.factory = APIRequestFactory()

    def test_create_imposes_company_and_owner(self):
        req = self.factory.post(
            '/saved-queries/',
            {'titre': 'Q1', 'dataset': 'utilisateurs', 'spec': {}},
            format='json')
        force_authenticate(req, user=self.user)
        view = SavedQueryViewSet.as_view({'post': 'create'})
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        sq = SavedQuery.objects.get(titre='Q1')
        self.assertEqual(sq.company, self.company)
        self.assertEqual(sq.owner, self.user)

    def test_types_stricts_post_put_patch(self):
        # CI #985 (api-fuzz) — ``"partage": 0`` (booléen) et ``"titre": 0``
        # (chaîne) étaient convertis en silence (200) : 400 nommant le champ.
        sq = SavedQuery.objects.create(
            company=self.company, owner=self.user, titre='Fuzz',
            dataset='utilisateurs')
        for corps, champ in (
                ({'titre': '0', 'dataset': '0', 'spec': {}, 'partage': 0},
                 'partage'),
                ({'titre': 0, 'dataset': 'utilisateurs', 'spec': {}},
                 'titre')):
            for methode, action, kwargs in (
                    ('post', 'create', {}),
                    ('put', 'update', {'pk': sq.pk}),
                    ('patch', 'partial_update', {'pk': sq.pk})):
                with self.subTest(methode=methode, champ=champ):
                    req = getattr(self.factory, methode)(
                        '/saved-queries/', corps, format='json')
                    force_authenticate(req, user=self.user)
                    resp = SavedQueryViewSet.as_view({methode: action})(
                        req, **kwargs)
                    self.assertEqual(resp.status_code,
                                     status.HTTP_400_BAD_REQUEST)
                    self.assertIn(champ, resp.data)
        self.assertEqual(SavedQuery.objects.count(), 1)

    def test_run_adhoc_corps_hors_schema_400(self):
        # ERR-ENF11-FUZZ-CORE — `dataset` liste (500 avant), `spec` non objet.
        view = SavedQueryViewSet.as_view({'post': 'run_adhoc'})
        for corps in ({'dataset': [None, None], 'spec': None},
                      {'dataset': 'nope', 'spec': [1]}):
            with self.subTest(corps=corps):
                req = self.factory.post(
                    '/saved-queries/run/', corps, format='json')
                force_authenticate(req, user=self.user)
                self.assertEqual(view(req).status_code,
                                 status.HTTP_400_BAD_REQUEST)

    def test_run_requete_enregistree_dataset_inconnu_est_409(self):
        # api-fuzz-full 41773314544 : la requête existe, c'est son dataset stocké
        # qui n'existe pas (le 404 lisait « ressource indisponible après création »).
        requete = SavedQuery.objects.create(
            company=self.user.company, owner=self.user, titre='q', dataset='nope')
        req = self.factory.post(f'/saved-queries/{requete.pk}/run/', {}, format='json')
        force_authenticate(req, user=self.user)
        resp = SavedQueryViewSet.as_view({'post': 'run'})(req, pk=requete.pk)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_run_adhoc_unknown_dataset_is_404(self):
        req = self.factory.post(
            '/saved-queries/run/', {'dataset': 'nope'}, format='json')
        force_authenticate(req, user=self.user)
        view = SavedQueryViewSet.as_view({'post': 'run_adhoc'})
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
