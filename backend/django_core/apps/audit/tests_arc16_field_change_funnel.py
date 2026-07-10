"""Tests ARC16 — entonnoir unique de journalisation d'un changement de champ.

Prouve que ``apps.audit.recorder.record_field_change`` écrit en UN appel
l'``AuditLog`` ET la ligne de chatter ``records.Activity`` (kind=modification),
que ``chatter=False`` n'écrit QUE l'audit, que le diff structuré ``changes`` est
posé, que la détection STATUS/UPDATE est automatique, et que l'entonnoir est
best-effort (un chatter cassé ne casse jamais la ligne d'audit).

Run :
    docker compose exec django_core python manage.py test \
        apps.audit.tests_arc16_field_change_funnel -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.audit import recorder
from apps.audit.models import AuditLog
from apps.records.models import Activity

User = get_user_model()


def _company(slug='arc16-co', nom='ARC16 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _client(company):
    from apps.crm.models import Client
    return Client.objects.create(
        company=company, nom='Cible', prenom='ARC16',
        email='arc16@example.com', telephone='+212600000021', adresse='Rabat')


def _devis(company, client, reference='DEV-ARC16-0001'):
    from apps.ventes.models import Devis
    return Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'))


class RecordFieldChangeFunnelTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='arc16_user', password='pw', role_legacy='admin',
            company=self.company)
        self.client_obj = _client(self.company)

    def test_writes_both_auditlog_and_chatter_in_one_call(self):
        devis = _devis(self.company, self.client_obj)
        recorder.record_field_change(
            devis, 'statut', 'brouillon', 'envoye', user=self.user,
            field_label='Statut')

        # Ligne d'audit STATUS (statut est un champ status-like).
        audit = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.STATUS).latest('id')
        self.assertIn('brouillon', audit.detail)
        self.assertIn('envoye', audit.detail)
        # Diff structuré présent.
        self.assertEqual(audit.changes, [
            {'field': 'statut', 'old': 'brouillon', 'new': 'envoye'}])

        # Ligne de chatter records.Activity kind=modification.
        act = Activity.objects.filter(
            company=self.company, kind=Activity.Kind.MODIFICATION).latest('id')
        self.assertEqual(act.field, 'statut')
        self.assertEqual(act.old_value, 'brouillon')
        self.assertEqual(act.new_value, 'envoye')
        self.assertEqual(act.field_label, 'Statut')
        self.assertEqual(act.created_by, self.user)

    def test_chatter_false_writes_only_auditlog(self):
        devis = _devis(self.company, self.client_obj, reference='DEV-ARC16-0002')
        before = Activity.objects.filter(company=self.company).count()
        recorder.record_field_change(
            devis, 'statut', 'brouillon', 'envoye', user=self.user,
            chatter=False)
        self.assertTrue(AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.STATUS).exists())
        # Aucune nouvelle ligne de chatter.
        self.assertEqual(
            Activity.objects.filter(company=self.company).count(), before)

    def test_non_status_field_uses_update_action(self):
        devis = _devis(self.company, self.client_obj, reference='DEV-ARC16-0003')
        recorder.record_field_change(
            devis, 'remise_globale', '0', '10', user=self.user,
            field_label='Remise globale', chatter=False)
        audit = AuditLog.objects.filter(company=self.company).latest('id')
        self.assertEqual(audit.action, AuditLog.Action.UPDATE)
        self.assertEqual(audit.changes, [
            {'field': 'remise_globale', 'old': '0', 'new': '10'}])

    def test_explicit_action_and_detail_preserved(self):
        devis = _devis(self.company, self.client_obj, reference='DEV-ARC16-0004')
        recorder.record_field_change(
            devis, 'statut', 'envoye', 'expire', user=None,
            action=AuditLog.Action.STATUS, chatter=False,
            detail='Expiration automatique (job : expire_stale_devis).')
        audit = AuditLog.objects.filter(company=self.company).latest('id')
        self.assertEqual(audit.action, AuditLog.Action.STATUS)
        self.assertEqual(
            audit.detail, 'Expiration automatique (job : expire_stale_devis).')
        self.assertEqual(audit.changes, [
            {'field': 'statut', 'old': 'envoye', 'new': 'expire'}])

    def test_best_effort_broken_chatter_does_not_block_audit(self):
        """Un chatter cassé ne casse jamais la ligne d'audit (best-effort)."""
        devis = _devis(self.company, self.client_obj, reference='DEV-ARC16-0005')
        from unittest.mock import patch
        with patch('apps.records.services.log_field_change',
                   side_effect=RuntimeError('boom')):
            # Ne lève pas malgré le chatter cassé.
            recorder.record_field_change(
                devis, 'statut', 'brouillon', 'envoye', user=self.user)
        # La ligne d'audit est bien écrite.
        self.assertTrue(AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.STATUS,
            object_id=str(devis.pk)).exists())
