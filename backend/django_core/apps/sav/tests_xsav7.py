"""XSAV7 — SLA différencié par contrat / segment client.

Couvre :
  * client sous contrat actif avec override → ticket hérite du SLA contrat ;
  * client sans contrat (ou contrat sans override) → comportement actuel
    (sla_par_priorite puis défauts société) ;
  * précédence : contrat actif > sla_par_priorite > défauts société ;
  * migration additive (NULL = pas de override, aucun changement).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav7 -v 2
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import ContratMaintenance, SavSlaSettings

User = get_user_model()


def make_company(slug='sav-xsav7', nom='Sav Co XSAV7'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV7ContratSlaOverrideTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsav7_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_premium = Client.objects.create(
            company=self.company, nom='Premium', prenom='Client',
            email='xsav7-premium@example.invalid')
        self.client_standard = Client.objects.create(
            company=self.company, nom='Standard', prenom='Client',
            email='xsav7-standard@example.invalid')
        self.inst_premium = Installation.objects.create(
            company=self.company, reference='CHT-XSAV7-P', client=self.client_premium)
        self.inst_standard = Installation.objects.create(
            company=self.company, reference='CHT-XSAV7-S', client=self.client_standard)

        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_resolution_days = 7
        sla.save(update_fields=['sla_breach_enabled', 'sla_resolution_days'])

    def test_client_sous_contrat_override_herite_sla_contrat(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_premium,
            periodicite='annuel', date_debut=date(2024, 1, 1),
            actif=True, sla_resolution_days=1)

        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_premium.id, 'installation': self.inst_premium.id,
            'date_ouverture': '2024-06-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        # 2024-06-10 + 1 jour (override contrat, pas les 7 j société).
        self.assertEqual(resp.data['sla_due_at'], '2024-06-11')

    def test_client_sans_contrat_comportement_actuel(self):
        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_standard.id, 'installation': self.inst_standard.id,
            'date_ouverture': '2024-06-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        # 2024-06-10 + 7 jours société (aucun contrat).
        self.assertEqual(resp.data['sla_due_at'], '2024-06-17')

    def test_contrat_sans_override_retombe_sur_societe(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_standard,
            periodicite='annuel', date_debut=date(2024, 1, 1),
            actif=True)  # aucun override SLA posé.

        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_standard.id, 'installation': self.inst_standard.id,
            'date_ouverture': '2024-06-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['sla_due_at'], '2024-06-17')

    def test_contrat_inactif_ignore(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_premium,
            periodicite='annuel', date_debut=date(2024, 1, 1),
            actif=False, sla_resolution_days=1)

        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_premium.id, 'installation': self.inst_premium.id,
            'date_ouverture': '2024-06-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['sla_due_at'], '2024-06-17')

    def test_precedence_contrat_avant_priorite(self):
        sla = SavSlaSettings.get(self.company)
        sla.sla_par_priorite = {'urgente': {'resolution': 2}}
        sla.save(update_fields=['sla_par_priorite'])
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_premium,
            periodicite='annuel', date_debut=date(2024, 1, 1),
            actif=True, sla_resolution_days=1)

        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_premium.id, 'installation': self.inst_premium.id,
            'date_ouverture': '2024-06-10', 'priorite': 'urgente',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        # Contrat (1 j) l'emporte sur sla_par_priorite urgente (2 j).
        self.assertEqual(resp.data['sla_due_at'], '2024-06-11')

    def test_actif_pour_client_prend_le_plus_recent(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_premium,
            periodicite='annuel', date_debut=date(2023, 1, 1),
            actif=True, sla_resolution_days=5)
        recent = ContratMaintenance.objects.create(
            company=self.company, client=self.client_premium,
            periodicite='annuel', date_debut=date(2024, 1, 1),
            actif=True, sla_resolution_days=2)
        found = ContratMaintenance.actif_pour_client(self.client_premium)
        self.assertEqual(found.id, recent.id)

    def test_migration_additive_null_par_defaut(self):
        c = ContratMaintenance.objects.create(
            company=self.company, client=self.client_standard,
            periodicite='annuel', date_debut=date(2024, 1, 1), actif=True)
        self.assertIsNone(c.sla_response_days)
        self.assertIsNone(c.sla_resolution_days)
