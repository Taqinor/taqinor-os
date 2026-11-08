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
        # La CRÉATION d'un ticket notifie déjà (YEVNT4, signal hors balayage) :
        # seules les notifications posées PAR LES BALAYAGES sont jugées.
        avant = set(Notification.objects.filter(
            company=self.suspendue).values_list('pk', flat=True))
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
            company=self.suspendue).exclude(pk__in=avant).exists())

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

    def test_cloture_facturable_non_facture_refusee(self):
        """ACSV60 : « Clôturer » un ticket facturable à 1 pièce sans facture
        rend 409 `ticket_non_facture`, le balayage le laisse Résolu, le
        forçage responsable motivé passe (note), le Technicien est refusé."""
        from decimal import Decimal

        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.roles.models import Role
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.sav.models import PieceConsommee
        from apps.stock.models import Produit
        t = self._resolu_dormant(self.active)
        Ticket.objects.filter(pk=t.pk).update(couverture='facturable')
        produit = Produit.objects.create(
            company=self.active, nom='Câble ACSV60', sku='CAB-ACSV60',
            prix_vente=Decimal('50'), prix_achat=Decimal('20'))
        PieceConsommee.objects.create(
            company=self.active, ticket=t, produit=produit,
            quantite=Decimal('1'), created_by=self.active._tech)
        self.assertEqual(tasks.scan_auto_cloture_tickets_resolus(), 0)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.RESOLU)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(
            self.active._tech))
        url = f'/api/django/sav/tickets/{t.pk}/cloturer/'
        r = api.post(url, {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data['code'], 'ticket_non_facture')
        role = Role.objects.create(
            company=self.active, nom='Technicien ACSV60',
            permissions=list(TECHNICIEN_PERMISSIONS))
        tech = User.objects.create_user(
            username='acsv60-tech', password='x', company=self.active,
            role=role)
        # Portée « équipe » du Technicien : le ticket lui est affecté, le
        # refus attendu est celui du forçage (403), pas l'invisibilité (404).
        Ticket.objects.filter(pk=t.pk).update(technicien_responsable=tech)
        api_tech = APIClient()
        api_tech.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(tech))
        r = api_tech.post(url, {'sans_facture': True, 'motif': 'x'},
                          format='json')
        self.assertEqual(r.status_code, 403, r.data)
        r = api.post(url, {'sans_facture': True, 'motif': 'geste commercial'},
                     format='json')
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.CLOTURE)
        self.assertTrue(TicketActivity.objects.filter(
            ticket=t,
            body__contains='Clôturé sans facture : geste commercial').exists())

    def test_entree_beat(self):
        from django.conf import settings

        from erp_agentique.celery import app
        entree = app.conf.beat_schedule['sav-auto-cloture']
        self.assertEqual(entree['task'], 'sav.scan_auto_cloture_quotidien')
        self.assertEqual(
            settings.CELERY_TASK_ROUTES['sav.scan_auto_cloture_quotidien'],
            {'queue': 'scheduled'})
