"""Tests de la machine à états du Projet (PROJ3) — distincte de STAGES.py.

Le cycle de vie ``Projet.statut`` est PROPRE au projet d'installation solaire :
``brouillon → planifie → en_cours → en_pause → termine / annule`` (défaut
``brouillon``). Il ne réutilise AUCUNE clé du tunnel CRM (``STAGES.py``).

Couvre : statut par défaut, toutes les transitions légales + cycle de vie
complet, transitions illégales (→ 400 sans changement d'état), journal des
transitions (ancien → nouveau + auteur + société côté serveur), statut NON
modifiable par PATCH, scoping société (isolation) et 404 cross-tenant sur les
actions.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import Projet, ProjetActivity

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


class GestionProjetWorkflowTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-wf-a', 'A')
        self.co_b = make_company('gp-wf-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-wf-a')
        self.user_b = make_user(self.co_b, 'gp-wf-b')
        self._n = 0

    def _make(self, company, **kw):
        self._n += 1
        defaults = {'code': f'P-{self._n:03d}', 'nom': 'Centrale toiture'}
        defaults.update(kw)
        return Projet.objects.create(company=company, **defaults)

    # ── Statut par défaut (PROPRE, jamais STAGES.py) ─────────────────────────
    def test_default_statut_brouillon(self):
        p = self._make(self.co_a)
        self.assertEqual(p.statut, Projet.Statut.BROUILLON)

    # ── Transitions légales ──────────────────────────────────────────────────
    def test_planifier_brouillon_to_planifie(self):
        p = self._make(self.co_a)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/planifier/')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.PLANIFIE)

    def test_demarrer_planifie_to_en_cours(self):
        p = self._make(self.co_a, statut=Projet.Statut.PLANIFIE)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/demarrer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.EN_COURS)

    def test_mettre_en_pause_en_cours_to_en_pause(self):
        p = self._make(self.co_a, statut=Projet.Statut.EN_COURS)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/mettre-en-pause/')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.EN_PAUSE)

    def test_reprendre_en_pause_to_en_cours(self):
        p = self._make(self.co_a, statut=Projet.Statut.EN_PAUSE)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/reprendre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.EN_COURS)

    def test_demarrer_from_en_pause_allowed(self):
        p = self._make(self.co_a, statut=Projet.Statut.EN_PAUSE)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/demarrer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.EN_COURS)

    def test_terminer_en_cours_to_termine(self):
        p = self._make(self.co_a, statut=Projet.Statut.EN_COURS)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/terminer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.TERMINE)

    def test_annuler_from_brouillon(self):
        p = self._make(self.co_a)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/annuler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.ANNULE)

    def test_annuler_from_en_cours(self):
        p = self._make(self.co_a, statut=Projet.Statut.EN_COURS)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/annuler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.ANNULE)

    def test_full_lifecycle(self):
        p = self._make(self.co_a)
        api = auth(self.user_a)
        api.post(f'{self.BASE}{p.id}/planifier/')
        api.post(f'{self.BASE}{p.id}/demarrer/')
        api.post(f'{self.BASE}{p.id}/mettre-en-pause/')
        api.post(f'{self.BASE}{p.id}/reprendre/')
        api.post(f'{self.BASE}{p.id}/terminer/')
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.TERMINE)

    # ── Transitions illégales (400, état inchangé) ───────────────────────────
    def test_demarrer_from_brouillon_rejected(self):
        p = self._make(self.co_a)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/demarrer/')
        self.assertEqual(resp.status_code, 400)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.BROUILLON)

    def test_terminer_from_brouillon_rejected(self):
        p = self._make(self.co_a)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/terminer/')
        self.assertEqual(resp.status_code, 400)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.BROUILLON)

    def test_planifier_from_en_cours_rejected(self):
        p = self._make(self.co_a, statut=Projet.Statut.EN_COURS)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/planifier/')
        self.assertEqual(resp.status_code, 400)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.EN_COURS)

    def test_reprendre_from_en_cours_rejected(self):
        p = self._make(self.co_a, statut=Projet.Statut.EN_COURS)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/reprendre/')
        self.assertEqual(resp.status_code, 400)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.EN_COURS)

    def test_mettre_en_pause_from_planifie_rejected(self):
        p = self._make(self.co_a, statut=Projet.Statut.PLANIFIE)
        resp = auth(self.user_a).post(f'{self.BASE}{p.id}/mettre-en-pause/')
        self.assertEqual(resp.status_code, 400)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.PLANIFIE)

    def test_terminal_termine_is_immutable(self):
        p = self._make(self.co_a, statut=Projet.Statut.TERMINE)
        api = auth(self.user_a)
        for act in ('planifier', 'demarrer', 'mettre-en-pause', 'reprendre',
                    'terminer', 'annuler'):
            resp = api.post(f'{self.BASE}{p.id}/{act}/')
            self.assertEqual(resp.status_code, 400, act)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.TERMINE)

    def test_terminal_annule_is_immutable(self):
        p = self._make(self.co_a, statut=Projet.Statut.ANNULE)
        api = auth(self.user_a)
        for act in ('planifier', 'demarrer', 'mettre-en-pause', 'reprendre',
                    'terminer', 'annuler'):
            resp = api.post(f'{self.BASE}{p.id}/{act}/')
            self.assertEqual(resp.status_code, 400, act)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.ANNULE)

    # ── Journal des transitions ──────────────────────────────────────────────
    def test_transition_logs_activity_old_new_and_author(self):
        p = self._make(self.co_a)
        auth(self.user_a).post(f'{self.BASE}{p.id}/planifier/')
        act = ProjetActivity.objects.get(projet=p)
        self.assertEqual(act.old_value, Projet.Statut.BROUILLON)
        self.assertEqual(act.new_value, Projet.Statut.PLANIFIE)
        self.assertEqual(act.auteur, self.user_a)
        self.assertEqual(act.company, self.co_a)

    def test_illegal_transition_writes_no_activity(self):
        p = self._make(self.co_a)
        auth(self.user_a).post(f'{self.BASE}{p.id}/demarrer/')
        self.assertEqual(
            ProjetActivity.objects.filter(projet=p).count(), 0)

    def test_historique_returns_timeline_recent_first(self):
        p = self._make(self.co_a)
        api = auth(self.user_a)
        api.post(f'{self.BASE}{p.id}/planifier/')
        api.post(f'{self.BASE}{p.id}/demarrer/')
        resp = api.get(f'{self.BASE}{p.id}/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        # La plus récente d'abord (planifie → en_cours).
        self.assertEqual(resp.data[0]['new_value'], Projet.Statut.EN_COURS)

    # ── Statut non modifiable par PATCH direct ───────────────────────────────
    def test_statut_not_writable_via_patch(self):
        p = self._make(self.co_a)
        resp = auth(self.user_a).patch(
            f'{self.BASE}{p.id}/',
            {'statut': Projet.Statut.TERMINE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        # read_only_fields → PATCH ignore le statut.
        self.assertEqual(p.statut, Projet.Statut.BROUILLON)

    def test_statut_not_writable_at_create(self):
        resp = auth(self.user_a).post(
            self.BASE,
            {'code': 'P-CREATE', 'nom': 'X',
             'statut': Projet.Statut.TERMINE},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Projet.objects.get(id=resp.data['id'])
        # statut read-only à la création → reste au défaut.
        self.assertEqual(obj.statut, Projet.Statut.BROUILLON)

    # ── Isolation multi-société ──────────────────────────────────────────────
    def test_transition_cross_tenant_404(self):
        p = self._make(self.co_a)
        resp = auth(self.user_b).post(f'{self.BASE}{p.id}/planifier/')
        self.assertEqual(resp.status_code, 404)
        p.refresh_from_db()
        self.assertEqual(p.statut, Projet.Statut.BROUILLON)
        self.assertEqual(ProjetActivity.objects.count(), 0)

    def test_historique_cross_tenant_404(self):
        p = self._make(self.co_a)
        resp = auth(self.user_b).get(f'{self.BASE}{p.id}/historique/')
        self.assertEqual(resp.status_code, 404)

    # ── Rôle limité refusé sur les actions ───────────────────────────────────
    def test_role_normal_refused_on_action(self):
        p = self._make(self.co_a)
        normal = make_user(self.co_a, 'gp-wf-normal', role='normal')
        resp = auth(normal).post(f'{self.BASE}{p.id}/planifier/')
        self.assertEqual(resp.status_code, 403)
