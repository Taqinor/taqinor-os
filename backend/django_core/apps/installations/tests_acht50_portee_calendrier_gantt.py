"""ACHT50 (C-ACHT-049) — `interventions/calendrier/` et `chantiers/gantt/`
partent du queryset du viewset (portée de visibilité Feature F) : un
Technicien de portée équipe n'y voit que ce que sa liste lui montre.

Rejoue CTEN-1 : calendrier 200 i1 i2 · gantt avec le chantier hors portée.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht50_portee_calendrier_gantt"
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import Installation, Intervention
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    CANONICAL_SYSTEM_ROLES, TECHNICIEN_PERMISSIONS,
)

User = get_user_model()
BASE = '/api/django/installations'


class PorteeCalendrierGanttTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT50', slug='acht50-co')
        role_tech = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS))
        role_admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
        self.t1 = User.objects.create_user(
            username='t1-acht50', password='x', company=self.company,
            role=role_tech)
        self.t2 = User.objects.create_user(
            username='t2-acht50', password='x', company=self.company,
            role=role_tech)
        self.admin = User.objects.create_user(
            username='admin-acht50', password='x', company=self.company,
            role=role_admin)
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ACHT50',
            technicien_responsable=self.admin, created_by=self.admin)
        jour = datetime.date.today() + datetime.timedelta(days=2)
        self.i1 = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.t1, date_prevue=jour)
        self.i2 = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.t2, date_prevue=jour)
        self.fenetre = {
            'date_from': str(jour - datetime.timedelta(days=1)),
            'date_to': str(jour + datetime.timedelta(days=1))}

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _ids_calendrier(self, user):
        r = self._api(user).get(f'{BASE}/interventions/calendrier/',
                                self.fenetre)
        self.assertEqual(r.status_code, 200, r.data)
        ids = set()
        for groupe in r.data:
            for iv in groupe['interventions']:
                ids.add(iv['id'])
        return ids

    def test_technicien_voit_sa_portee(self):
        self.assertEqual(self._ids_calendrier(self.t1), {self.i1.id})
        r = self._api(self.t1).get(f'{BASE}/chantiers/gantt/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn(self.chantier.id, [row['id'] for row in r.data])

    def test_admin_voit_tout(self):
        self.assertEqual(self._ids_calendrier(self.admin),
                         {self.i1.id, self.i2.id})
        r = self._api(self.admin).get(f'{BASE}/chantiers/gantt/')
        self.assertIn(self.chantier.id, [row['id'] for row in r.data])
