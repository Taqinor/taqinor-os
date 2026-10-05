"""CIQ646 — garantie de production : aucun rapport client tant que la
société n'a pas validé l'engagement (``garantie_production_autorisee``,
CIQ622 ; D-CIQ-12). Réglage faux → PDF de garantie 409 FR, rapport O&M 200
sans ligne de garantie ; réglage vrai → comportement actuel.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.monitoring.test_ciq646_garantie_non_validee"
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import MonitoringConfig, ProductionWarranty
from apps.parametres.models import CompanyProfile

User = get_user_model()
RECOURS = {'has_warranty': True, 'manufacturer_recourse': True}


class GarantieNonValideeTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq646-co', defaults={'nom': 'CIQ646 Co'})
        self.user = User.objects.create_user(
            username='ciq646_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Cli', prenom='CIQ646',
            email='ciq646@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CIQ646-1', client=client,
            puissance_installee_kwc=Decimal('10'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst)
        ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0'),
            start_year=2026, tolerance_pct=Decimal('5'))
        self.base = f'/api/django/monitoring/configs/{self.config.pk}/'

    def _autoriser(self):
        profil = CompanyProfile.get(company=self.company)
        profil.garantie_production_autorisee = True
        profil.garantie_production_validation = 'Assureur X, 02/10/2026'
        profil.save()

    def test_reglage_faux_pdf_garantie_409(self):
        r = self.api.get(self.base + 'rapport-garantie-pdf/?annee=2026')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['detail'],
                         'Garantie de production non validée (Paramètres).')

    def test_reglage_faux_rapport_om_sans_garantie(self):
        with mock.patch('apps.monitoring.report.warranty_curve_overlay',
                        return_value=RECOURS) as courbe:
            r = self.api.get(self.base + 'om-report/')
        self.assertEqual(r.status_code, 200, r.data)
        courbe.assert_not_called()
        self.assertFalse(any('garantie' in reco
                             for reco in r.data['recommendations']))

    def test_reglage_vrai_comportement_actuel(self):
        self._autoriser()
        r = self.api.get(self.base + 'rapport-garantie-pdf/?annee=2026')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        from apps.monitoring.report import build_om_report_data
        with mock.patch('apps.monitoring.report.warranty_curve_overlay',
                        return_value=RECOURS):
            data = build_om_report_data(self.inst, today=date(2026, 6, 30))
        self.assertTrue(any('courbe garantie' in reco
                            for reco in data['recommendations']))
