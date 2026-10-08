"""ASAV13 — le statut d'une réponse type passe par la machine d'états.

Une macro ne peut plus sauter le graphe : ``noter`` applique son
``nouveau_statut`` par ``appliquer_transition_ticket`` (refus 400 sans note
ni statut), et ``nouveau_statut`` est limité aux choix de ``Ticket.Statut``.

Run :
    python manage.py test apps.sav.tests_asav13_macro_transition -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import ReponseType, Ticket, TicketActivity
from core.events import ticket_resolu

User = get_user_model()


class MacroTransitionTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav13-co', defaults={'nom': 'ASAV13 Co'})
        self.admin = User.objects.create_user(
            username='asav13_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV13')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV13',
            client=self.client_obj)
        self.macros = {
            statut: ReponseType.objects.create(
                company=self.company, titre=f'Macro {statut}',
                corps=f'Passage {statut}.', nouveau_statut=statut)
            for statut in ('cloture', 'resolu', 'nouveau')
        }

    def _ticket(self, ref, statut):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=self.inst, type=Ticket.Type.CORRECTIF,
            statut=statut, created_by=self.admin)

    def _noter(self, ticket, statut_macro):
        return self.api.post(
            f'/api/django/sav/tickets/{ticket.pk}/noter/',
            {'reponse_type_id': self.macros[statut_macro].pk}, format='json')

    def _notes(self, ticket):
        return TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE).count()

    def test_saut_refuse(self):
        t = self._ticket('SAV-ASAV13-1', Ticket.Statut.NOUVEAU)
        notes = self._notes(t)
        r = self._noter(t, 'cloture')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('Transition de statut interdite', str(r.data))
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.NOUVEAU)
        self.assertEqual(self._notes(t), notes)

    def test_garde_interventions(self):
        t = self._ticket('SAV-ASAV13-2', Ticket.Statut.EN_COURS)
        Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=t,
            type_intervention=Intervention.Type.DEPANNAGE,
            created_by=self.admin)
        r = self._noter(t, 'cloture')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('interventions_ouvertes', r.data)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.EN_COURS)

    def test_resolu_effets_complets(self):
        t = self._ticket('SAV-ASAV13-3', Ticket.Statut.EN_COURS)
        Ticket.objects.filter(pk=t.pk).update(
            sla_due_at=timezone.localdate() - timedelta(days=2),
            sla_breach=True)
        recus = []

        def _recu(sender, ticket=None, **kw):
            recus.append(ticket.pk)
        ticket_resolu.connect(_recu, weak=False)
        try:
            r = self._noter(t, 'resolu')
        finally:
            ticket_resolu.disconnect(_recu)
        self.assertEqual(r.status_code, 201, r.content)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.RESOLU)
        self.assertFalse(t.sla_breach)
        self.assertTrue(t.canal_resolution)
        self.assertEqual(recus, [t.pk])

    def test_reouverture_comptee(self):
        t = self._ticket('SAV-ASAV13-4', Ticket.Statut.CLOTURE)
        r = self._noter(t, 'nouveau')
        self.assertEqual(r.status_code, 201, r.content)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.NOUVEAU)
        self.assertEqual(t.reopen_count, 1)

    def test_statut_invalide_400(self):
        r = self.api.post(
            '/api/django/sav/reponses-type/',
            {'titre': 'Bidon', 'corps': 'x', 'nouveau_statut': 'bidon'},
            format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('nouveau_statut', r.data)
        self.assertFalse(ReponseType.objects.filter(
            nouveau_statut='bidon').exists())
