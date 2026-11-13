"""ASAV15 — l'échéance SLA suit la priorité, l'ouverture et le client.

Un PATCH de ``priorite`` / ``date_ouverture`` / ``client`` (et l'édition en
masse de la priorité) recalcule ``sla_due_at`` et remet à zéro pré-alerte,
escalade et ``sla_breach`` (nouveau cycle). Un PATCH d'un autre champ ne
touche pas l'échéance.

Run :
    python manage.py test apps.sav.tests_asav15_sla_edition -v2
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


class SlaEditionTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav15-co', defaults={'nom': 'ASAV15 Co'})
        self.admin = User.objects.create_user(
            username='asav15_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_jours_ouvres = False
        sla.sla_resolution_days = 7
        sla.sla_par_priorite = {'urgente': {'resolution': 1}}
        sla.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV15')
        self.today = timezone.localdate()
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ASAV15-1',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            priorite='normale', date_ouverture=self.today,
            created_by=self.admin)
        Ticket.objects.filter(pk=self.ticket.pk).update(
            sla_due_at=self.today + timedelta(days=7),
            sla_pre_alert_notifiee=True, sla_escalade_notifiee=True)
        self.ticket.refresh_from_db()

    def _patch(self, corps):
        r = self.api.patch(f'{BASE}/{self.ticket.pk}/', corps, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.ticket.refresh_from_db()

    def test_priorite_recalcule(self):
        self._patch({'priorite': 'urgente'})
        self.assertEqual(self.ticket.sla_due_at, self.today + timedelta(days=1))

    def test_date_ouverture_recalcule(self):
        ouverture = self.today - timedelta(days=30)
        self._patch({'date_ouverture': ouverture.isoformat()})
        self.assertEqual(self.ticket.sla_due_at, ouverture + timedelta(days=7))
        self.assertTrue(self.ticket.sla_breach)

    def test_lot_recalcule(self):
        self._patch({'priorite': 'urgente'})
        r = self.api.post(f'{BASE}/actions-groupees/', {
            'ids': [self.ticket.pk], 'operation': 'priorite',
            'priorite': 'normale'}, format='json')
        self.assertIn(r.status_code, (200, 207), r.content)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.sla_due_at, self.today + timedelta(days=7))

    def test_drapeaux_remis(self):
        self._patch({'priorite': 'urgente'})
        self.assertFalse(self.ticket.sla_pre_alert_notifiee)
        self.assertFalse(self.ticket.sla_escalade_notifiee)

    def test_sla_et_supervision_journalises(self):
        """ASOC82 (C-ASOC-164) — l'upsert des réglages SLA SAV et de
        supervision écrit une ligne ``SettingsAuditLog`` ancien → nouveau ;
        réponses inchangées (200 + réglage)."""
        from apps.parametres.models import SettingsAuditLog
        r = self.api.post('/api/django/sav/sla-settings/',
                          {'sla_resolution_days': 3}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['sla_resolution_days'], 3)
        r = self.api.post('/api/django/monitoring/settings/',
                          {'underperf_threshold_pct': '5'}, format='json')  # DecimalLitteral
        self.assertEqual(r.status_code, 200, r.content)
        lignes = {ligne.section: ligne for ligne in SettingsAuditLog.objects
                  .filter(company=self.company)}
        self.assertEqual(set(lignes), {'sav', 'monitoring'})
        self.assertIn('sla_resolution_days=7', lignes['sav'].old_value)
        self.assertIn('sla_resolution_days=3', lignes['sav'].new_value)
        self.assertIn('underperf_threshold_pct=20', lignes['monitoring'].old_value)
        self.assertIn('underperf_threshold_pct=5', lignes['monitoring'].new_value)
        self.assertEqual(lignes['sav'].user, self.admin)

    def test_autre_champ_inchange(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(
            sla_due_at=self.today + timedelta(days=5))
        self._patch({'description': 'Précision du client.'})
        self.assertEqual(self.ticket.sla_due_at, self.today + timedelta(days=5))
        self.assertTrue(self.ticket.sla_pre_alert_notifiee)

    def test_ecriture_sla_et_supervision_exige_parametres_modifier(self):
        """ADRG46 (C-ADRG-036, D-ADRG-5) — délais SLA SAV et réglage de
        supervision = réglages de toute la société : écriture réservée à
        ``parametres_modifier`` (Directeur, Administrateur, compte hérité
        responsable) ; les quatre rôles livrés sans le code → 403, singletons
        inchangés, aucune ligne ``SettingsAuditLog`` ; lectures inchangées."""
        from apps.monitoring.models import MonitoringSettings
        from apps.parametres.models import SettingsAuditLog
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            ADMIN_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
            DIRECTEUR_PERMISSIONS, RESPONSABLE_PERMISSIONS,
            TECHNICIEN_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS)
        roles = {
            'Commercial responsable': COMMERCIAL_RESP_PERMISSIONS,
            'Technicien': TECHNICIEN_PERMISSIONS,
            'Technicien responsable': TECHNICIEN_RESP_PERMISSIONS,
            'Responsable': RESPONSABLE_PERMISSIONS,
            'Directeur': DIRECTEUR_PERMISSIONS,
            'Administrateur': ADMIN_PERMISSIONS,
        }
        autorises = {'Directeur', 'Administrateur', 'hérité'}
        comptes = {'hérité': User.objects.create_user(
            username='adrg46_herite', password='x',
            role_legacy='responsable', company=self.company)}
        for i, (nom, perms) in enumerate(roles.items()):
            comptes[nom] = User.objects.create_user(
                username=f'adrg46_u{i}', password='x', company=self.company,
                role=Role.objects.create(company=self.company, nom=nom,
                                         permissions=list(perms)))
        MonitoringSettings.get(self.company)

        def api_de(nom):
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=(
                f'Bearer {AccessToken.for_user(comptes[nom])}'))
            return api

        for nom in set(comptes) - autorises:
            api = api_de(nom)
            r = api.post('/api/django/sav/sla-settings/',
                         {'sla_resolution_days': 30}, format='json')
            self.assertEqual(r.status_code, 403, (nom, r.content))
            r = api.post('/api/django/monitoring/settings/',
                         {'underperf_threshold_pct': '30'}, format='json')
            self.assertEqual(r.status_code, 403, (nom, r.content))
            self.assertEqual(api.get('/api/django/sav/sla-settings/')
                             .status_code, 200, nom)
            self.assertEqual(api.get('/api/django/monitoring/settings/')
                             .status_code, 200, nom)
        self.assertEqual(SavSlaSettings.get(self.company).sla_resolution_days, 7)
        self.assertEqual(
            MonitoringSettings.get(self.company).underperf_threshold_pct, 20)
        self.assertFalse(SettingsAuditLog.objects.filter(
            company=self.company).exists())
        for nom in autorises:
            r = api_de(nom).post('/api/django/sav/sla-settings/',
                                 {'sla_resolution_days': 30}, format='json')
            self.assertEqual(r.status_code, 200, (nom, r.content))
            r = api_de(nom).post('/api/django/monitoring/settings/',
                                 {'underperf_threshold_pct': '30'}, format='json')
            self.assertEqual(r.status_code, 200, (nom, r.content))
