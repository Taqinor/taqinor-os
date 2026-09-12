"""NTSRV27 — Rapport de charge et performance par agent.

Critère d'acceptation : un agent avec 0 ticket sur la période n'apparaît PAS
en division par zéro (garde) — et chaque moyenne vaut ``None``, jamais 0,
quand son dénominateur est vide.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv27 -v 2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket, TicketSatisfaction
from apps.sav.selectors import performance_agent

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV27PerformanceAgentTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv27', defaults={'nom': 'Sav Co NTSRV27'})
        self.admin = User.objects.create_user(
            username='ntsrv27_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.amine = User.objects.create_user(
            username='amine', password='x', role_legacy='normal',
            company=self.company)
        self.zineb = User.objects.create_user(
            username='zineb', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV27')
        self.compteur = 0

    def _ticket(self, agent=None, resolution=None, sla_due=None,
                statut=Ticket.Statut.CLOTURE):
        self.compteur += 1
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-NTSRV27-{self.compteur}',
            client=self.client_obj, statut=statut,
            technicien_responsable=agent,
            date_resolution=resolution, sla_due_at=sla_due)

    def _agent(self, data, nom):
        return next(a for a in data['agents'] if a['agent_nom'] == nom)

    # ── Critère d'acceptation : garde division par zéro ──────────────────
    def test_agent_sans_ticket_n_apparait_pas(self):
        self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        data = performance_agent(self.company)
        self.assertEqual([a['agent_nom'] for a in data['agents']], ['amine'])

    def test_aucun_ticket_du_tout_ne_leve_rien(self):
        data = performance_agent(self.company)
        self.assertEqual(data['agents'], [])
        self.assertEqual(data['nb_tickets_traites'], 0)

    def test_sans_csat_la_moyenne_est_none_pas_zero(self):
        self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        agent = self._agent(performance_agent(self.company), 'amine')
        self.assertIsNone(agent['csat_moyen'])
        self.assertEqual(agent['nb_csat'], 0)

    def test_sans_echeance_sla_le_taux_est_none_pas_zero(self):
        self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        agent = self._agent(performance_agent(self.company), 'amine')
        self.assertIsNone(agent['taux_respect_sla'])
        self.assertEqual(agent['nb_tickets_avec_sla'], 0)

    # ── Agrégats ─────────────────────────────────────────────────────────
    def test_nb_tickets_traites_par_agent(self):
        self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        self._ticket(agent=self.amine, resolution=date(2026, 3, 11))
        self._ticket(agent=self.zineb, resolution=date(2026, 3, 12))
        data = performance_agent(self.company)
        self.assertEqual(self._agent(data, 'amine')['nb_tickets_traites'], 2)
        self.assertEqual(self._agent(data, 'zineb')['nb_tickets_traites'], 1)
        self.assertEqual(data['nb_tickets_traites'], 3)

    def test_ticket_sans_technicien_dans_le_seau_non_assigne(self):
        self._ticket(agent=None, resolution=date(2026, 3, 10))
        data = performance_agent(self.company)
        self.assertEqual(
            self._agent(data, 'Non assigné')['nb_tickets_traites'], 1)

    def test_csat_moyen_recu(self):
        premier = self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        second = self._ticket(agent=self.amine, resolution=date(2026, 3, 11))
        TicketSatisfaction.objects.create(
            company=self.company, ticket=premier, note=5)
        TicketSatisfaction.objects.create(
            company=self.company, ticket=second, note=3)
        agent = self._agent(performance_agent(self.company), 'amine')
        self.assertEqual(agent['csat_moyen'], 4.0)
        self.assertEqual(agent['nb_csat'], 2)

    def test_taux_respect_sla(self):
        self._ticket(agent=self.amine, resolution=date(2026, 3, 10),
                     sla_due=date(2026, 3, 12))
        self._ticket(agent=self.amine, resolution=date(2026, 3, 20),
                     sla_due=date(2026, 3, 12))
        agent = self._agent(performance_agent(self.company), 'amine')
        self.assertEqual(agent['nb_tickets_avec_sla'], 2)
        self.assertEqual(agent['taux_respect_sla'], 50.0)

    def test_delai_moyen_de_resolution(self):
        ticket = self._ticket(agent=self.amine)
        # Même conversion que le sélecteur (heure LOCALE) : sinon le test
        # bascule d'un jour selon l'heure d'exécution.
        ouverture = timezone.localtime(ticket.date_creation).date()
        ticket.date_resolution = ouverture + timedelta(days=4)
        ticket.save(update_fields=['date_resolution'])
        agent = self._agent(performance_agent(self.company), 'amine')
        self.assertEqual(agent['delai_resolution_moyen_jours'], 4.0)

    # ── Périmètre ────────────────────────────────────────────────────────
    def test_ticket_ouvert_non_compte(self):
        self._ticket(agent=self.amine, statut=Ticket.Statut.EN_COURS)
        self.assertEqual(performance_agent(self.company)['agents'], [])

    def test_ticket_annule_non_compte(self):
        ticket = self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        ticket.annule = True
        ticket.save(update_fields=['annule'])
        self.assertEqual(performance_agent(self.company)['agents'], [])

    def test_hors_periode_exclu(self):
        self._ticket(agent=self.amine, resolution=date(2026, 1, 5))
        self._ticket(agent=self.zineb, resolution=date(2026, 3, 10))
        data = performance_agent(
            self.company, date_debut=date(2026, 3, 1),
            date_fin=date(2026, 3, 31))
        self.assertEqual([a['agent_nom'] for a in data['agents']], ['zineb'])

    def test_autre_societe_jamais_melangee(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv27-b', defaults={'nom': 'Autre NTSRV27'})
        self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        self.assertEqual(performance_agent(autre)['agents'], [])

    # ── Jamais un classement ─────────────────────────────────────────────
    def test_tri_alphabetique_jamais_par_volume(self):
        self._ticket(agent=self.zineb, resolution=date(2026, 3, 10))
        self._ticket(agent=self.zineb, resolution=date(2026, 3, 11))
        self._ticket(agent=self.zineb, resolution=date(2026, 3, 12))
        self._ticket(agent=self.amine, resolution=date(2026, 3, 13))
        data = performance_agent(self.company)
        self.assertEqual([a['agent_nom'] for a in data['agents']],
                         ['amine', 'zineb'])

    # ── Endpoint ─────────────────────────────────────────────────────────
    def test_endpoint_json(self):
        self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        resp = self.api.get(
            '/api/django/sav/insights/sav-performance-agent/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['agents'][0]['agent_nom'], 'amine')

    def test_endpoint_export_xlsx(self):
        self._ticket(agent=self.amine, resolution=date(2026, 3, 10))
        resp = self.api.get(
            '/api/django/sav/insights/sav-performance-agent/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])

    def test_endpoint_refuse_au_role_normal(self):
        resp = auth(self.amine).get(
            '/api/django/sav/insights/sav-performance-agent/')
        self.assertEqual(resp.status_code, 403)

    def test_endpoint_date_invalide_nomme_le_champ(self):
        resp = self.api.get(
            '/api/django/sav/insights/sav-performance-agent/?date_fin=demain')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('date_fin', resp.json())
