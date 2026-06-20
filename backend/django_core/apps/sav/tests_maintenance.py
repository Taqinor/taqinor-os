"""T16 — contrats de maintenance : prochaine visite / dû calculés à la lecture,
génération idempotente de tickets SAV préventifs (sans planificateur)."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.sav.models import ContratMaintenance, Ticket
from authentication.models import Company

User = get_user_model()


class TestMaintenance(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cm-co', defaults={'nom': 'CM Co'})[0]
        self.user = User.objects.create_user(
            username='cm_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company, nom='C')

    def test_prochaine_visite_and_due(self):
        c = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today() - timedelta(days=400))
        self.assertTrue(c.is_due())  # début il y a >1 an
        future = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today())
        self.assertFalse(future.is_due())

    def test_generer_dus_creates_ticket_once(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='mensuel',
            date_debut=date.today() - timedelta(days=40))
        r1 = self.api.post('/api/django/sav/contrats-maintenance/generer-dus/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['tickets_generes'], 1)
        self.assertEqual(Ticket.objects.filter(
            company=self.company, type='preventif').count(), 1)
        # Re-générer juste après n'en recrée pas (visite avancée).
        r2 = self.api.post('/api/django/sav/contrats-maintenance/generer-dus/')
        self.assertEqual(r2.data['tickets_generes'], 0)

    def test_due_filter(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today() - timedelta(days=400))
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today())
        resp = self.api.get('/api/django/sav/contrats-maintenance/?due=1')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 1)

    def test_cannot_bind_foreign_client(self):
        # ERR9 — un contrat ne peut pas lier le client d'une AUTRE société.
        other = Company.objects.get_or_create(
            slug='cm-other', defaults={'nom': 'Other'})[0]
        foreign_client = Client.objects.create(company=other, nom='Étranger')
        r = self.api.post('/api/django/sav/contrats-maintenance/', {
            'client': foreign_client.id, 'periodicite': 'annuel',
            'date_debut': date.today().isoformat()}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('client', r.data)
        self.assertFalse(ContratMaintenance.objects.filter(
            client=foreign_client).exists())

    def test_cannot_bind_foreign_installation(self):
        # ERR9 — ni le chantier d'une autre société.
        from apps.installations.models import Installation
        other = Company.objects.get_or_create(
            slug='cm-other2', defaults={'nom': 'Other2'})[0]
        other_client = Client.objects.create(company=other, nom='B')
        foreign_inst = Installation.objects.create(
            company=other, reference='CHT-X', client=other_client)
        r = self.api.post('/api/django/sav/contrats-maintenance/', {
            'client': self.client_obj.id, 'installation': foreign_inst.id,
            'periodicite': 'annuel', 'date_debut': date.today().isoformat()},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('installation', r.data)
