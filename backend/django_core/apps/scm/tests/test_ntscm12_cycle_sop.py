"""NTSCM12 — Cycle S&OP mensuel : modèle et statuts.

Critère d'acceptation : tenter de sauter une étape (ex. brouillon->approuve
directement) renvoie 400 ; l'historique des transitions est conservé."""
from django.test import TestCase

from apps.scm.models import CyclePlanificationSOP
from apps.scm.services import avancer_statut_cycle, reouvrir_cycle

from .helpers import auth, make_company, make_user


class CycleSopStateMachineApiTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-sop', 'Supply SOP')
        self.admin = make_user(self.company, 'scm-sop-admin', 'admin')
        self.api = auth(self.admin)
        resp = self.api.post('/api/django/scm/cycles-sop/', {
            'periode': '2026-09',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.cycle_id = resp.data['id']
        self.assertEqual(resp.data['statut'], 'brouillon')

    def test_skipping_a_step_returns_400(self):
        resp = self.api.post(
            f'/api/django/scm/cycles-sop/{self.cycle_id}/avancer-statut/',
            {'statut': 'approuve'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

        cycle = CyclePlanificationSOP.objects.get(id=self.cycle_id)
        self.assertEqual(cycle.statut, 'brouillon')  # inchangé après le refus

    def test_sequential_advance_succeeds_and_history_is_kept(self):
        resp = self.api.post(
            f'/api/django/scm/cycles-sop/{self.cycle_id}/avancer-statut/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'revue_demande')

        resp = self.api.post(
            f'/api/django/scm/cycles-sop/{self.cycle_id}/avancer-statut/',
            {'statut': 'revue_offre'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'revue_offre')

        hist = self.api.get(
            f'/api/django/scm/cycles-sop/{self.cycle_id}/historique/')
        self.assertEqual(hist.status_code, 200, hist.data)
        self.assertEqual(len(hist.data), 2)
        self.assertEqual(hist.data[0]['field'], 'statut')
        transitions = {(e['old_value'], e['new_value']) for e in hist.data}
        self.assertEqual(
            transitions,
            {('brouillon', 'revue_demande'), ('revue_demande', 'revue_offre')})

    def test_full_sequence_to_clos_then_refuses_further_advance(self):
        cycle = CyclePlanificationSOP.objects.get(id=self.cycle_id)
        for _ in range(len(CyclePlanificationSOP.STATUT_ORDER) - 1):
            avancer_statut_cycle(cycle, self.admin)
        cycle.refresh_from_db()
        self.assertEqual(cycle.statut, CyclePlanificationSOP.Statut.CLOS)

        with self.assertRaises(ValueError):
            avancer_statut_cycle(cycle, self.admin)

    def test_statut_cannot_be_patched_directly(self):
        resp = self.api.patch(
            f'/api/django/scm/cycles-sop/{self.cycle_id}/',
            {'statut': 'approuve'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # `statut` en lecture seule côté serializer : le PATCH réussit mais
        # n'a aucun effet sur le champ protégé.
        self.assertEqual(resp.data['statut'], 'brouillon')

    def test_reouvrir_requires_admin_and_logs_history(self):
        cycle = CyclePlanificationSOP.objects.get(id=self.cycle_id)
        avancer_statut_cycle(cycle, self.admin)  # -> revue_demande
        cycle.refresh_from_db()

        responsable = make_user(self.company, 'scm-sop-resp', 'responsable')
        resp = auth(responsable).post(
            f'/api/django/scm/cycles-sop/{self.cycle_id}/reouvrir/',
            {'motif': 'test'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

        resp = self.api.post(
            f'/api/django/scm/cycles-sop/{self.cycle_id}/reouvrir/',
            {'motif': 'erreur de saisie demande'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'brouillon')

        hist = self.api.get(
            f'/api/django/scm/cycles-sop/{self.cycle_id}/historique/')
        self.assertEqual(len(hist.data), 2)  # avancer + reouvrir

    def test_unique_periode_per_company(self):
        resp = self.api.post('/api/django/scm/cycles-sop/', {
            'periode': '2026-09',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_tenant_isolation(self):
        other_company = make_company('scm-sop-b', 'Supply SOP B')
        other_admin = make_user(other_company, 'scm-sop-admin-b', 'admin')
        resp = auth(other_admin).get('/api/django/scm/cycles-sop/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(rows, [])


class ReouvrirCycleServiceTests(TestCase):
    def test_reouvrir_cycle_resets_to_brouillon(self):
        company = make_company('scm-sop-svc', 'Supply SOP Service')
        admin = make_user(company, 'scm-sop-svc-admin', 'admin')
        cycle = CyclePlanificationSOP.objects.create(
            company=company, periode='2026-10',
            statut=CyclePlanificationSOP.Statut.REVUE_FINANCE)
        reouvrir_cycle(cycle, admin, motif='correction')
        cycle.refresh_from_db()
        self.assertEqual(cycle.statut, CyclePlanificationSOP.Statut.BROUILLON)
