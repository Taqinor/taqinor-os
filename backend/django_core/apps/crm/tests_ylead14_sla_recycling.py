"""YLEAD14 — Recyclage des leads non travaillés (SLA speed-to-lead → escalade).

Couvre :
  - ``selectors.leads_sla_depasse`` : un lead NEW assigné sans contact depuis
    plus que le seuil (``now`` injecté) est listé ; un lead déjà contacté ne
    l'est pas ; company-scopé ; SLA désactivé (0) → liste vide ;
  - la commande escalade (activité + notification) chaque lead SLA-dépassé,
    une seule fois (idempotent — un second passage ne re-notifie pas) ;
  - un lead déjà contacté n'est jamais escaladé ;
  - désassignation optionnelle au 2e seuil (``lead_sla_deassign_hours``),
    désactivée par défaut (0 → jamais désassigné) ;
  - best-effort : company-scopé, aucune fuite entre sociétés.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from django.contrib.auth import get_user_model

from apps.crm import selectors, stages
from apps.crm.management.commands.recycler_leads_non_travailles import (
    recycler_leads_non_travailles,
)
from apps.crm.models import Lead, LeadActivity
from apps.notifications.models import Notification
from apps.parametres.models import CompanyProfile

User = get_user_model()


def _old_new_lead(company, hours_ago=48, owner=None):
    lead = Lead.objects.create(
        company=company, nom='Prospect ancien', stage=stages.NEW)
    # L'owner est posé via .update() (comme date_creation ci-dessous), pas à
    # la création : passer owner=... à Lead.objects.create() déclencherait le
    # signal apps.notifications.signals.lead_post_save (LEAD_ASSIGNED) sur la
    # transition d'owner, ce qui polluerait les assertions de comptage de
    # notification de ces tests (elles ne portent que sur la notification
    # d'escalade SLA émise par la commande elle-même).
    Lead.objects.filter(pk=lead.pk).update(
        date_creation=timezone.now() - datetime.timedelta(hours=hours_ago),
        owner=owner)
    lead.refresh_from_db()
    return lead


class LeadsSlaDepasseSelectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD14', slug='taqinor-ylead14')
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=24)

    def test_uncontacted_lead_past_sla_is_listed(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48)
        qs = selectors.leads_sla_depasse(self.company, now=now)
        self.assertIn(lead, list(qs))

    def test_already_contacted_lead_is_not_listed(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48)
        lead.first_contacted_at = timezone.now()
        lead.stage = stages.CONTACTED
        lead.save(update_fields=['first_contacted_at', 'stage'])
        qs = selectors.leads_sla_depasse(self.company, now=now)
        self.assertNotIn(lead, list(qs))

    def test_recent_lead_within_sla_not_listed(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=1)
        qs = selectors.leads_sla_depasse(self.company, now=now)
        self.assertNotIn(lead, list(qs))

    def test_sla_disabled_returns_empty(self):
        now = timezone.now()
        _old_new_lead(self.company, hours_ago=100)
        qs = selectors.leads_sla_depasse(self.company, now=now, seuil_heures=0)
        self.assertEqual(list(qs), [])

    def test_company_scoped(self):
        other = Company.objects.create(nom='Autre', slug='ylead14-autre')
        CompanyProfile.objects.create(company=other, lead_sla_hours=24)
        now = timezone.now()
        lead_a = _old_new_lead(self.company, hours_ago=48)
        _old_new_lead(other, hours_ago=48)
        qs = selectors.leads_sla_depasse(self.company, now=now)
        self.assertEqual(list(qs), [lead_a])


class RecyclerLeadsCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD14 Cmd', slug='taqinor-ylead14-cmd')
        self.profile = CompanyProfile.objects.create(
            company=self.company, lead_sla_hours=24)
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir'])
        self.owner = User.objects.create_user(
            username='owner_ylead14', password='x',
            company=self.company, role=role)

    def test_un_lead_en_echec_n_arrete_pas_la_passe(self):
        # ACVI85 — le 1er lève, le 2e est traité ; la société inactive : rien.
        from unittest import mock
        from apps.crm.management.commands import (
            escalader_rappels_demandes as rappels,
            recycler_leads_non_travailles as recyclage)
        inactive = Company.objects.create(
            nom='ACVI85 inactive', slug='acvi85-inactive', actif=False)
        CompanyProfile.objects.create(company=inactive, lead_sla_hours=24)
        chez_inactive = _old_new_lead(inactive, hours_ago=48)
        _old_new_lead(self.company, hours_ago=48, owner=self.owner)
        second = _old_new_lead(self.company, hours_ago=47, owner=self.owner)
        vrai = recyclage._escalate
        appels = []

        def premier_leve(lead, *args):
            appels.append(lead.pk)
            if len(appels) == 1:
                raise RuntimeError('écriture impossible')
            return vrai(lead, *args)

        with mock.patch.object(recyclage, '_escalate', premier_leve), \
                self.assertLogs(recyclage.logger, 'WARNING'):
            escalated, _ = recycler_leads_non_travailles(now=timezone.now())
        self.assertEqual(escalated, 1)
        self.assertEqual(len(appels), 2)
        self.assertTrue(LeadActivity.objects.filter(
            lead=second, body__contains='recyclage SLA').exists())
        self.assertNotIn(chez_inactive.pk, appels)

        # Le jumeau des rappels demandés : même isolement par lead.
        leads = [_old_new_lead(self.company), second]
        with mock.patch.object(
                selectors, 'leads_callback_sla_depasse', return_value=leads), \
                mock.patch.object(rappels, '_escalate',
                                  side_effect=[RuntimeError('x'), None]) as escalade, \
                self.assertLogs(rappels.logger, 'WARNING'):
            total = rappels.escalader_rappels_demandes(now=timezone.now())
        self.assertEqual(escalade.call_count, 2)
        self.assertEqual(total, 1)

    def test_traiter_chaine_acceptation_isole_chaque_devis(self):
        # ACVI85 — la notification du 1er devis lève, le 2e est escaladé.
        import datetime as dt
        from types import SimpleNamespace
        from unittest import mock
        from apps.crm import cadence_filet
        accepte = dt.date(2026, 10, 1)
        devis = [
            SimpleNamespace(pk=rang, reference=f'DEV-{rang}', date_acceptation=accepte,
                            lead=lead, lead_id=lead.pk)
            for rang, lead in enumerate((_old_new_lead(self.company),
                                         _old_new_lead(self.company)), start=1)]
        echus = mock.MagicMock()
        echus.filter.return_value.select_related.return_value = devis
        with mock.patch('apps.ventes.selectors.devis_signes_en_vigueur',
                        return_value=echus), \
                mock.patch('apps.ventes.selectors.acompte_paye_pour_devis',
                           return_value=False), \
                mock.patch('apps.crm.dispatch._destinataires_direction',
                           return_value=[self.owner]), \
                mock.patch('apps.notifications.services.notify_many',
                           side_effect=[RuntimeError('x'), []]):
            bilan = cadence_filet.traiter_chaine_acceptation()
        self.assertEqual(bilan['escalades'], 1)

    def test_escalates_sla_breached_lead_once(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48, owner=self.owner)

        escalated, deassigned = recycler_leads_non_travailles(now=now)
        self.assertEqual(escalated, 1)
        self.assertEqual(deassigned, 0)

        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('recyclage SLA' in (n.body or '') for n in notes))
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner).count(), 1)

        # Deuxième passage — idempotent : pas de deuxième escalade/notif.
        escalated_2, _ = recycler_leads_non_travailles(now=now)
        self.assertEqual(escalated_2, 0)
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner).count(), 1)

    def test_contacted_lead_is_never_escalated(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48, owner=self.owner)
        lead.first_contacted_at = timezone.now()
        lead.stage = stages.CONTACTED
        lead.save(update_fields=['first_contacted_at', 'stage'])

        escalated, _ = recycler_leads_non_travailles(now=now)
        self.assertEqual(escalated, 0)
        self.assertFalse(
            LeadActivity.objects.filter(lead=lead).exists())

    def test_deassign_disabled_by_default(self):
        """lead_sla_deassign_hours=0 (défaut) → jamais désassigné, même très
        ancien — comportement actuel préservé tant que non configuré."""
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=500, owner=self.owner)
        _, deassigned = recycler_leads_non_travailles(now=now)
        self.assertEqual(deassigned, 0)
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.owner.id)

    def test_deassign_after_second_threshold(self):
        self.profile.lead_sla_deassign_hours = 100
        self.profile.save(update_fields=['lead_sla_deassign_hours'])
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=150, owner=self.owner)

        _, deassigned = recycler_leads_non_travailles(now=now)
        self.assertEqual(deassigned, 1)
        lead.refresh_from_db()
        self.assertIsNone(lead.owner_id)

    def test_dry_run_does_not_write(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48, owner=self.owner)
        escalated, _ = recycler_leads_non_travailles(now=now, dry_run=True)
        self.assertEqual(escalated, 1)
        self.assertFalse(LeadActivity.objects.filter(lead=lead).exists())
        self.assertEqual(Notification.objects.count(), 0)
