"""NTSEC17 — Rétention & horodatage inviolable (hash-chaining).

Garanties : une chaîne intacte se vérifie ; toute altération d'une ligne casse
la vérification ; le chaînage est scopé société ; la rétention effective ne
descend jamais sous le plancher légal.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.recorder import record
from apps.audit.selectors import (
    AUDIT_RETENTION_FLOOR_DAYS, effective_retention_days, verify_audit_chain,
)
from testkit.factories import CompanyFactory


class HashChainTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other = CompanyFactory()

    def _emit(self, n, company=None):
        company = company or self.company
        for i in range(n):
            record(AuditLog.Action.LOGIN, user=None, company=company,
                   detail=f'evt-{i}')

    def test_intact_chain_verifies(self):
        self._emit(4)
        res = verify_audit_chain(self.company.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['checked'], 4)

    def test_each_entry_is_chained(self):
        self._emit(3)
        rows = list(AuditLog.objects.filter(
            company=self.company).order_by('id'))
        self.assertTrue(all(r.entry_hash for r in rows))
        # Chaque prev_hash pointe le entry_hash précédent.
        self.assertEqual(rows[0].prev_hash, '')
        self.assertEqual(rows[1].prev_hash, rows[0].entry_hash)
        self.assertEqual(rows[2].prev_hash, rows[1].entry_hash)

    def test_tampering_breaks_chain(self):
        self._emit(4)
        target = AuditLog.objects.filter(
            company=self.company).order_by('id')[1]
        # Altération directe en base (contourne record()) → hash désaligné.
        AuditLog.objects.filter(pk=target.pk).update(detail='ALTERED')
        res = verify_audit_chain(self.company.id)
        self.assertFalse(res['ok'])
        self.assertEqual(res['broken_pk'], target.pk)

    def test_deletion_breaks_chain(self):
        self._emit(4)
        rows = list(AuditLog.objects.filter(
            company=self.company).order_by('id'))
        rows[1].delete()
        res = verify_audit_chain(self.company.id)
        self.assertFalse(res['ok'])

    def test_chain_is_company_scoped(self):
        self._emit(3, company=self.company)
        self._emit(3, company=self.other)
        self.assertTrue(verify_audit_chain(self.company.id)['ok'])
        self.assertTrue(verify_audit_chain(self.other.id)['ok'])

    def test_retention_floor(self):
        self.assertEqual(effective_retention_days(0), 0)
        self.assertEqual(
            effective_retention_days(30), AUDIT_RETENTION_FLOOR_DAYS)
        self.assertEqual(
            effective_retention_days(AUDIT_RETENTION_FLOOR_DAYS + 100),
            AUDIT_RETENTION_FLOOR_DAYS + 100)


class PurgeRetentionTests(TestCase):
    def test_purge_respects_floor(self):
        from django.core.management import call_command

        from apps.parametres.models import CompanyProfile

        company = CompanyFactory()
        CompanyProfile.objects.create(
            company=company, audit_retention_days=30)  # < plancher
        old = AuditLog.objects.create(
            company=company, action=AuditLog.Action.LOGIN)
        # Entrée « ancienne de 200 j » : sous 30 j configurés mais AU-DESSUS du
        # plancher légal (365 j) → NE DOIT PAS être purgée.
        AuditLog.objects.filter(pk=old.pk).update(
            timestamp=timezone.now() - timedelta(days=200))
        call_command('purge_audit_log', '--company', str(company.id))
        self.assertTrue(AuditLog.objects.filter(pk=old.pk).exists())

    def test_purge_deletes_beyond_effective_window(self):
        from django.core.management import call_command

        from apps.parametres.models import CompanyProfile

        company = CompanyFactory()
        CompanyProfile.objects.create(
            company=company, audit_retention_days=30)
        ancient = AuditLog.objects.create(
            company=company, action=AuditLog.Action.LOGIN)
        AuditLog.objects.filter(pk=ancient.pk).update(
            timestamp=timezone.now() - timedelta(days=500))
        call_command('purge_audit_log', '--company', str(company.id))
        self.assertFalse(AuditLog.objects.filter(pk=ancient.pk).exists())
