"""YSERV12 — Canal de résolution (à distance / sur site) + taux d'évitement.

Couvre :
  * proposition automatique correcte (sur_site si intervention terminée liée
    existe, sinon à_distance) à la transition RESOLU ;
  * jamais requis rétroactivement (anciens tickets NULL tolérés) ;
  * jamais écrasé si posé explicitement ;
  * KPI taux_resolution_a_distance exact sur fixtures (global + par
    technicien), aucune division par zéro.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_yserv12 -v 2
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import Ticket
from apps.sav.selectors import taux_resolution_a_distance

User = get_user_model()


def make_company(slug='sav-yserv12', nom='Sav Co YSERV12'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class YSERV12CanalResolutionTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='yserv12_admin', password='x', role_legacy='admin',
            company=self.company)
        self.tech = User.objects.create_user(
            username='yserv12_tech', password='x', role_legacy='employe',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSERV12',
            email='yserv12-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-YSERV12', client=self.client_obj)

    def _ticket(self, ref, statut=Ticket.Statut.EN_COURS, technicien=None):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=self.inst, statut=statut,
            technicien_responsable=technicien, created_by=self.admin)

    def test_proposition_a_distance_sans_intervention(self):
        ticket = self._ticket('SAV-YSERV12-1')
        self.assertEqual(
            ticket.canal_resolution_propose(), Ticket.CanalResolution.A_DISTANCE)

    def test_proposition_sur_site_avec_intervention_terminee(self):
        ticket = self._ticket('SAV-YSERV12-2')
        Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.TERMINEE, created_by=self.admin)
        self.assertEqual(
            ticket.canal_resolution_propose(), Ticket.CanalResolution.SUR_SITE)

    def test_transition_resolu_applique_proposition(self):
        # YDOCF1 — la transition passe par l'action guardée `resoudre`.
        ticket = self._ticket('SAV-YSERV12-3')
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{ticket.pk}/resoudre/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ticket.refresh_from_db()
        self.assertEqual(
            ticket.canal_resolution, Ticket.CanalResolution.A_DISTANCE)

    def test_jamais_ecrase_si_pose_explicitement(self):
        ticket = self._ticket('SAV-YSERV12-4')
        api = auth(self.admin)
        resp = api.post(f'/api/django/sav/tickets/{ticket.pk}/resoudre/', {
            'canal_resolution': 'sur_site',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.canal_resolution, Ticket.CanalResolution.SUR_SITE)

    def test_ancien_ticket_null_tolere(self):
        ticket = self._ticket('SAV-YSERV12-5', statut=Ticket.Statut.RESOLU)
        self.assertIsNone(ticket.canal_resolution)

    def test_kpi_exact_sur_fixtures(self):
        t1 = self._ticket(
            'SAV-YSERV12-K1', statut=Ticket.Statut.RESOLU, technicien=self.tech)
        t1.canal_resolution = Ticket.CanalResolution.A_DISTANCE
        t1.date_resolution = date(2026, 3, 1)
        t1.save(update_fields=['canal_resolution', 'date_resolution'])
        t2 = self._ticket(
            'SAV-YSERV12-K2', statut=Ticket.Statut.CLOTURE, technicien=self.tech)
        t2.canal_resolution = Ticket.CanalResolution.SUR_SITE
        t2.date_resolution = date(2026, 3, 2)
        t2.save(update_fields=['canal_resolution', 'date_resolution'])
        # Ticket sans canal renseigné (ancien) : exclu du dénominateur.
        self._ticket('SAV-YSERV12-K3', statut=Ticket.Statut.RESOLU)

        result = taux_resolution_a_distance(
            self.company, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), group_by_technicien=True)
        self.assertEqual(result['global']['resolus'], 2)
        self.assertEqual(result['global']['a_distance'], 1)
        self.assertEqual(result['global']['taux_pct'], 50.0)

    def test_kpi_aucune_division_par_zero(self):
        result = taux_resolution_a_distance(self.company)
        self.assertEqual(result['global']['resolus'], 0)
        self.assertIsNone(result['global']['taux_pct'])
