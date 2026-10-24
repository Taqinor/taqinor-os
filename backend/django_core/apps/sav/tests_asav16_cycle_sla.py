"""ASAV16 — le cycle SLA suit les transitions : la résolution clôt la pause
« en attente client » (l'échéance ne glisse plus), la réouverture repart de
la date de réouverture (D-ASAV-5) et remet les drapeaux d'alerte à False.

Run :
    python manage.py test apps.sav.tests_asav16_cycle_sla -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import SavSlaSettings, Ticket

User = get_user_model()
BASE = '/api/django/sav/tickets'


class CycleSlaTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav16-co', defaults={'nom': 'ASAV16 Co'})
        self.admin = User.objects.create_user(
            username='asav16_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_jours_ouvres = False
        sla.sla_resolution_days = 7
        sla.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV16')
        self.today = timezone.localdate()

    def _ticket(self, ref, **kw):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            type=Ticket.Type.CORRECTIF, priorite='normale',
            date_ouverture=self.today - timedelta(days=5),
            sla_due_at=self.today + timedelta(days=2),
            created_by=self.admin, **kw)

    def _post(self, ticket, action):
        r = self.api.post(f'{BASE}/{ticket.pk}/{action}/', {}, format='json')
        self.assertIn(r.status_code, (200, 201), (action, r.content))
        ticket.refresh_from_db()

    def test_resolution_clot_pause(self):
        t = self._ticket('SAV-A16-1', en_attente_client=True,
                         attente_depuis=self.today - timedelta(days=1))
        self._post(t, 'demarrer')
        self._post(t, 'resoudre')
        self.assertFalse(t.en_attente_client)
        self.assertIsNone(t.attente_depuis)
        self.assertEqual(t.jours_pause, 1)

    def test_echeance_figee_apres_resolution(self):
        t = self._ticket('SAV-A16-2', en_attente_client=True,
                         attente_depuis=self.today - timedelta(days=1))
        self._post(t, 'demarrer')
        self._post(t, 'resoudre')
        apres = t.sla_due_at_effectif(today=self.today)
        plus_tard = t.sla_due_at_effectif(today=self.today + timedelta(days=10))
        self.assertEqual(apres, plus_tard)

    def test_reouverture_nouvelle_echeance(self):
        t = self._ticket('SAV-A16-3')
        self._post(t, 'demarrer')
        self._post(t, 'resoudre')
        self._post(t, 'reouvrir')
        self.assertEqual(t.sla_due_at, self.today + timedelta(days=7))
        self.assertFalse(t.en_attente_client)
        self.assertEqual(t.jours_pause, 0)

    def test_drapeaux_remis_reouverture(self):
        t = self._ticket('SAV-A16-4', sla_pre_alert_notifiee=True,
                         sla_escalade_notifiee=True)
        self._post(t, 'demarrer')
        self._post(t, 'resoudre')
        self._post(t, 'reouvrir')
        self.assertFalse(t.sla_pre_alert_notifiee)
        self.assertFalse(t.sla_escalade_notifiee)

    def test_pause_compte_jours_ouvres(self):
        """Sous ``sla_jours_ouvres`` la pause compte des jours ouvrés
        (vendredi 2026-10-09 → mardi 2026-10-13 : vendredi + lundi = 2,
        pas 4 jours calendaires)."""
        from datetime import date
        sla = SavSlaSettings.get(self.company)
        sla.sla_jours_ouvres = True
        sla.save()
        t = self._ticket('SAV-A16-5', en_attente_client=True,
                         attente_depuis=date(2026, 10, 9))
        mardi = date(2026, 10, 13)
        self.assertEqual(t._pause_en_cours_jours(today=mardi), 2)
        t.reprendre_apres_attente(today=mardi)
        self.assertEqual(t.jours_pause, 2)
        sla.sla_jours_ouvres = False
        sla.save()
        t2 = self._ticket('SAV-A16-6', en_attente_client=True,
                          attente_depuis=date(2026, 10, 9))
        self.assertEqual(t2._pause_en_cours_jours(today=mardi), 4)

    # ── ASAV109 — l'annulation clôt la pause « en attente client » ──────────
    def _ticket_en_pause(self, ref, **kw):
        return self._ticket(
            ref, en_attente_client=True,
            attente_depuis=self.today - timedelta(days=3), **kw)

    def _assert_pause_close(self, ticket, contexte):
        ticket.refresh_from_db()
        self.assertFalse(ticket.en_attente_client, contexte)
        self.assertIsNone(ticket.attente_depuis, contexte)
        self.assertEqual(ticket.jours_pause, 3, contexte)
        # L'échéance effective ne glisse plus avec le temps.
        self.assertEqual(
            ticket.sla_due_at_effectif(today=self.today),
            ticket.sla_due_at_effectif(today=self.today + timedelta(days=10)),
            contexte)

    def test_annulation_clot_pause(self):
        # Annulation unitaire.
        unitaire = self._ticket_en_pause('SAV-A109-1')
        self._post(unitaire, 'annuler')
        self.assertTrue(unitaire.annule)
        self._assert_pause_close(unitaire, 'annuler')
        # Annulation en lot.
        lot = self._ticket_en_pause('SAV-A109-2')
        r = self.api.post(f'{BASE}/actions-groupees/', {
            'ids': [lot.pk], 'operation': 'annuler'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        lot.refresh_from_db()
        self.assertTrue(lot.annule)
        self._assert_pause_close(lot, 'actions-groupees')
        # Fusion : le doublon est annulé, sa pause est close.
        principal = self._ticket('SAV-A109-3')
        doublon = self._ticket_en_pause('SAV-A109-4')
        r = self.api.post(f'{BASE}/{principal.pk}/fusionner/', {
            'doublon_id': doublon.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        doublon.refresh_from_db()
        self.assertTrue(doublon.annule)
        self._assert_pause_close(doublon, 'fusionner')

    def test_reactivation_clot_pause_heritee(self):
        """Un ticket annulé resté en pause (donnée antérieure au correctif)
        voit sa pause close à la réactivation."""
        t = self._ticket_en_pause(
            'SAV-A109-5', annule=True, motif_annulation='Doublon client')
        self._post(t, 'reactiver')
        self.assertFalse(t.annule)
        self._assert_pause_close(t, 'reactiver')

    # ── ASAV110 — la mise en attente client exige un ticket ouvert non annulé
    def _poster_attente(self, ticket):
        return self.api.post(
            f'{BASE}/{ticket.pk}/attente-client/', {}, format='json')

    def test_attente_refusee_ticket_resolu(self):
        t = self._ticket('SAV-A110-1', statut=Ticket.Statut.RESOLU)
        r = self._poster_attente(t)
        self.assertEqual(r.status_code, 409, r.content)
        # Persistance : le refus n'a rien écrit.
        t.refresh_from_db()
        self.assertFalse(t.en_attente_client)
        self.assertIsNone(t.attente_depuis)

    def test_attente_refusee_ticket_annule(self):
        t = self._ticket('SAV-A110-2', annule=True)
        r = self._poster_attente(t)
        self.assertEqual(r.status_code, 409, r.content)
        t.refresh_from_db()
        self.assertFalse(t.en_attente_client)

    def test_attente_acceptee_ticket_en_cours(self):
        t = self._ticket('SAV-A110-3', statut=Ticket.Statut.EN_COURS)
        r = self._poster_attente(t)
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertTrue(t.en_attente_client)
        self.assertEqual(t.attente_depuis, self.today)
