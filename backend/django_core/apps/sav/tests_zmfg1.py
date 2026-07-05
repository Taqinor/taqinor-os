"""ZMFG1 — Équipes de maintenance (Configuration > Maintenance Teams).

Couvre :
  * CRUD équipe scopé société ;
  * un membre d'une autre société est refusé (400) ;
  * un ticket est filtrable/affectable par équipe (`?equipe=`) ;
  * isolation multi-tenant.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg1 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import EquipeMaintenance, Ticket

User = get_user_model()


def make_company(slug='sav-zmfg1', nom='Sav Co ZMFG1'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZMFG1EquipeMaintenanceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zmfg1_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.tech1 = User.objects.create_user(
            username='zmfg1_tech1', password='x', role_legacy='normal',
            company=self.company)
        self.other_company = make_company(
            slug='sav-zmfg1-other', nom='Sav Co ZMFG1 Other')
        self.other_user = User.objects.create_user(
            username='zmfg1_other_user', password='x', role_legacy='normal',
            company=self.other_company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG1',
            email='zmfg1-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZMFG1', client=self.client_obj)

    def test_crud_scoped_to_company(self):
        r = self.api.post('/api/django/sav/equipes-maintenance/', {
            'nom': 'Équipe Nord', 'membres': [self.tech1.id],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        equipe_id = r.data['id']
        equipe = EquipeMaintenance.objects.get(pk=equipe_id)
        self.assertEqual(equipe.company_id, self.company.id)
        self.assertEqual(equipe.membres.count(), 1)

        r2 = self.api.get('/api/django/sav/equipes-maintenance/')
        ids = [row['id'] for row in r2.data.get(
            'results', r2.data if isinstance(r2.data, list) else [])]
        self.assertIn(equipe_id, ids)

    def test_membre_autre_societe_refuse(self):
        r = self.api.post('/api/django/sav/equipes-maintenance/', {
            'nom': 'Équipe Sud', 'membres': [self.other_user.id],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_ticket_filtrable_et_affectable_par_equipe(self):
        equipe = EquipeMaintenance.objects.create(
            company=self.company, nom='Équipe Est')
        ticket_avec = Ticket.objects.create(
            company=self.company, reference='SAV-ZMFG1-1',
            client=self.client_obj, installation=self.inst,
            equipe=equipe, created_by=self.admin)
        Ticket.objects.create(
            company=self.company, reference='SAV-ZMFG1-2',
            client=self.client_obj, installation=self.inst,
            created_by=self.admin)

        r = self.api.get(
            '/api/django/sav/tickets/', {'equipe': equipe.id, 'ouvert': 'tous'})
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        ids = [row['id'] for row in rows]
        self.assertEqual(ids, [ticket_avec.id])

    def test_ticket_equipe_autre_societe_rejetee(self):
        equipe_etrangere = EquipeMaintenance.objects.create(
            company=self.other_company, nom='Équipe Étrangère')
        r = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'equipe': equipe_etrangere.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_company_isolation(self):
        EquipeMaintenance.objects.create(
            company=self.other_company, nom='Équipe Étrangère 2')
        r = self.api.get('/api/django/sav/equipes-maintenance/')
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        noms = [row['nom'] for row in rows]
        self.assertNotIn('Équipe Étrangère 2', noms)
