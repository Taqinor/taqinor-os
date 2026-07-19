"""PUB100 — Tests rétention/purge CNDP + propagation d'effacement CRM.

Prouve : la purge supprime les miroirs au-delà de la fenêtre et garde les
récents (idempotente, désactivable par fenêtre ≤ 0) ; l'événement domaine
``lead_erased`` anonymise les miroirs (phone_key effacé, crm_lead_id détaché)
sans les supprimer ; scoping société.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company

from core.events import lead_erased

from apps.adsengine.models import (
    AdCampaignMirror, CtwaReferral, InsightBreakdown, MetaLeadMirror,
)
from apps.adsengine.receivers import on_lead_erased
from apps.adsengine.tasks import purge_expired_mirrors


def _age(obj, days):
    """Force ``created_at`` à N jours dans le passé (contourne auto_now_add)."""
    type(obj).objects.filter(pk=obj.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=days))


class PurgeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Purge Co', slug='purge-co')

    def _lead_mirror(self, leadgen, days_old):
        m = MetaLeadMirror.objects.create(
            company=self.company, leadgen_id=leadgen, phone_key='k')
        _age(m, days_old)
        return m

    @override_settings(ADSENGINE_LEAD_MIRROR_RETENTION_DAYS=400)
    def test_purges_beyond_window_keeps_recent(self):
        self._lead_mirror('old', 500)
        self._lead_mirror('recent', 10)
        result = purge_expired_mirrors()
        self.assertEqual(result['meta_lead_mirror'], 1)
        self.assertFalse(
            MetaLeadMirror.objects.filter(leadgen_id='old').exists())
        self.assertTrue(
            MetaLeadMirror.objects.filter(leadgen_id='recent').exists())

    @override_settings(ADSENGINE_LEAD_MIRROR_RETENTION_DAYS=400)
    def test_idempotent(self):
        self._lead_mirror('old', 500)
        purge_expired_mirrors()
        result = purge_expired_mirrors()
        self.assertEqual(result['meta_lead_mirror'], 0)

    @override_settings(ADSENGINE_LEAD_MIRROR_RETENTION_DAYS=0)
    def test_window_zero_disables_purge(self):
        self._lead_mirror('old', 900)
        result = purge_expired_mirrors()
        self.assertNotIn('meta_lead_mirror', result)
        self.assertTrue(MetaLeadMirror.objects.filter(leadgen_id='old').exists())

    @override_settings(ADSENGINE_BREAKDOWN_RETENTION_DAYS=400)
    def test_breakdown_purged_by_date(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='C', status='PAUSED')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        old_date = datetime.date.today() - datetime.timedelta(days=500)
        InsightBreakdown.objects.create(
            company=self.company, content_type=ct, object_id=camp.pk,
            date=old_date, dimension=InsightBreakdown.Dimension.REGION,
            key='Casablanca')
        result = purge_expired_mirrors()
        self.assertEqual(result['insight_breakdown'], 1)


class LeadErasedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Erase Co', slug='erase-co')

    def test_anonymizes_mirror_by_lead_id(self):
        m = MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', phone_key='key1',
            crm_lead_id=42)
        on_lead_erased(sender=None, company=self.company, crm_lead_id=42)
        m.refresh_from_db()
        self.assertEqual(m.phone_key, '')
        self.assertIsNone(m.crm_lead_id)
        # La ligne subsiste (agrégat d'attribution conservé, dépersonnalisé).
        self.assertTrue(MetaLeadMirror.objects.filter(pk=m.pk).exists())

    def test_anonymizes_ctwa_by_phone_key(self):
        c = CtwaReferral.objects.create(
            company=self.company, wa_message_id='m1', phone_key='key9',
            crm_lead_id=7)
        on_lead_erased(sender=None, company=self.company, crm_lead_id=None,
                       phone_key='key9')
        c.refresh_from_db()
        self.assertEqual(c.phone_key, '')
        self.assertIsNone(c.crm_lead_id)

    def test_signal_wired(self):
        m = MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg2', phone_key='key2',
            crm_lead_id=99)
        lead_erased.send(sender=None, company=self.company, crm_lead_id=99)
        m.refresh_from_db()
        self.assertEqual(m.phone_key, '')

    def test_company_scoped(self):
        other = Company.objects.create(nom='Other', slug='other-erase')
        mine = MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='a', phone_key='k', crm_lead_id=5)
        theirs = MetaLeadMirror.objects.create(
            company=other, leadgen_id='b', phone_key='k', crm_lead_id=5)
        on_lead_erased(sender=None, company=self.company, crm_lead_id=5)
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.phone_key, '')
        self.assertEqual(theirs.phone_key, 'k')  # autre société intacte
