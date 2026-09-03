"""AUD514 — Ticket.statut n'est plus écrit HORS de la machine d'états.

Constat d'audit (le ROUGE figé ici) :

  * ``TicketViewSet.planifier_intervention`` posait ``ticket.statut =
    PLANIFIE`` en écriture DIRECTE, sans passer par ``machine_etats`` ;
  * le récepteur ``intervention_completed`` écrivait ``statut = RESOLU`` en
    direct pour tout ticket encore OUVERT — alors que le graphe gardé
    n'autorise RESOLU QUE depuis EN_COURS. Un ticket jamais planifié sautait
    donc silencieusement NOUVEAU → RESOLU, saut que l'écran SAV refuse
    (``TransitionInterdite``) : deux vérités contradictoires pour la même
    transition.

Correctif : les deux écritures passent par ``machine_etats.changer_statut``.
Le saut automatique NOUVEAU/PLANIFIE → RESOLU est DÉCLARÉ (transitions
« système », jamais offertes à un humain) et tracé au chatter — plus jamais
silencieux.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_aud514 -v 2
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav import machine_etats
from apps.sav.models import Ticket, TicketActivity

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AUD514TransitionsGardeesTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-aud514', defaults={'nom': 'Sav Co AUD514'})
        self.admin = User.objects.create_user(
            username='aud514_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD514',
            email='aud514-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-AUD514',
            client=self.client_obj)

    def _ticket(self, ref, statut=Ticket.Statut.NOUVEAU):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=self.inst, statut=statut, created_by=self.admin)

    # ── Le graphe HUMAIN reste inchangé : le saut est toujours refusé ───────

    def test_saut_nouveau_resolu_reste_interdit_au_chemin_humain(self):
        self.assertFalse(
            machine_etats.transition_permise(
                Ticket.Statut.NOUVEAU, Ticket.Statut.RESOLU))
        ticket = self._ticket('SAV-AUD514-1')
        self.assertNotIn(
            Ticket.Statut.RESOLU, machine_etats.statuts_suivants(ticket))
        resp = auth(self.admin).post(
            f'/api/django/sav/tickets/{ticket.pk}/resoudre/', {},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.NOUVEAU)

    def test_transition_systeme_declaree_explicitement(self):
        """Le saut automatique existe, mais DÉCLARÉ (``systeme=True``)."""
        self.assertTrue(
            machine_etats.transition_permise(
                Ticket.Statut.NOUVEAU, Ticket.Statut.RESOLU, systeme=True))
        self.assertTrue(
            machine_etats.transition_permise(
                Ticket.Statut.PLANIFIE, Ticket.Statut.RESOLU, systeme=True))
        # Une transition hors des deux graphes reste refusée même en système.
        self.assertFalse(
            machine_etats.transition_permise(
                Ticket.Statut.NOUVEAU, Ticket.Statut.CLOTURE, systeme=True))
        with self.assertRaises(machine_etats.TransitionInterdite):
            machine_etats.changer_statut(
                self._ticket('SAV-AUD514-2'), Ticket.Statut.CLOTURE,
                persister=False, systeme=True)

    # ── Le récepteur passe par la machine, et la trace n'est pas silencieuse ─

    def test_intervention_terminee_sur_ticket_nouveau_passe_par_la_machine(self):
        ticket = self._ticket('SAV-AUD514-3')
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.admin)
        from core.events import intervention_completed
        reel = machine_etats.changer_statut
        with patch('apps.sav.machine_etats.changer_statut',
                   side_effect=reel) as espion:
            intervention_completed.send(
                sender=Intervention, intervention=interv,
                company=self.company, user=self.admin)
        self.assertTrue(espion.called, 'écriture directe du statut détectée')
        _, kwargs = espion.call_args
        self.assertTrue(kwargs.get('systeme'))
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.RESOLU)

    def test_saut_systeme_trace_au_chatter(self):
        ticket = self._ticket('SAV-AUD514-4')
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.admin)
        from core.events import intervention_completed
        intervention_completed.send(
            sender=Intervention, intervention=interv, company=self.company,
            user=self.admin)
        notes = TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE)
        self.assertTrue(
            any('Transition système' in (n.body or '') for n in notes),
            'le saut automatique doit être tracé, jamais silencieux')

    def test_depuis_en_cours_pas_de_mention_systeme(self):
        """Non-régression YSERV2 : le chemin normal EN_COURS → RESOLU ne
        change pas (et ne se déclare pas « système »)."""
        ticket = self._ticket('SAV-AUD514-5', statut=Ticket.Statut.EN_COURS)
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.admin)
        from core.events import intervention_completed
        intervention_completed.send(
            sender=Intervention, intervention=interv, company=self.company,
            user=self.admin)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.RESOLU)
        notes = TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE)
        self.assertFalse(
            any('Transition système' in (n.body or '') for n in notes))

    # ── planifier-intervention passe aussi par la machine ───────────────────

    def test_planifier_intervention_passe_par_la_machine(self):
        ticket = self._ticket('SAV-AUD514-6')
        reel = machine_etats.changer_statut
        with patch('apps.sav.machine_etats.changer_statut',
                   side_effect=reel) as espion:
            resp = auth(self.admin).post(
                f'/api/django/sav/tickets/{ticket.pk}/planifier-intervention/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(espion.called, 'écriture directe du statut détectée')
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.PLANIFIE)
