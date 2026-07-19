"""PUB37 — Flag no-show sur les RDV (crm.Appointment) + taux par annonce.

Couvre :
  - modèle : ``Appointment.Statut.NO_SHOW`` additif, DISTINCT d'ANNULE ;
  - ``crm.selectors.lead_appointment_stats`` : total/no_show PAR LEAD, un lead
    sans RDV absent du dict ;
  - ``apps.adsengine.attribution.variant_attribution`` : appointments/no_show/
    no_show_rate PAR AD (signal qualité intermédiaire) ;
  - ``apps.adsengine.reporting.variant_table`` : propage les mêmes clés.
"""
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Appointment, Lead
from apps.crm.selectors import lead_appointment_stats


def make_company(slug, nom=None):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom or slug})
    return c


class AppointmentNoShowModelTests(TestCase):
    def test_no_show_distinct_from_annule(self):
        self.assertNotEqual(
            Appointment.Statut.NO_SHOW, Appointment.Statut.ANNULE)
        self.assertEqual(Appointment.Statut.NO_SHOW, 'no_show')


class LeadAppointmentStatsTests(TestCase):
    def setUp(self):
        self.co = make_company('pub37-stats')
        self.lead = Lead.objects.create(company=self.co, nom='L')

    def _appt(self, statut, **kw):
        from django.utils import timezone
        return Appointment.objects.create(
            company=self.co, lead=self.lead,
            scheduled_at=timezone.now(), statut=statut, **kw)

    def test_lead_without_appointment_absent_from_dict(self):
        stats = lead_appointment_stats(self.co)
        self.assertNotIn(self.lead.id, stats)

    def test_counts_total_and_no_show(self):
        self._appt(Appointment.Statut.EFFECTUE)
        self._appt(Appointment.Statut.NO_SHOW)
        self._appt(Appointment.Statut.NO_SHOW)
        stats = lead_appointment_stats(self.co)
        self.assertEqual(stats[self.lead.id]['total'], 3)
        self.assertEqual(stats[self.lead.id]['no_show'], 2)

    def test_annule_not_counted_as_no_show(self):
        self._appt(Appointment.Statut.ANNULE)
        stats = lead_appointment_stats(self.co)
        self.assertEqual(stats[self.lead.id]['total'], 1)
        self.assertEqual(stats[self.lead.id]['no_show'], 0)

    def test_scoped_to_company(self):
        other = make_company('pub37-stats-other')
        other_lead = Lead.objects.create(company=other, nom='O')
        from django.utils import timezone
        Appointment.objects.create(
            company=other, lead=other_lead, scheduled_at=timezone.now(),
            statut=Appointment.Statut.NO_SHOW)
        stats = lead_appointment_stats(self.co)
        self.assertNotIn(other_lead.id, stats)


class VariantAttributionNoShowTests(TestCase):
    def setUp(self):
        from apps.adsengine.models import AdCampaignMirror, AdMirror, AdSetMirror

        self.co = make_company('pub37-variant')
        camp = AdCampaignMirror.objects.create(
            company=self.co, meta_id='cmp_ns', name='Campagne', status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=self.co, meta_id='ast_ns', name='Toit', campaign=camp)
        AdMirror.objects.create(
            company=self.co, meta_id='ad_ns', name='Ad No-Show', adset=adset)

    def _appt(self, lead, statut):
        from django.utils import timezone
        return Appointment.objects.create(
            company=self.co, lead=lead, scheduled_at=timezone.now(),
            statut=statut)

    def test_no_show_rate_per_ad(self):
        from apps.adsengine import attribution

        l1 = Lead.objects.create(company=self.co, nom='L1', meta_ad_id='ad_ns')
        l2 = Lead.objects.create(company=self.co, nom='L2', meta_ad_id='ad_ns')
        self._appt(l1, Appointment.Statut.EFFECTUE)
        self._appt(l2, Appointment.Statut.NO_SHOW)
        self._appt(l2, Appointment.Statut.NO_SHOW)

        res = attribution.variant_attribution(self.co)
        v = res['variants'][0]
        self.assertEqual(v['appointments'], 3)
        self.assertEqual(v['no_show'], 2)
        self.assertAlmostEqual(v['no_show_rate'], 2 / 3, places=4)

    def test_no_show_rate_none_without_appointments(self):
        from apps.adsengine import attribution

        Lead.objects.create(company=self.co, nom='L1', meta_ad_id='ad_ns')
        res = attribution.variant_attribution(self.co)
        v = res['variants'][0]
        self.assertEqual(v['appointments'], 0)
        self.assertIsNone(v['no_show_rate'])


class ReportingVariantTableNoShowTests(TestCase):
    def test_variant_table_exposes_no_show_fields(self):
        from django.utils import timezone

        from apps.adsengine import reporting
        from apps.adsengine.models import AdCampaignMirror, AdMirror, AdSetMirror

        co = make_company('pub37-reporting')
        camp = AdCampaignMirror.objects.create(
            company=co, meta_id='cmp_r2', name='Campagne', status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=co, meta_id='ast_r2', name='Toit', campaign=camp)
        AdMirror.objects.create(
            company=co, meta_id='ad_r2', name='Ad Report NS', adset=adset)
        lead = Lead.objects.create(company=co, nom='L', meta_ad_id='ad_r2')
        Appointment.objects.create(
            company=co, lead=lead, scheduled_at=timezone.now(),
            statut=Appointment.Statut.NO_SHOW)

        table = reporting.variant_table(co)
        v = table['variants'][0]
        self.assertEqual(v['appointments'], 1)
        self.assertEqual(v['no_show'], 1)
        self.assertEqual(v['no_show_rate'], 1.0)
