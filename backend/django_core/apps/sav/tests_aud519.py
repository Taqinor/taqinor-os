"""AUD519 — parité SLA entre TOUS les producteurs de tickets SAV.

Constat d'audit (le ROUGE figé ici) : ``TicketViewSet.perform_create`` était le
SEUL point qui calculait ``sla_due_at``. Tous les autres producteurs créaient
le ``Ticket`` sans échéance — et comme ``recompute_sla_breach`` ne calcule
jamais ``sla_due_at`` quand il est None, ces tickets étaient silencieusement
exclus des scans quotidiens : SLA purement décoratif sur WhatsApp, alias
e-mail, QR public, visites préventives, monitoring, tâches projet, NCR et
escalade d'alarme onduleur.

Chaque test ci-dessous créait un ticket avec ``sla_due_at is None`` avant le
correctif ; il vaut désormais exactement l'échéance du chemin manuel.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_aud519 -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import (
    AlarmeOnduleur, CategorieEquipement, ContratMaintenance, Equipement,
    SavSlaSettings, Ticket,
)
from apps.stock.models import Produit

User = get_user_model()

RESOLUTION_DAYS = 4


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AUD519PariteProducteursSlaTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-aud519', defaults={'nom': 'Sav Co AUD519'})
        self.admin = User.objects.create_user(
            username='aud519_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD519',
            email='aud519-client@example.invalid', telephone='0611112222')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-AUD519',
            client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur AUD519', sku='OND-AUD519',
            prix_achat=100, prix_vente=200)
        self.equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        # SLA activé côté société : sans cela, sla_due_at reste None PARTOUT
        # (y compris sur le chemin manuel) — c'est le réglage de référence.
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_resolution_days = RESOLUTION_DAYS
        sla.save(update_fields=['sla_breach_enabled', 'sla_resolution_days'])
        self.today = timezone.localdate()
        self.attendu = self.today + timedelta(days=RESOLUTION_DAYS)

    def _assert_sla(self, ticket, attendu=None):
        self.assertIsNotNone(
            ticket, 'aucun ticket produit — le test ne prouve rien')
        ticket.refresh_from_db()
        self.assertIsNotNone(
            ticket.sla_due_at,
            f'sla_due_at non posé sur le ticket {ticket.reference}')
        self.assertEqual(ticket.sla_due_at, attendu or self.attendu)

    # ── Référence : le chemin manuel (inchangé) ─────────────────────────────

    def test_chemin_manuel_reference(self):
        resp = auth(self.admin).post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'description': 'Panne', 'type': Ticket.Type.CORRECTIF,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self._assert_sla(Ticket.objects.get(pk=resp.data['id']))

    # ── Les producteurs automatiques ────────────────────────────────────────

    def test_create_corrective_ticket(self):
        from apps.sav.services import create_corrective_ticket
        self._assert_sla(create_corrective_ticket(
            company=self.company, client=self.client_obj,
            installation=self.inst, description='Correctif',
            created_by=self.admin))

    def test_creer_ticket_preventif(self):
        from apps.sav.services import creer_ticket_preventif
        self._assert_sla(creer_ticket_preventif(
            company=self.company, client=self.client_obj,
            installation=self.inst, description='Préventif monitoring',
            created_by=self.admin))

    def test_create_ticket_from_projet_tache(self):
        from apps.sav.services import create_ticket_from_projet_tache
        self._assert_sla(create_ticket_from_projet_tache(
            company=self.company, client=self.client_obj,
            description='Tâche projet'))

    def test_router_whatsapp_entrant_vers_ticket(self):
        from apps.sav.services import router_whatsapp_entrant_vers_ticket
        action, ticket = router_whatsapp_entrant_vers_ticket(
            company=self.company, expediteur='212611112222',
            texte='Ma pompe ne démarre plus')
        self.assertEqual(action, 'ticket_cree')
        self._assert_sla(ticket)

    def test_creer_ticket_depuis_email_alias(self):
        from apps.sav.services import creer_ticket_depuis_email_alias
        from core.email_intake import InboundMessage

        CategorieEquipement.objects.create(
            company=self.company, nom='Onduleurs AUD519',
            alias_email='onduleurs-aud519@example.invalid')
        message = InboundMessage(
            message_id='<aud519@example.invalid>', subject='Panne',
            from_email='aud519-client@example.invalid', from_name='Client',
            body='Ça ne démarre plus.',
            raw_headers={'To': 'onduleurs-aud519@example.invalid',
                         'From': 'aud519-client@example.invalid'})
        self._assert_sla(
            creer_ticket_depuis_email_alias(message, self.company))

    def test_qr_public_signaler(self):
        token = self.equip.ensure_public_token()
        resp = APIClient().post(
            f'/api/django/public/sav/equipement/{token}/signaler/',
            {'description': 'La pompe ne démarre plus.'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self._assert_sla(Ticket.objects.get(reference=resp.data['reference']))

    def test_visite_preventive_generee(self):
        from apps.sav.maintenance import generer_visites_dues

        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, actif=True,
            date_debut=self.today - timedelta(days=400))
        self.assertEqual(generer_visites_dues(self.company, self.admin), 1)
        ticket = Ticket.objects.filter(
            company=self.company, type=Ticket.Type.PREVENTIF).latest('id')
        # La visite est datée de son échéance passée : l'échéance SLA se
        # calcule depuis CETTE date d'ouverture, comme le chemin manuel.
        self._assert_sla(
            ticket, ticket.date_ouverture + timedelta(days=RESOLUTION_DAYS))

    def test_escalade_alarme_onduleur(self):
        alarme = AlarmeOnduleur.objects.create(
            company=self.company, equipement=self.equip, code='E07',
            gravite=AlarmeOnduleur.Gravite.CRITIQUE, libelle='Défaut isolement')
        resp = auth(self.admin).post(
            f'/api/django/sav/alarmes-onduleur/{alarme.pk}/escalader/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        alarme.refresh_from_db()
        self._assert_sla(Ticket.objects.get(pk=alarme.ticket_id))

    def test_ticket_ncr(self):
        from apps.sav.services import creer_intervention_depuis_installation

        ticket, cree = creer_intervention_depuis_installation(
            company=self.company, installation_id=self.inst.id,
            description='Non-conformité constatée', ncr_reference='NCR-1')
        self.assertTrue(cree)
        self._assert_sla(ticket)

    # ── No-op quand la société n'a pas activé le SLA ────────────────────────

    def test_sla_desactive_reste_none(self):
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = False
        sla.save(update_fields=['sla_breach_enabled'])
        from apps.sav.services import create_corrective_ticket
        ticket = create_corrective_ticket(
            company=self.company, client=self.client_obj,
            installation=self.inst, description='Sans SLA',
            created_by=self.admin)
        self.assertIsNone(ticket.sla_due_at)
