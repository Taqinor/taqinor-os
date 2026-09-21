"""Tests du détail idée + actions de transition (NTIDE5).

Couvre : machine à états (examiner/retenir/réaliser/fermer), 400 sur
transition illégale, 403 pour un rôle limité, 404 cross-tenant, chatter
automatique (``records.Activity`` générique, ARC8) sur chaque transition
avec note optionnelle sur fermeture, et le détail complet (historique + lien
opaque devis/ticket/chantier).
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


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class IdeeActionsTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-act-a', 'A')
        self.co_b = make_company('innov-act-b', 'B')
        self.resp_a = make_user(self.co_a, 'innov-act-resp')
        self.normal_a = make_user(self.co_a, 'innov-act-normal', role='normal')
        self.user_b = make_user(self.co_b, 'innov-act-b-user')

    def _make(self, **kw):
        defaults = {'company': self.co_a, 'titre': 'Une idée'}
        defaults.update(kw)
        return Idee.objects.create(**defaults)

    # ── Transitions légales ──────────────────────────────────────────────────
    def test_examiner_ouvert_to_examinee(self):
        idee = self._make()
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/examiner/')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.EXAMINEE)

    def test_retenir_examinee_to_retenue(self):
        idee = self._make(statut=Idee.Statut.EXAMINEE)
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/retenir/')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.RETENUE)

    def test_realiser_retenue_to_realisee(self):
        idee = self._make(statut=Idee.Statut.RETENUE)
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/realiser/')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.REALISEE)

    def test_fermer_from_ouvert(self):
        idee = self._make()
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/fermer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.FERMEE)

    def test_fermer_from_retenue(self):
        idee = self._make(statut=Idee.Statut.RETENUE)
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/fermer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.FERMEE)

    # ── Transitions illégales ────────────────────────────────────────────────
    def test_realiser_from_ouvert_rejected(self):
        idee = self._make()
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/realiser/')
        self.assertEqual(resp.status_code, 400)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.OUVERT)

    def test_fermer_from_realisee_rejected(self):
        """Une idée réalisée est terminale — pas de fermeture après coup."""
        idee = self._make(statut=Idee.Statut.REALISEE)
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/fermer/')
        self.assertEqual(resp.status_code, 400)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.REALISEE)

    def test_examiner_from_fermee_rejected(self):
        idee = self._make(statut=Idee.Statut.FERMEE)
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/examiner/')
        self.assertEqual(resp.status_code, 400)

    # ── Palier d'accès ───────────────────────────────────────────────────────
    def test_role_normal_refused_on_action(self):
        idee = self._make()
        resp = auth(self.normal_a).post(f'{self.BASE}{idee.id}/examiner/')
        self.assertEqual(resp.status_code, 403)

    def test_role_normal_can_still_read_detail(self):
        idee = self._make()
        resp = auth(self.normal_a).get(f'{self.BASE}{idee.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_cross_tenant_404_on_action(self):
        idee = self._make()
        resp = auth(self.user_b).post(f'{self.BASE}{idee.id}/examiner/')
        self.assertEqual(resp.status_code, 404)

    # ── Chatter automatique (ARC8, records.Activity générique) ──────────────
    def test_transition_logs_chatter_old_new_and_author(self):
        from apps.records.models import Activity

        idee = self._make()
        auth(self.resp_a).post(f'{self.BASE}{idee.id}/examiner/')
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Idee)
        act = Activity.objects.get(
            content_type=ct, object_id=idee.id, kind=Activity.Kind.MODIFICATION)
        self.assertEqual(act.field, 'statut')
        self.assertEqual(act.old_value, Idee.Statut.OUVERT)
        self.assertEqual(act.new_value, Idee.Statut.EXAMINEE)
        self.assertEqual(act.created_by, self.resp_a)
        self.assertEqual(act.company, self.co_a)

    def test_fermer_with_note_logs_body(self):
        from apps.records.models import Activity

        idee = self._make()
        resp = auth(self.resp_a).post(
            f'{self.BASE}{idee.id}/fermer/', {'note': 'Doublon d\'une autre idée'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Idee)
        act = Activity.objects.get(
            content_type=ct, object_id=idee.id, new_value=Idee.Statut.FERMEE)
        self.assertEqual(act.body, "Doublon d'une autre idée")

    def test_illegal_transition_writes_no_chatter(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        idee = self._make()
        auth(self.resp_a).post(f'{self.BASE}{idee.id}/realiser/')
        ct = ContentType.objects.get_for_model(Idee)
        self.assertEqual(
            Activity.objects.filter(
                content_type=ct, object_id=idee.id,
                kind=Activity.Kind.MODIFICATION).count(),
            0)

    def test_creation_logs_chatter(self):
        from apps.records.models import Activity

        resp = auth(self.resp_a).post(
            self.BASE, {'titre': 'Nouvelle idée'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Idee)
        self.assertTrue(Activity.objects.filter(
            content_type=ct, object_id=resp.data['id'],
            kind=Activity.Kind.CREATION).exists())

    # ── Détail : historique + lien opaque ────────────────────────────────────
    def test_detail_includes_historique(self):
        idee = self._make()
        auth(self.resp_a).post(f'{self.BASE}{idee.id}/examiner/')
        resp = auth(self.resp_a).get(f'{self.BASE}{idee.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['historique']), 1)
        self.assertEqual(resp.data['historique'][0]['new_value'], 'examinee')

    def test_detail_includes_lien_opaque(self):
        idee = self._make(linked_type=Idee.LinkedType.DEVIS, linked_id=42)
        resp = auth(self.resp_a).get(f'{self.BASE}{idee.id}/')
        self.assertEqual(resp.data['linked_type'], 'devis')
        self.assertEqual(resp.data['linked_id'], 42)

    def test_historique_endpoint_cross_tenant_404(self):
        idee = self._make()
        resp = auth(self.user_b).get(f'{self.BASE}{idee.id}/historique/')
        self.assertEqual(resp.status_code, 404)

    def test_historique_endpoint_recent_first(self):
        idee = self._make()
        api = auth(self.resp_a)
        api.post(f'{self.BASE}{idee.id}/examiner/')
        api.post(f'{self.BASE}{idee.id}/retenir/')
        resp = api.get(f'{self.BASE}{idee.id}/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]['new_value'], 'retenue')
