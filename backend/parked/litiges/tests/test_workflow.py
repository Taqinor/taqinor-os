"""Tests du workflow de statut + chatter des Réclamations (LITIGE2).

Couvre : machine à états (transitions légales / illégales → 400), journal
automatique du chatter sur changement de statut (ancien → nouveau), note
manuelle, auteur + société posés côté serveur, et isolation multi-société
(404 cross-tenant sur les actions).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.litiges.models import Reclamation, ReclamationActivity

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


class LitigesWorkflowTests(TestCase):
    BASE = '/api/django/litiges/reclamations/'

    def setUp(self):
        self.co_a = make_company('litiges-wf-a', 'A')
        self.co_b = make_company('litiges-wf-b', 'B')
        self.user_a = make_user(self.co_a, 'litiges-wf-a')
        self.user_b = make_user(self.co_b, 'litiges-wf-b')

    def _make(self, company, **kw):
        defaults = {'objet': 'Facture contestée'}
        defaults.update(kw)
        return Reclamation.objects.create(company=company, **defaults)

    # ── Statut par défaut ────────────────────────────────────────────────────
    def test_default_statut_ouverte(self):
        r = self._make(self.co_a)
        self.assertEqual(r.statut, Reclamation.Statut.OUVERTE)

    # ── Transitions légales ──────────────────────────────────────────────────
    def test_prendre_en_charge_ouverte_to_en_traitement(self):
        r = self._make(self.co_a)
        resp = auth(self.user_a).post(f'{self.BASE}{r.id}/prendre-en-charge/')
        self.assertEqual(resp.status_code, 200, resp.data)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.EN_TRAITEMENT)

    def test_resoudre_en_traitement_to_resolue(self):
        r = self._make(self.co_a, statut=Reclamation.Statut.EN_TRAITEMENT)
        resp = auth(self.user_a).post(f'{self.BASE}{r.id}/resoudre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.RESOLUE)

    def test_rejeter_from_ouverte(self):
        r = self._make(self.co_a)
        resp = auth(self.user_a).post(f'{self.BASE}{r.id}/rejeter/')
        self.assertEqual(resp.status_code, 200, resp.data)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.REJETEE)

    def test_rejeter_from_en_traitement(self):
        r = self._make(self.co_a, statut=Reclamation.Statut.EN_TRAITEMENT)
        resp = auth(self.user_a).post(f'{self.BASE}{r.id}/rejeter/')
        self.assertEqual(resp.status_code, 200, resp.data)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.REJETEE)

    def test_full_lifecycle(self):
        r = self._make(self.co_a)
        api = auth(self.user_a)
        api.post(f'{self.BASE}{r.id}/prendre-en-charge/')
        api.post(f'{self.BASE}{r.id}/resoudre/')
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.RESOLUE)

    # ── Transitions illégales (400) ──────────────────────────────────────────
    def test_resoudre_from_ouverte_rejected(self):
        r = self._make(self.co_a)
        resp = auth(self.user_a).post(f'{self.BASE}{r.id}/resoudre/')
        self.assertEqual(resp.status_code, 400)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.OUVERTE)

    def test_prendre_en_charge_from_resolue_rejected(self):
        r = self._make(self.co_a, statut=Reclamation.Statut.RESOLUE)
        resp = auth(self.user_a).post(f'{self.BASE}{r.id}/prendre-en-charge/')
        self.assertEqual(resp.status_code, 400)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.RESOLUE)

    def test_resolve_a_rejected_claim_is_rejected(self):
        r = self._make(self.co_a, statut=Reclamation.Statut.REJETEE)
        resp = auth(self.user_a).post(f'{self.BASE}{r.id}/resoudre/')
        self.assertEqual(resp.status_code, 400)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.REJETEE)

    def test_rejeter_from_resolue_rejected(self):
        r = self._make(self.co_a, statut=Reclamation.Statut.RESOLUE)
        resp = auth(self.user_a).post(f'{self.BASE}{r.id}/rejeter/')
        self.assertEqual(resp.status_code, 400)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.RESOLUE)

    # ── Chatter : log automatique ────────────────────────────────────────────
    def test_transition_logs_chatter_old_new_and_author(self):
        r = self._make(self.co_a)
        auth(self.user_a).post(f'{self.BASE}{r.id}/prendre-en-charge/')
        act = ReclamationActivity.objects.get(reclamation=r)
        self.assertEqual(act.type, ReclamationActivity.Kind.LOG)
        self.assertEqual(act.old_value, Reclamation.Statut.OUVERTE)
        self.assertEqual(act.new_value, Reclamation.Statut.EN_TRAITEMENT)
        self.assertEqual(act.auteur, self.user_a)
        self.assertEqual(act.company, self.co_a)

    def test_illegal_transition_writes_no_chatter(self):
        r = self._make(self.co_a)
        auth(self.user_a).post(f'{self.BASE}{r.id}/resoudre/')
        self.assertEqual(
            ReclamationActivity.objects.filter(reclamation=r).count(), 0)

    # ── Chatter : note manuelle + historique ─────────────────────────────────
    def test_noter_creates_note_server_side_author(self):
        r = self._make(self.co_a)
        resp = auth(self.user_a).post(
            f'{self.BASE}{r.id}/noter/', {'message': 'Client recontacté'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        act = ReclamationActivity.objects.get(
            reclamation=r, type=ReclamationActivity.Kind.NOTE)
        self.assertEqual(act.message, 'Client recontacté')
        self.assertEqual(act.auteur, self.user_a)
        self.assertEqual(act.company, self.co_a)

    def test_noter_empty_rejected(self):
        r = self._make(self.co_a)
        resp = auth(self.user_a).post(
            f'{self.BASE}{r.id}/noter/', {'message': '   '}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ReclamationActivity.objects.count(), 0)

    def test_historique_returns_timeline_recent_first(self):
        r = self._make(self.co_a)
        api = auth(self.user_a)
        api.post(f'{self.BASE}{r.id}/prendre-en-charge/')
        api.post(f'{self.BASE}{r.id}/noter/', {'message': 'note'},
                 format='json')
        resp = api.get(f'{self.BASE}{r.id}/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        # Note la plus récente d'abord (ordering -date_creation).
        self.assertEqual(resp.data[0]['type'], 'note')

    # ── Isolation multi-société ──────────────────────────────────────────────
    def test_transition_cross_tenant_404(self):
        r = self._make(self.co_a)
        resp = auth(self.user_b).post(f'{self.BASE}{r.id}/prendre-en-charge/')
        self.assertEqual(resp.status_code, 404)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reclamation.Statut.OUVERTE)

    def test_noter_cross_tenant_404(self):
        r = self._make(self.co_a)
        resp = auth(self.user_b).post(
            f'{self.BASE}{r.id}/noter/', {'message': 'x'}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(ReclamationActivity.objects.count(), 0)

    def test_historique_cross_tenant_404(self):
        r = self._make(self.co_a)
        resp = auth(self.user_b).get(f'{self.BASE}{r.id}/historique/')
        self.assertEqual(resp.status_code, 404)

    # ── Permission : statut non modifiable par PATCH direct ──────────────────
    def test_statut_not_writable_via_patch(self):
        r = self._make(self.co_a)
        resp = auth(self.user_a).patch(
            f'{self.BASE}{r.id}/',
            {'statut': Reclamation.Statut.RESOLUE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        r.refresh_from_db()
        # read_only_fields → PATCH ignore le statut.
        self.assertEqual(r.statut, Reclamation.Statut.OUVERTE)

    # ── Rôle limité refusé sur les actions ───────────────────────────────────
    def test_role_normal_refused_on_action(self):
        r = self._make(self.co_a)
        normal = make_user(self.co_a, 'litiges-wf-normal', role='normal')
        resp = auth(normal).post(f'{self.BASE}{r.id}/prendre-en-charge/')
        self.assertEqual(resp.status_code, 403)
