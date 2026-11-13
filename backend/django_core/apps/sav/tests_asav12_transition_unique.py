"""ASAV12 — UN service de transition de statut pour les deux chemins de
résolution : l'action ``resoudre`` et l'intervention terminée.

Deux tickets jumeaux EN_COURS, en retard SLA, avec une immobilisation
ouverte : A résolu par POST ``resoudre``, B par le VRAI service
``installations.services.changer_statut_intervention`` (émet
``intervention_completed``). Mêmes effets : statut, ``sla_breach`` recalculé,
immobilisation fermée, notification client, notification des suiveurs,
RECORD_STATE_CHANGE, ``ticket_resolu`` une fois. Les notifications sont
comptées en base / dans la boîte mail de test.

Run :
    python manage.py test apps.sav.tests_asav12_transition_unique -v2
"""
import threading
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.sav.models import (
    Equipement, SavSlaSettings, Ticket, TicketFollower,
)
from apps.sav.services import ouvrir_downtime
from apps.stock.models import Produit
from core.events import ticket_resolu
from core.test_utils import WideTeardownTimeoutMixin
from testkit.verrous import attendre_un_ecrivain_bloque

User = get_user_model()


@override_settings(ANYMAIL={'SENDINBLUE_API_KEY': 'cle-factice'},  # AMSG57 — l'e-mail part
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TransitionUniqueTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav12-co', defaults={'nom': 'ASAV12 Co'})
        self.admin = User.objects.create_user(
            username='asav12_admin', password='x', role_legacy='admin',
            company=self.company)
        self.suiveur = User.objects.create_user(
            username='asav12_suiveur', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        sla = SavSlaSettings.get(self.company)
        sla.notifications_client_sav = True
        sla.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV12',
            email='asav12-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV12',
            client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASAV12', sku='OND-ASAV12',
            prix_achat=0, prix_vente=600)
        self.signaux = []
        ticket_resolu.connect(self._recu, weak=False)
        self.addCleanup(ticket_resolu.disconnect, self._recu)

    def _recu(self, sender, ticket=None, **kw):
        self.signaux.append(ticket.pk)

    def _jumeau(self, n):
        # Un client par jumeau : la notification client se compte par
        # destinataire, sans dépendre du gabarit du message.
        client = Client.objects.create(
            company=self.company, nom='Jumeau', prenom=n,
            email=f'asav12-{n.lower()}@example.invalid')
        equip = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.inst, numero_serie=f'ASAV12-SN-{n}')
        ticket = Ticket.objects.create(
            company=self.company, reference=f'SAV-ASAV12-{n}',
            client=client, installation=self.inst, equipement=equip,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.EN_COURS,
            created_by=self.admin)
        Ticket.objects.filter(pk=ticket.pk).update(
            sla_due_at=timezone.localdate() - timedelta(days=3),
            sla_breach=True)
        ticket.refresh_from_db()
        TicketFollower.objects.create(
            company=self.company, ticket=ticket, user=self.suiveur)
        ouvrir_downtime(
            company=self.company, equipement=equip,
            debut=timezone.now() - timedelta(days=2), ticket=ticket)
        return ticket, equip

    def _resoudre_par_intervention(self, ticket):
        from apps.installations.services import changer_statut_intervention
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.admin)
        changer_statut_intervention(
            interv, Intervention.Statut.TERMINEE, self.admin)

    def _effets(self, ticket):
        ticket.refresh_from_db()
        return {
            'statut': ticket.statut,
            'sla_breach': ticket.sla_breach,
            'downtimes_ouverts': ticket.downtimes.filter(
                fin__isnull=True).count(),
            'suiveurs': Notification.objects.filter(
                company=self.company, recipient=self.suiveur,
                event_type=EventType.SAV_TICKET_FOLLOWED_UPDATE,
                link=f'/sav/tickets/{ticket.pk}').count(),
            'mails_client': sum(
                1 for m in mail.outbox if ticket.client.email in m.to),
            'ticket_resolu': self.signaux.count(ticket.pk),
        }

    def test_parite_resoudre_vs_intervention(self):
        a, _ = self._jumeau('A')
        b, _ = self._jumeau('B')
        with patch('apps.automation.engine.evaluate') as evaluate:
            r = self.api.post(f'/api/django/sav/tickets/{a.pk}/resoudre/')
            self.assertEqual(r.status_code, 200, r.content)
            self._resoudre_par_intervention(b)
        cibles = [c.args[1].pk for c in evaluate.call_args_list
                  if isinstance(c.args[1], Ticket)]
        self.assertEqual(cibles.count(a.pk), 1)
        self.assertEqual(cibles.count(b.pk), 1)
        effets_a, effets_b = self._effets(a), self._effets(b)
        self.assertEqual(effets_a, effets_b)
        self.assertEqual(effets_a['statut'], Ticket.Statut.RESOLU)
        self.assertFalse(effets_a['sla_breach'])
        self.assertEqual(effets_a['ticket_resolu'], 1)

    def test_immobilisation_fermee_par_intervention(self):
        b, equip = self._jumeau('B')
        self._resoudre_par_intervention(b)
        self.assertEqual(b.downtimes.filter(fin__isnull=True).count(), 0)
        # Une nouvelle immobilisation de l'équipement est acceptée.
        ouvrir_downtime(
            company=self.company, equipement=equip, debut=timezone.now())

    def test_notifications_par_intervention(self):
        b, _ = self._jumeau('B')
        self._resoudre_par_intervention(b)
        effets = self._effets(b)
        self.assertEqual(effets['suiveurs'], 1)
        self.assertEqual(effets['mails_client'], 1)
        self.assertEqual(effets['ticket_resolu'], 1)

    def test_transition_interdite_400(self):
        t = Ticket.objects.create(
            company=self.company, reference='SAV-ASAV12-C',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.EN_COURS,
            created_by=self.admin)
        r = self.api.post(f'/api/django/sav/tickets/{t.pk}/reouvrir/')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('statut', r.data)


