"""Tests des dépendances de tâches (PROJ6 — FS/SS/FF/SF + lag).

Couvre : la création des quatre types de dépendance (FS/SS/FF/SF) avec un ``lag``
positif ET négatif ; la société posée côté serveur (jamais lue du corps) ; le
scoping multi-société (isolation + filtres) ; le refus de l'auto-dépendance
(400) ; le refus d'une dépendance entre tâches de projets DIFFÉRENTS (400) ; le
refus d'un cycle DIRECT (A→B alors que B→A existe, 400) ; le refus d'un FK d'une
AUTRE société (400) ; les sélecteurs prédécesseurs/successeurs ; et l'accès
réservé au palier Administrateur/Responsable (rôle ``normal`` → 403).

Le ``type_dependance`` est PROPRE à ce module (fs/ss/ff/sf) et ne réutilise
aucune clé de ``STAGES.py`` (règle #2).
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import DependanceTache, Projet, Tache

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


class DependanceTacheModelTests(TestCase):
    """Garde-fous au niveau modèle (``clean``)."""

    def setUp(self):
        self.co = make_company('gp-dep-mdl', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-DEP', nom='Projet dép')
        self.t1 = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T1', ordre=1)
        self.t2 = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T2', ordre=2)

    def test_clean_rejects_self_dependency(self):
        dep = DependanceTache(
            company=self.co, predecesseur=self.t1, successeur=self.t1)
        with self.assertRaises(ValidationError):
            dep.clean()

    def test_clean_rejects_cross_projet(self):
        autre_projet = Projet.objects.create(
            company=self.co, code='P-DEP2', nom='Projet dép 2')
        autre = Tache.objects.create(
            company=self.co, projet=autre_projet, libelle='Ailleurs')
        dep = DependanceTache(
            company=self.co, predecesseur=self.t1, successeur=autre)
        with self.assertRaises(ValidationError):
            dep.clean()

    def test_clean_rejects_direct_cycle(self):
        DependanceTache.objects.create(
            company=self.co, predecesseur=self.t1, successeur=self.t2)
        inverse = DependanceTache(
            company=self.co, predecesseur=self.t2, successeur=self.t1)
        with self.assertRaises(ValidationError):
            inverse.clean()

    def test_clean_accepts_valid_edge(self):
        dep = DependanceTache(
            company=self.co, predecesseur=self.t1, successeur=self.t2,
            type_dependance=DependanceTache.TypeDependance.SS, lag=-2)
        # Aucune exception levée.
        dep.clean()


class DependanceTacheSelectorTests(TestCase):
    """Sélecteurs prédécesseurs / successeurs / dependances_de_tache."""

    def setUp(self):
        self.co = make_company('gp-dep-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-SEL', nom='Projet sél')
        self.a = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='A', code_wbs='1',
            ordre=1)
        self.b = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='B', code_wbs='2',
            ordre=2)
        self.c = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='C', code_wbs='3',
            ordre=3)
        # A → B (FS) et A → C (SS) ; donc B et C ont A en prédécesseur.
        DependanceTache.objects.create(
            company=self.co, predecesseur=self.a, successeur=self.b,
            type_dependance=DependanceTache.TypeDependance.FS, lag=1)
        DependanceTache.objects.create(
            company=self.co, predecesseur=self.a, successeur=self.c,
            type_dependance=DependanceTache.TypeDependance.SS, lag=0)

    def test_successeurs_de_tache(self):
        succ = selectors.successeurs_de_tache(self.a)
        ids = sorted(d['tache_id'] for d in succ)
        self.assertEqual(ids, sorted([self.b.id, self.c.id]))
        types = {d['tache_id']: d['type_dependance'] for d in succ}
        self.assertEqual(types[self.b.id], 'fs')
        self.assertEqual(types[self.c.id], 'ss')

    def test_predecesseurs_de_tache(self):
        pred = selectors.predecesseurs_de_tache(self.b)
        self.assertEqual(len(pred), 1)
        self.assertEqual(pred[0]['tache_id'], self.a.id)
        self.assertEqual(pred[0]['tache_libelle'], 'A')
        self.assertEqual(pred[0]['lag'], 1)

    def test_dependances_de_tache_both_sides(self):
        # B est successeur de A et prédécesseur de rien.
        deps_b = selectors.dependances_de_tache(self.b)
        self.assertEqual(len(deps_b['predecesseurs']), 1)
        self.assertEqual(deps_b['successeurs'], [])
        # A est prédécesseur de B et C.
        deps_a = selectors.dependances_de_tache(self.a)
        self.assertEqual(deps_a['predecesseurs'], [])
        self.assertEqual(len(deps_a['successeurs']), 2)


class DependanceTacheApiTests(TestCase):
    BASE = '/api/django/gestion-projet/dependances/'

    def setUp(self):
        self.co_a = make_company('gp-dep-a', 'A')
        self.co_b = make_company('gp-dep-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-dep-a')
        self.user_b = make_user(self.co_b, 'gp-dep-b')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-A', nom='Projet A')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-B', nom='Projet B')
        self.a1 = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='A1', ordre=1)
        self.a2 = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='A2', ordre=2)
        self.b1 = Tache.objects.create(
            company=self.co_b, projet=self.projet_b, libelle='B1', ordre=1)

    def _payload(self, pred, succ, **over):
        data = {
            'predecesseur': pred.id,
            'successeur': succ.id,
            'type_dependance': 'fs',
            'lag': 0,
        }
        data.update(over)
        return data

    def test_create_fs_ss_ff_sf_with_lag(self):
        # Quatre types distincts entre quatre paires différentes (unique
        # ensemble prédécesseur/successeur) + lag positif et négatif.
        a3 = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='A3', ordre=3)
        a4 = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='A4', ordre=4)
        cases = [
            (self.a1, self.a2, 'fs', 3),
            (self.a1, a3, 'ss', -2),
            (self.a2, a3, 'ff', 0),
            (self.a2, a4, 'sf', 5),
        ]
        for pred, succ, typ, lag in cases:
            resp = auth(self.user_a).post(
                self.BASE, self._payload(pred, succ, type_dependance=typ,
                                         lag=lag), format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
            obj = DependanceTache.objects.get(id=resp.data['id'])
            self.assertEqual(obj.type_dependance, typ)
            self.assertEqual(obj.lag, lag)
            self.assertEqual(obj.company, self.co_a)

    def test_create_ignores_company_in_body(self):
        payload = self._payload(self.a1, self.a2)
        payload['company'] = self.co_b.id
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = DependanceTache.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_rejects_self_dependency(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.a1, self.a1), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('successeur', resp.data)
        self.assertFalse(DependanceTache.objects.exists())

    def test_rejects_cross_projet_dependency(self):
        # Prédécesseur projet A, successeur projet B (sociétés différentes →
        # le FK est d'abord rejeté même-société, donc 400 sur successeur).
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.a1, self.b1), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_rejects_cross_projet_same_company(self):
        # Deux projets de la MÊME société : la dépendance inter-projets est
        # refusée par le ``validate`` global (400 sur successeur).
        autre_projet = Projet.objects.create(
            company=self.co_a, code='P-A2', nom='Projet A2')
        autre = Tache.objects.create(
            company=self.co_a, projet=autre_projet, libelle='Autre')
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.a1, autre), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('successeur', resp.data)

    def test_rejects_direct_cycle(self):
        # A1 → A2 existe ; A2 → A1 doit être refusé (cycle direct).
        DependanceTache.objects.create(
            company=self.co_a, predecesseur=self.a1, successeur=self.a2)
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.a2, self.a1), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('successeur', resp.data)

    def test_rejects_cross_tenant_fk(self):
        # Tâche d'une AUTRE société → 400 (jamais 500 / fuite cross-tenant).
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.b1, self.a1), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('predecesseur', resp.data)

    def test_list_isolation(self):
        DependanceTache.objects.create(
            company=self.co_a, predecesseur=self.a1, successeur=self.a2)
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_projet(self):
        DependanceTache.objects.create(
            company=self.co_a, predecesseur=self.a1, successeur=self.a2)
        resp = auth(self.user_a).get(
            self.BASE + '?projet=%d' % self.projet_a.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_list_filter_by_successeur(self):
        a3 = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='A3', ordre=3)
        DependanceTache.objects.create(
            company=self.co_a, predecesseur=self.a1, successeur=self.a2)
        DependanceTache.objects.create(
            company=self.co_a, predecesseur=self.a1, successeur=a3)
        resp = auth(self.user_a).get(
            self.BASE + '?successeur=%d' % self.a2.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['successeur'], self.a2.id)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'gp-dep-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class DependanceTacheActionTests(TestCase):
    """Action ``taches/<id>/dependances/`` — prédécesseurs & successeurs."""
    BASE = '/api/django/gestion-projet/taches/'

    def setUp(self):
        self.co_a = make_company('gp-dep-act-a', 'A')
        self.co_b = make_company('gp-dep-act-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-dep-act-a')
        self.user_b = make_user(self.co_b, 'gp-dep-act-b')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-ACT', nom='Projet action')
        self.a = Tache.objects.create(
            company=self.co_a, projet=self.projet, libelle='A', ordre=1)
        self.b = Tache.objects.create(
            company=self.co_a, projet=self.projet, libelle='B', ordre=2)
        DependanceTache.objects.create(
            company=self.co_a, predecesseur=self.a, successeur=self.b,
            type_dependance=DependanceTache.TypeDependance.FS, lag=2)

    def test_action_returns_both_sides(self):
        resp = auth(self.user_a).get(f'{self.BASE}{self.b.id}/dependances/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['predecesseurs']), 1)
        self.assertEqual(resp.data['successeurs'], [])
        self.assertEqual(resp.data['predecesseurs'][0]['tache_id'], self.a.id)
        self.assertEqual(resp.data['predecesseurs'][0]['lag'], 2)

    def test_action_cross_tenant_404(self):
        resp = auth(self.user_b).get(f'{self.BASE}{self.a.id}/dependances/')
        self.assertEqual(resp.status_code, 404)
