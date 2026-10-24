"""ASAV5 — les droits d'un contrat de maintenance se comptent sur les tickets
ANTÉRIEURS non annulés (le ticket évalué n'en consomme pas), rattachés par
chantier ou, sans chantier, par client : un quota de N couvre exactement les N
premiers tickets.

Run :
    python manage.py test apps.sav.tests_asav5_quotas_contrat -v2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import ContratMaintenance, Ticket, TicketActivity
from apps.sav.droits_contrat import droits_restants

User = get_user_model()
ANNEE = 2026


class QuotasContratTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav5-co', defaults={'nom': 'ASAV5 Co'})
        self.user = User.objects.create_user(
            username='asav5_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV5')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV5',
            client=self.client_obj)

    def _contrat(self, quota, *, chantier=True):
        return ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst if chantier else None,
            date_debut=date(ANNEE, 1, 1), actif=True,
            deplacements_inclus_an=quota)

    def _ticket(self, n, mois, **kw):
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-A5-{n}',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.user,
            date_ouverture=date(ANNEE, mois, 10), **kw)

    def test_quota_1_premier_couvert(self):
        self._contrat(1)
        t1, t2 = self._ticket(1, 2), self._ticket(2, 3)
        self.assertEqual(t1.couverture_calculee(), Ticket.Couverture.CONTRAT)
        self.assertEqual(
            t2.couverture_calculee(), Ticket.Couverture.FACTURABLE)

    def test_annule_ne_consomme_pas(self):
        self._contrat(2)
        t1 = self._ticket(1, 2)
        self._ticket(2, 3, annule=True)
        t3 = self._ticket(3, 4)
        self.assertEqual(t1.couverture_calculee(), Ticket.Couverture.CONTRAT)
        self.assertEqual(t3.couverture_calculee(), Ticket.Couverture.CONTRAT)

    def test_quota_n_couvre_n(self):
        self._contrat(3)
        tickets = [self._ticket(i, i) for i in range(1, 6)]
        self.assertEqual(
            [t.couverture_calculee() for t in tickets],
            [Ticket.Couverture.CONTRAT] * 3
            + [Ticket.Couverture.FACTURABLE] * 2)

    def test_contrat_client_sans_chantier(self):
        contrat = self._contrat(1, chantier=False)
        t1, t2, t3 = (self._ticket(i, i + 1) for i in range(1, 4))
        self.assertEqual(t1.couverture_calculee(), Ticket.Couverture.CONTRAT)
        self.assertEqual(
            t2.couverture_calculee(), Ticket.Couverture.FACTURABLE)
        self.assertEqual(
            t3.couverture_calculee(), Ticket.Couverture.FACTURABLE)
        # Écran des contrats (sans ticket) : compteur de l'année, 3 tickets.
        droits = droits_restants(contrat, ANNEE)
        self.assertEqual(droits['deplacements_consommes'], 3)
        self.assertEqual(droits['deplacements_restants'], 0)

    # ── ASAV108 — avertissements de création jugés à la date du ticket ──────
    def _poster_correctif(self, description, date_ouverture):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.pk, 'installation': self.inst.pk,
            'type': 'correctif', 'description': description,
            'date_ouverture': date_ouverture.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['id']

    def _notes_quota(self, ticket_id):
        return [
            n.body for n in TicketActivity.objects.filter(
                ticket_id=ticket_id, kind=TicketActivity.Kind.NOTE)
            if 'quota' in (n.body or '').lower()]

    def test_creation_premier_ticket_sans_note_quota(self):
        aujourdhui = timezone.localdate()
        contrat = self._contrat(1)
        contrat.date_debut = aujourdhui - timedelta(days=30)
        contrat.save(update_fields=['date_debut'])
        premier = self._poster_correctif('Premier déplacement', aujourdhui)
        second = self._poster_correctif('Second déplacement', aujourdhui)
        # Le 1er ticket couvert d'un quota 1 ne se compte pas lui-même.
        self.assertEqual(self._notes_quota(premier), [])
        # Le 2e dépasse le quota : la note nomme le contrat et l'année.
        notes = self._notes_quota(second)
        self.assertEqual(len(notes), 1)
        self.assertIn('déjà atteint', notes[0])
        self.assertIn(f'#{contrat.pk}', notes[0])

    def test_creation_ticket_anterieur_au_contrat_sans_note(self):
        aujourdhui = timezone.localdate()
        contrat = self._contrat(1)
        contrat.date_debut = aujourdhui
        contrat.save(update_fields=['date_debut'])
        ticket_id = self._poster_correctif(
            'Déplacement avant le contrat', aujourdhui - timedelta(days=60))
        # Contrat non encore débuté à la date du ticket : aucune note sur lui.
        notes = [
            n.body for n in TicketActivity.objects.filter(
                ticket_id=ticket_id, kind=TicketActivity.Kind.NOTE)
            if f'#{contrat.pk}' in (n.body or '')]
        self.assertEqual(notes, [])
