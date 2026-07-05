"""YSERV2 — Handoff ticket SAV <-> intervention.

Couvre :
  * un clic crée l'intervention liée (chantier du ticket, technicien) et
    planifie le ticket (NOUVEAU -> PLANIFIE) ;
  * refus propre (400) si le ticket n'a pas de chantier lié ;
  * terminer l'intervention avance le ticket vers RESOLU avec trace, sans
    jamais reculer un statut déjà clos ;
  * clôturer un ticket à intervention ouverte est refusé (400) ;
  * ré-émission du signal = aucun double effet (idempotent).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_yserv2 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import Ticket, TicketActivity

User = get_user_model()


def make_company(slug='sav-yserv2', nom='Sav Co YSERV2'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class YSERV2HandoffTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='yserv2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSERV2',
            email='yserv2-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-YSERV2', client=self.client_obj)

    def _ticket(self, ref='SAV-YSERV2-1', installation=None, statut=Ticket.Statut.NOUVEAU):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=installation, statut=statut, created_by=self.admin)

    def test_planifier_intervention_un_clic(self):
        ticket = self._ticket(installation=self.inst)
        api = auth(self.admin)
        resp = api.post(f'/api/django/sav/tickets/{ticket.pk}/planifier-intervention/')
        self.assertEqual(resp.status_code, 201, resp.data)
        interv = Intervention.objects.get(pk=resp.data['intervention_id'])
        self.assertEqual(interv.installation_id, self.inst.id)
        self.assertEqual(interv.ticket_id, ticket.id)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.PLANIFIE)

    def test_planifier_intervention_sans_chantier_refuse(self):
        ticket = self._ticket(installation=None)
        api = auth(self.admin)
        resp = api.post(f'/api/django/sav/tickets/{ticket.pk}/planifier-intervention/')
        self.assertEqual(resp.status_code, 400)

    def test_terminer_intervention_avance_ticket_resolu(self):
        ticket = self._ticket(installation=self.inst, statut=Ticket.Statut.EN_COURS)
        # F5 (installations) bloque désormais toute progression au-delà de
        # « À préparer » (défaut du modèle) sans confirmation « Tout est
        # chargé » — hors périmètre de ce test (handoff SAV<->intervention).
        # On démarre l'intervention à « Sur site », déjà au-delà de la garde.
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.admin)
        api = auth(self.admin)
        resp = api.patch(f'/api/django/installations/interventions/{interv.pk}/', {
            'statut': 'terminee',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.RESOLU)
        self.assertIsNotNone(ticket.date_resolution)
        notes = TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE)
        self.assertTrue(any('automatiquement' in (n.body or '') for n in notes))

    def test_ne_recule_jamais_un_statut_deja_clos(self):
        ticket = self._ticket(installation=self.inst, statut=Ticket.Statut.CLOTURE)
        # F5 (installations) : démarre au-delà de « À préparer » — voir
        # commentaire de test_terminer_intervention_avance_ticket_resolu.
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.admin)
        api = auth(self.admin)
        resp = api.patch(f'/api/django/installations/interventions/{interv.pk}/', {
            'statut': 'terminee',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.CLOTURE)

    def test_cloture_refusee_intervention_ouverte(self):
        # YDOCF1 — la clôture passe par l'action guardée `cloturer`.
        ticket = self._ticket(installation=self.inst, statut=Ticket.Statut.EN_COURS)
        Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE, created_by=self.admin)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{ticket.pk}/cloturer/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('interventions_ouvertes', resp.data)

    def test_cloture_autorisee_intervention_terminee(self):
        ticket = self._ticket(installation=self.inst, statut=Ticket.Statut.RESOLU)
        Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.VALIDEE, created_by=self.admin)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{ticket.pk}/cloturer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_reemission_signal_aucun_double_effet(self):
        """Idempotence : re-déclencher intervention_completed (ex. re-save du
        même statut TERMINEE) ne produit aucune seconde note ni double
        incrément visible."""
        ticket = self._ticket(installation=self.inst, statut=Ticket.Statut.EN_COURS)
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE, created_by=self.admin)
        from core.events import intervention_completed
        intervention_completed.send(
            sender=Intervention, intervention=interv, company=self.company,
            user=self.admin)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.RESOLU)
        premiere_date = ticket.date_resolution
        notes_avant = TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE).count()
        # Deuxième émission : le ticket est déjà RESOLU (hors OPEN_STATUTS),
        # le récepteur ne doit plus rien faire.
        intervention_completed.send(
            sender=Intervention, intervention=interv, company=self.company,
            user=self.admin)
        ticket.refresh_from_db()
        self.assertEqual(ticket.date_resolution, premiere_date)
        notes_apres = TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE).count()
        self.assertEqual(notes_avant, notes_apres)
