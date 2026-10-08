"""ASAV33 — balayages SAV dans ``apps/sav/tasks.py``, bornés aux sociétés
actives ; l'auto-clôture a sa tâche planifiée et passe par la machine
d'états (``appliquer_transition_ticket``).

Run :
    python manage.py test apps.sav.tests_asav33_balayages -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.notifications.models import Notification
from apps.sav import tasks
from apps.sav.models import SavSlaSettings, Ticket, TicketActivity

User = get_user_model()


class BalayagesSavTests(TestCase):

    def setUp(self):
        self.today = timezone.localdate()
        self.n = 0
        self.active = self._societe('asav33-active')
        self.suspendue = self._societe('asav33-suspendue')
        Company.objects.filter(pk=self.suspendue.pk).update(actif=False)

    def _societe(self, slug):
        company, _ = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})
        sla = SavSlaSettings.get(company)
        sla.sla_breach_enabled = True
        sla.sla_warning_days = 3
        sla.escalade_activee = True
        sla.auto_cloture_jours = 1
        sla.save()
        user = User.objects.create_user(
            username=f'{slug}-tech', password='x', role_legacy='admin',
            company=company)
        client = Client.objects.create(company=company, nom='C', prenom=slug)
        inst = Installation.objects.create(
            company=company, reference=f'CHT-{slug}', client=client)
        company._tech, company._client, company._inst = user, client, inst
        return company

    def _ticket(self, company, statut, **champs):
        self.n += 1
        t = Ticket.objects.create(
            company=company, reference=f'SAV-ASAV33-{self.n}',
            client=company._client, installation=company._inst,
            type=Ticket.Type.CORRECTIF, statut=statut,
            technicien_responsable=company._tech, created_by=company._tech)
        Ticket.objects.filter(pk=t.pk).update(**champs)
        t.refresh_from_db()
        return t

    def _resolu_dormant(self, company):
        t = self._ticket(company, Ticket.Statut.RESOLU)
        TicketActivity.objects.filter(ticket=t).update(
            created_at=timezone.now() - timedelta(days=2))
        Ticket.objects.filter(pk=t.pk).update(
            date_modification=timezone.now() - timedelta(days=2))
        return t

    def test_societe_suspendue_ignoree(self):
        echu = dict(sla_due_at=self.today - timedelta(days=2))
        t1 = self._ticket(self.suspendue, Ticket.Statut.EN_COURS, **echu)
        t2 = self._ticket(self.suspendue, Ticket.Statut.EN_COURS, **echu)
        resolu = self._resolu_dormant(self.suspendue)
        tasks.scan_sla_breaches()
        tasks.scan_sla_pre_alerts_and_escalations()
        tasks.scan_auto_cloture_tickets_resolus()
        for t in (t1, t2):
            t.refresh_from_db()
            self.assertFalse(t.sla_breach)
            self.assertFalse(t.sla_escalade_notifiee)
        resolu.refresh_from_db()
        self.assertEqual(resolu.statut, Ticket.Statut.RESOLU)
        self.assertFalse(Notification.objects.filter(
            company=self.suspendue).exists())

    def test_auto_cloture_appliquee(self):
        t = self._resolu_dormant(self.active)
        resultat = tasks.scan_auto_cloture_quotidien()
        self.assertEqual(resultat, {'skipped': False, 'tickets': 1})
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.CLOTURE)

    def test_auto_cloture_par_machine_etats(self):
        # Garde YSERV2 : une intervention encore ouverte empêche la clôture.
        t = self._resolu_dormant(self.active)
        Intervention.objects.create(
            company=self.active, installation=self.active._inst, ticket=t,
            type_intervention=Intervention.Type.DEPANNAGE,
            created_by=self.active._tech)
        TicketActivity.objects.filter(ticket=t).update(
            created_at=timezone.now() - timedelta(days=2))
        self.assertEqual(tasks.scan_auto_cloture_tickets_resolus(), 0)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.RESOLU)

    def test_entree_beat(self):
        from django.conf import settings

        from erp_agentique.celery import app
        entree = app.conf.beat_schedule['sav-auto-cloture']
        self.assertEqual(entree['task'], 'sav.scan_auto_cloture_quotidien')
        self.assertEqual(
            settings.CELERY_TASK_ROUTES['sav.scan_auto_cloture_quotidien'],
            {'queue': 'scheduled'})
