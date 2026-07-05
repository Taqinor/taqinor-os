"""ZMFG4 — Tableau de bord maintenance découpé par équipe/statut.

Couvre :
  * les compteurs par équipe (ouverts / en retard SLA / préventifs dus /
    correctifs urgents) sont exacts sur fixtures ;
  * les tickets sans équipe sont regroupés séparément ;
  * l'endpoint est réservé au tier responsable/admin.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg4 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import EquipeMaintenance, Ticket
from apps.sav.selectors import resume_par_equipe

User = get_user_model()


def make_company(slug='sav-zmfg4', nom='Sav Co ZMFG4'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZMFG4ResumeParEquipeTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zmfg4_admin', password='x', role_legacy='admin',
            company=self.company)
        self.viewer = User.objects.create_user(
            username='zmfg4_viewer', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG4',
            email='zmfg4-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZMFG4', client=self.client_obj)
        self.equipe = EquipeMaintenance.objects.create(
            company=self.company, nom='Équipe Nord')

    def _ticket(self, **kwargs):
        defaults = dict(
            company=self.company, client=self.client_obj,
            installation=self.inst, created_by=self.admin,
            reference=f'SAV-ZMFG4-{Ticket.objects.count()}')
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def test_compteurs_exacts_par_equipe(self):
        self._ticket(equipe=self.equipe, sla_breach=True)
        self._ticket(equipe=self.equipe, type=Ticket.Type.PREVENTIF)
        self._ticket(
            equipe=self.equipe, type=Ticket.Type.CORRECTIF,
            priorite=Ticket.Priorite.URGENTE)
        self._ticket()  # sans équipe

        rows = resume_par_equipe(self.company)
        by_id = {r['equipe_id']: r for r in rows}
        row = by_id[self.equipe.id]
        self.assertEqual(row['ouverts'], 3)
        self.assertEqual(row['en_retard_sla'], 1)
        self.assertEqual(row['preventifs_dus'], 1)
        self.assertEqual(row['correctifs_urgents'], 1)

        sans_equipe = by_id[None]
        self.assertEqual(sans_equipe['ouverts'], 1)

    def test_ticket_clos_exclu_du_compteur(self):
        t = self._ticket(equipe=self.equipe, statut=Ticket.Statut.CLOTURE)
        rows = resume_par_equipe(self.company)
        row = next(r for r in rows if r['equipe_id'] == self.equipe.id)
        self.assertEqual(row['ouverts'], 0)
        self.assertIsNotNone(t.id)  # ticket existe bien, juste exclu du compte

    def test_endpoint_reserve_responsable_admin(self):
        r_viewer = auth(self.viewer).get(
            '/api/django/sav/insights/sav-resume-equipe/')
        self.assertEqual(r_viewer.status_code, 403, r_viewer.data)

        r_admin = auth(self.admin).get(
            '/api/django/sav/insights/sav-resume-equipe/')
        self.assertEqual(r_admin.status_code, 200, r_admin.data)

    def test_isolation_multitenant(self):
        other_company = make_company(slug='sav-zmfg4-other', nom='Other')
        EquipeMaintenance.objects.create(company=other_company, nom='Autre')
        rows = resume_par_equipe(self.company)
        noms = [r['equipe_nom'] for r in rows]
        self.assertNotIn('Autre', noms)
