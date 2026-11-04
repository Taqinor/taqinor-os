"""N84 — calendrier / agenda (multi-tenant, agrégation + replanification)."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from authentication.models import Company

User = get_user_model()


class TestCalendar(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cal-co', defaults={'nom': 'Cal Co'})[0]
        self.other = Company.objects.create(slug='cal-other', nom='Autre')
        self.user = User.objects.create_user(
            username='cal_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client A')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _chantier(self, **kw):
        return Installation.objects.create(
            company=self.company, reference=kw.pop('reference', 'CH-1'),
            client=self.client_obj, **kw)

    def test_pose_event_in_window_and_scoped(self):
        soon = date.today() + timedelta(days=5)
        self._chantier(reference='CH-POSE', date_pose_prevue=soon)
        # Chantier d'une autre société : ne doit pas apparaître.
        Installation.objects.create(
            company=self.other, reference='CH-X',
            client=Client.objects.create(company=self.other, nom='B'),
            date_pose_prevue=soon)
        resp = self.api.get('/api/django/reporting/calendar/')
        self.assertEqual(resp.status_code, 200)
        poses = [e for e in resp.data['events'] if e['type'] == 'pose']
        self.assertEqual(len(poses), 1)
        self.assertEqual(poses[0]['link_id'], self._only_pk('CH-POSE'))
        self.assertTrue(poses[0]['editable'])

    def _only_pk(self, ref):
        return Installation.objects.get(company=self.company,
                                        reference=ref).pk

    def test_type_filter_excludes_others(self):
        soon = date.today() + timedelta(days=3)
        self._chantier(reference='CH-MES', date_mise_en_service=soon)
        self._chantier(reference='CH-P', date_pose_prevue=soon)
        resp = self.api.get('/api/django/reporting/calendar/?types=pose')
        self.assertEqual(resp.status_code, 200)
        types = {e['type'] for e in resp.data['events']}
        self.assertEqual(types, {'pose'})

    def test_reschedule_pose_updates_date(self):
        soon = date.today() + timedelta(days=5)
        inst = self._chantier(reference='CH-R', date_pose_prevue=soon)
        new = (date.today() + timedelta(days=12)).isoformat()
        resp = self.api.post(
            '/api/django/reporting/calendar/reschedule/',
            {'type': 'pose', 'id': inst.pk, 'date': new}, format='json')
        self.assertEqual(resp.status_code, 200)
        inst.refresh_from_db()
        self.assertEqual(inst.date_pose_prevue.isoformat(), new)

    def test_reschedule_rejects_computed_type(self):
        resp = self.api.post(
            '/api/django/reporting/calendar/reschedule/',
            {'type': 'visite_maintenance', 'id': 1,
             'date': date.today().isoformat()}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_maintenance_visits_visible_when_filtering_by_assignee(self):
        """Un filtre ?assignee= ne doit pas masquer les visites de maintenance
        (calculées, sans responsable)."""
        from apps.sav.models import ContratMaintenance
        soon = date.today() + timedelta(days=10)
        # Visite due dans la fenêtre : date_debut tel que +1 mois ≈ soon.
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='mensuel',
            date_debut=date.today() - timedelta(days=20),
            derniere_visite=soon - timedelta(days=30), actif=True)
        resp = self.api.get(
            f'/api/django/reporting/calendar/?assignee={self.user.pk}')
        self.assertEqual(resp.status_code, 200)
        visites = [e for e in resp.data['events']
                   if e['type'] == 'visite_maintenance']
        self.assertGreaterEqual(len(visites), 1)
        self.assertIsNone(visites[0]['assignee_id'])

    def test_reschedule_intervention_comme_un_report(self):
        """ACHT135 (C-ACHT-VER4-030) — glisser une intervention confirmée dans
        l'Agenda la déconfirme, compte un report et le trace (comme le PATCH) ;
        rejouer la même date n'est pas un second report."""
        from apps.installations.models import Intervention, InterventionActivity
        iv = Intervention.objects.create(
            company=self.company, installation=self._chantier(reference='CH-IV'),
            type_intervention='pose', created_by=self.user,
            date_prevue=date.today() + timedelta(days=3), rdv_confirme=True)
        new = (date.today() + timedelta(days=5)).isoformat()
        corps = {'type': 'intervention', 'id': iv.pk, 'date': new}
        for _ in range(2):
            resp = self.api.post(
                '/api/django/reporting/calendar/reschedule/', corps, format='json')
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data, {'ok': True, 'date': new})
        iv.refresh_from_db()
        self.assertEqual(iv.date_prevue.isoformat(), new)
        self.assertFalse(iv.rdv_confirme)
        self.assertEqual(iv.rdv_reschedule_count, 1)
        self.assertEqual(InterventionActivity.objects.filter(
            intervention=iv, body__startswith='RDV reporté').count(), 1)

    def _portee(self):
        """ACHT136/137 — t1, t2 Techniciens (portée équipe), un admin ; i1 (t1),
        i2 (t2) sur un chantier C2 hors portée de t1, pose dans la fenêtre."""
        from apps.installations.models import Intervention
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            CANONICAL_SYSTEM_ROLES, TECHNICIEN_PERMISSIONS)
        role_tech = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS))
        role_admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
        p = {nom: User.objects.create_user(
            username=f'{nom}-cal', password='x', company=self.company, role=role)
            for nom, role in (('t1', role_tech), ('t2', role_tech), ('admin', role_admin))}
        jour = date.today() + timedelta(days=2)
        p['c2'] = Installation.objects.create(
            company=self.company, reference='CH-C2', client=self.client_obj,
            technicien_responsable=p['t2'], created_by=p['admin'], date_pose_prevue=jour)
        for n, tech in (('i1', p['t1']), ('i2', p['t2'])):
            p[n] = Intervention.objects.create(
                company=self.company, installation=p['c2'],
                type_intervention='pose', technicien=tech, date_prevue=jour)
        return p

    def _api_de(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_technicien_borne_a_sa_portee(self):
        """ACHT136 (C-ACHT-VER4-031) — l'agenda d'un Technicien a la portée de
        ses listes : i1 seule, aucune pose de C2 ; l'admin voit tout."""
        p = self._portee()

        def vus(user):
            r = self._api_de(user).get('/api/django/reporting/calendar/')
            self.assertEqual(r.status_code, 200, r.data)
            return {e['id'] for e in r.data['events'] if e['type'] in ('pose', 'intervention')}
        self.assertEqual(vus(p['t1']), {f"intervention-{p['i1'].pk}"})
        self.assertEqual(vus(p['admin']), {
            f"intervention-{p['i1'].pk}", f"intervention-{p['i2'].pk}", f"pose-{p['c2'].pk}"})
        autre = User.objects.create_user(
            username='autre-cal', password='x', role_legacy='responsable', company=self.other)
        self.assertEqual(vus(autre), set())
