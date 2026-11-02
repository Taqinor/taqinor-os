"""CADV2 -- les tuiles KPI du funnel ignorent opposes et fiches de test."""
from django.test import TestCase

from apps.crm.kpis import kpi_crm
from apps.crm.models import Lead
from apps.crm.stages import NEW


class KpiCrmComptesTests(TestCase):
    def test_opposes_et_fiches_test_hors_tuiles(self):
        from authentication.models import Company
        societe = Company.objects.create(slug='kpi-cadv2', nom='Kpi CADV2')
        base = {'company': societe, 'stage': NEW}
        Lead.objects.create(nom='N1', **base)
        Lead.objects.create(nom='N2', ne_plus_contacter=True, **base)
        Lead.objects.create(nom='N3', tags='vip, test', **base)
        Lead.objects.create(nom='N4', tags='testeur', **base)  # pas l'etiquette
        Lead.objects.create(nom='P', perdu=True, **base)
        Lead.objects.create(nom='A', is_archived=True, **base)
        Lead.objects.create(nom='PO', perdu=True, ne_plus_contacter=True,
                            **base)

        tuiles = {t['id']: t['valeur'] for t in kpi_crm(societe)}
        # N1 et N4 comptent ; N2 (oppose) et N3 (test) non.
        self.assertEqual(tuiles['crm_leads_actifs'], 2)
        self.assertEqual(tuiles['crm_funnel_%s' % NEW.lower()], 2)
        self.assertEqual(tuiles['crm_leads_perdus'], 1)