class TransitionCroiseeTests(WideTeardownTimeoutMixin, TransactionTestCase):
    """ACNC32 — deux « Résoudre » croisés sur DEUX vraies connexions (patron
    `TestSavPiecesConcurrence._course` de `tests_pieces.py`) : A résout dans
    sa transaction et tient la ligne ; B arrive avant le commit de A."""

    def setUp(self):
        self.company = Company.objects.create(nom='ACNC32 Co', slug='acnc32-co')
        self.admin = User.objects.create_user(
            username='acnc32_admin', password='x', role_legacy='admin',
            company=self.company)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ACNC32-1',
            client=Client.objects.create(company=self.company, nom='C'),
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.EN_COURS,
            created_by=self.admin)
        self.signaux = []
        ticket_resolu.connect(self._recu, weak=False)
        self.addCleanup(ticket_resolu.disconnect, self._recu)

    def _recu(self, sender, ticket=None, **kw):
        self.signaux.append(ticket.pk)

    def test_deux_resolutions_croisees_emettent_une_fois(self):
        from apps.sav.services import appliquer_transition_ticket
        a_tient, res = threading.Event(), {}

        def fil_a():
            with transaction.atomic():
                appliquer_transition_ticket(
                    Ticket.objects.get(pk=self.ticket.pk), Ticket.Statut.RESOLU, self.admin)
                a_tient.set()
                attendre_un_ecrivain_bloque()  # B bloqué avant le commit de A
            connection.close()

        def fil_b():
            a_tient.wait(5)
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
            res['b'] = api.post(f'/api/django/sav/tickets/{self.ticket.pk}/resoudre/').status_code
            connection.close()
        fils = [threading.Thread(target=fil_a), threading.Thread(target=fil_b)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(20)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, Ticket.Statut.RESOLU)
        self.assertEqual(self.signaux.count(self.ticket.pk), 1)
        # B relit « résolu » sous le verrou : même statut = no-op de la
        # machine d'états (aucun effet, aucune seconde émission).
        self.assertEqual(res.get('b'), 200)
