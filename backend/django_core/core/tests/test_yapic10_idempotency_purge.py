"""Tests YAPIC10 — purge quotidienne des `IdempotencyRecord` (YAPIC9) plus
vieux que 24 h."""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core.idempotency import IdempotencyRecord
from core.tasks import purge_idempotency_records_task


class Yapic10IdempotencyPurgeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='YAPIC10 Co', slug='yapic10-co')

    def _make_record(self, key, age_hours):
        record = IdempotencyRecord.objects.create(
            company=self.company, endpoint='ventes.DevisViewSet', key=key,
            request_fingerprint='deadbeef', response_status=201,
            response_body={'id': 1},
        )
        backdated = timezone.now() - timezone.timedelta(hours=age_hours)
        IdempotencyRecord.objects.filter(pk=record.pk).update(
            created_at=backdated)
        return record

    def test_25h_record_is_purged_23h_record_is_kept(self):
        old = self._make_record('key-old', age_hours=25)
        recent = self._make_record('key-recent', age_hours=23)

        result = purge_idempotency_records_task()

        self.assertEqual(result['deleted'], 1)
        self.assertFalse(
            IdempotencyRecord.objects.filter(pk=old.pk).exists())
        self.assertTrue(
            IdempotencyRecord.objects.filter(pk=recent.pk).exists())

    def test_purge_is_idempotent_second_run_deletes_nothing(self):
        self._make_record('key-old-2', age_hours=48)
        first = purge_idempotency_records_task()
        second = purge_idempotency_records_task()
        self.assertEqual(first['deleted'], 1)
        self.assertEqual(second['deleted'], 0)

    def test_purge_is_company_agnostic(self):
        """La purge se fait par date, jamais par société (une clé
        d'idempotence n'a plus de sens à rejouer passé la fenêtre, quel que
        soit le tenant)."""
        other_company = Company.objects.create(
            nom='YAPIC10 Co 2', slug='yapic10-co-2')
        rec1 = IdempotencyRecord.objects.create(
            company=self.company, endpoint='ventes.DevisViewSet',
            key='k1', request_fingerprint='a', response_status=201,
            response_body={})
        rec2 = IdempotencyRecord.objects.create(
            company=other_company, endpoint='ventes.DevisViewSet',
            key='k1', request_fingerprint='a', response_status=201,
            response_body={})
        cutoff = timezone.now() - timezone.timedelta(hours=25)
        IdempotencyRecord.objects.filter(
            pk__in=[rec1.pk, rec2.pk]).update(created_at=cutoff)

        result = purge_idempotency_records_task()

        self.assertEqual(result['deleted'], 2)
