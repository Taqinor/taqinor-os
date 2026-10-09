"""APAR51 (C-APAR-032) — une écriture AUTOMATIQUE = le geste manuel.

Sonde VA p_l7 : une règle SET_FIELD écrivait ``priorite='nimporte'`` (aucune
validation), ``relance_date=2030-01-01`` sur un lead à CADENCE ACTIVE (le
refus CAD49 du geste en masse ignoré), sans une ligne de chatter ; une règle
CREATE_SAV_TICKET créait un ticket ``type xx priorite yy`` sans échéance
SLA. Désormais le lead s'écrit par ``crm.services.appliquer_champ_automatique``
et le ticket par les services SAV.

Moteur, services crm/sav réels ; aucun mock.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.automation import actions
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType)
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.sav.models import Ticket

User = get_user_model()


class ActionsServicesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='APAR51 Solaire', slug='apar51-actions')
        self.user = User.objects.create_user(
            username='apar51-admin', password='x', company=self.company,
            role_legacy='admin')
        self.client_c = Client.objects.create(
            company=self.company, nom='Client', prenom='Auto')
        self.lead = Lead.objects.create(
            company=self.company, nom='Cadence', client=self.client_c)
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=1,
            canal=RelanceEtape.Canal.APPEL, libelle='Appeler',
            due_date=timezone.localdate() + datetime.timedelta(days=1))

    def _regle(self, action_type, config):
        return AutomationRule.objects.create(
            company=self.company, nom=f'Règle {action_type}',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=action_type, action_config=config)

    def _executer(self, regle):
        return actions.run(regle, self.lead, self.company, {}, self.user)

    def _modifications(self):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION).count()

    def test_priorite_hors_choix_failed(self):
        avant = self._modifications()
        statut, motif = self._executer(self._regle(
            ActionType.SET_FIELD, {'field': 'priorite', 'value': 'nimporte'}))
        self.assertEqual(statut, AutomationRun.Status.FAILED)
        self.assertIn('hors choix', motif)
        self.lead.refresh_from_db()
        self.assertNotEqual(self.lead.priorite, 'nimporte')
        self.assertEqual(self._modifications(), avant)

    def test_relance_sur_cadence_active_skipped(self):
        statut, motif = self._executer(self._regle(
            ActionType.SET_FIELD,
            {'field': 'relance_date', 'value': '2030-01-01'}))
        self.assertEqual(statut, AutomationRun.Status.SKIPPED)
        self.assertIn('CAD49', motif)
        self.lead.refresh_from_db()
        self.assertNotEqual(self.lead.relance_date,
                            datetime.date(2030, 1, 1))

    def test_valeur_valide_chatter(self):
        avant = self._modifications()
        statut, _motif = self._executer(self._regle(
            ActionType.SET_FIELD, {'field': 'priorite', 'value': 'haute'}))
        self.assertEqual(statut, AutomationRun.Status.SUCCESS)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.priorite, 'haute')
        self.assertEqual(self._modifications(), avant + 1)

    def test_ticket_types_valides_et_sla(self):
        statut, _ = self._executer(self._regle(
            ActionType.CREATE_SAV_TICKET,
            {'type': 'xx', 'priorite': 'yy', 'description': 'Contrôle'}))
        self.assertEqual(statut, AutomationRun.Status.FAILED)
        self.assertFalse(Ticket.objects.filter(company=self.company).exists())
        statut, _ = self._executer(self._regle(
            ActionType.CREATE_SAV_TICKET,
            {'type': Ticket.Type.PREVENTIF,
             'priorite': Ticket.Priorite.NORMALE,
             'description': 'Contrôle'}))
        self.assertEqual(statut, AutomationRun.Status.SUCCESS)
        ticket = Ticket.objects.get(company=self.company)
        self.assertIn(ticket.type, Ticket.Type.values)
        self.assertIn(ticket.priorite, Ticket.Priorite.values)
        from apps.sav.services import poser_sla_due_at
        attendu = poser_sla_due_at(
            Ticket(company=self.company, client=self.client_c,
                   priorite=ticket.priorite,
                   date_ouverture=ticket.date_ouverture),
            persister=False).sla_due_at
        self.assertEqual(ticket.sla_due_at, attendu)
