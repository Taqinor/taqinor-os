"""ALEA27 — toutes les actions annexes de ``LeadViewSet`` / ``ClientViewSet`` /
``AppointmentViewSet`` partent de la portée du viewset (société + équipe).

Constat C-ALEA-002 (sonde V4 LCOUT-2) : un Commercial (portée ``team``) qui
ne pouvait PAS lire le lead d'un collègue (GET → 404) pouvait pourtant le
réattribuer en masse (``updated: 1``) et lire ses coordonnées par les routes
de doublons. Aucun mock : rôles canoniques, ``core.scoping`` et vues réels.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Appointment, Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
from apps.ventes.models import Devis

User = get_user_model()

BASE = '/api/django/crm'
TEL_COLLEGUE = '+212661500001'


class PorteeActionsLeadTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA27', slug='taqinor-alea27')
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        self.moi = User.objects.create_user(
            username='alea27-moi', password='x', company=self.company,
            role=role)
        self.collegue = User.objects.create_user(
            username='alea27-collegue', password='x', company=self.company,
            role=role)
        self.admin = User.objects.create_user(
            username='alea27-admin', password='x', company=self.company,
            role_legacy='admin')
        # Le lead du collègue (hors portée) et son doublon.
        self.client_collegue = Client.objects.create(
            company=self.company, nom='Client collègue')
        self.l1 = Lead.objects.create(
            company=self.company, nom='Hors', prenom='Portee',
            telephone=TEL_COLLEGUE, email='hors.portee@example.ma',
            owner=self.collegue, stage=stages.CONTACTED,
            client=self.client_collegue)
        self.l1b = Lead.objects.create(
            company=self.company, nom='Hors', prenom='Portee',
            telephone=TEL_COLLEGUE, owner=self.collegue)
        # Mon lead (dans la portée).
        self.mien = Lead.objects.create(
            company=self.company, nom='Dans', prenom='Portee',
            telephone='+212661500099', owner=self.moi)
        self.api = APIClient()

    def _en(self, user):
        self.api.force_authenticate(user)
        return self.api

    def test_bulk_reassign_hors_portee_ignore(self):
        api = self._en(self.moi)
        self.assertEqual(
            api.get(f'{BASE}/leads/{self.l1.pk}/').status_code, 404)

        resp = api.post(f'{BASE}/leads/bulk/', {
            'action': 'reassign', 'ids': [self.l1.pk],
            'owner': self.moi.pk}, format='json')

        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['updated'], 0)
        # CLAUSE PERSISTANCE : L1 inchangé.
        self.l1.refresh_from_db()
        self.assertEqual(self.l1.owner_id, self.collegue.pk)
        self.assertEqual(self.l1.stage, stages.CONTACTED)
        self.assertFalse(self.l1.is_archived)

    def test_check_duplicates_hors_portee_masque(self):
        api = self._en(self.moi)

        resp = api.get(f'{BASE}/leads/check-duplicates/',
                       {'telephone': TEL_COLLEGUE})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json(), [])
        self.assertNotIn('hors.portee@example.ma', resp.content.decode())

        # Le détail d'un de MES leads ne rend pas non plus un doublon hors
        # portée : je pose mon téléphone sur celui du collègue.
        self.mien.telephone = TEL_COLLEGUE
        self.mien.save()  # recalcule phone_normalise
        resp = api.get(f'{BASE}/leads/{self.mien.pk}/duplicates/')
        self.assertEqual(resp.status_code, 200, resp.content)
        ids = {d['id'] for d in resp.json()}
        self.assertNotIn(self.l1.pk, ids)
        self.assertNotIn(self.l1b.pk, ids)

    def test_doublons_hors_portee_masques(self):
        resp = self._en(self.moi).get(f'{BASE}/leads/doublons/')
        self.assertEqual(resp.status_code, 200, resp.content)
        membres = {m['id'] for c in resp.json() for m in c['members']}
        self.assertNotIn(self.l1.pk, membres)
        self.assertNotIn(self.l1b.pk, membres)

    def test_dormants_bornes_portee(self):
        devis = Devis.objects.create(
            company=self.company, client=self.client_collegue,
            reference='DV-ALEA27', statut=Devis.Statut.ENVOYE,
            created_by=self.collegue)
        Devis.objects.filter(pk=devis.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=200))

        resp = self._en(self.moi).get(f'{BASE}/clients/dormants/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotIn(self.client_collegue.pk,
                         [r['id'] for r in resp.json()['results']])

        resp = self._en(self.admin).get(f'{BASE}/clients/dormants/')
        self.assertIn(self.client_collegue.pk,
                      [r['id'] for r in resp.json()['results']])

    def test_rendez_vous_bornes_portee(self):
        quand = timezone.now() + datetime.timedelta(days=2)
        rdv_collegue = Appointment.objects.create(
            company=self.company, lead=self.l1, scheduled_at=quand,
            created_by=self.collegue)
        rdv_mien = Appointment.objects.create(
            company=self.company, lead=self.mien, scheduled_at=quand,
            created_by=self.moi)

        resp = self._en(self.moi).get(f'{BASE}/appointments/')
        self.assertEqual(resp.status_code, 200, resp.content)
        donnees = resp.json()
        lignes = donnees['results'] if isinstance(donnees, dict) else donnees
        ids = {r['id'] for r in lignes}
        self.assertIn(rdv_mien.pk, ids)
        self.assertNotIn(rdv_collegue.pk, ids)

    def test_admin_voit_tout(self):
        api = self._en(self.admin)

        dups = api.get(f'{BASE}/leads/check-duplicates/',
                       {'telephone': TEL_COLLEGUE}).json()
        self.assertEqual({d['id'] for d in dups}, {self.l1.pk, self.l1b.pk})

        membres = {m['id'] for c in api.get(f'{BASE}/leads/doublons/').json()
                   for m in c['members']}
        self.assertIn(self.l1.pk, membres)

        resp = api.post(f'{BASE}/leads/bulk/', {
            'action': 'reassign', 'ids': [self.l1.pk],
            'owner': self.admin.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['updated'], 1)
