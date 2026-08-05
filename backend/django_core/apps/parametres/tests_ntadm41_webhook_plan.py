"""NTADM41 — webhook sortant `plan.changed` (déclenché depuis le SEUL point
d'écriture de CompanyProfile.plan : apps.parametres.admin.CompanyProfileAdmin
.save_model, founder-only). Journalise aussi SettingsAuditLog (section
'licence', field 'plan' — lu par l'écran NTADM9)."""
from types import SimpleNamespace
from unittest import mock

from django.contrib import admin as django_admin
from django.test import TestCase

from authentication.models import Company

from .admin import CompanyProfileAdmin
from .models import CompanyProfile, SettingsAuditLog


def _company(nom='NTADM41Co'):
    return Company.objects.create(nom=nom)


class PlanChangedWebhookTests(TestCase):
    def setUp(self):
        from apps.adminops.models import PlanLicence
        self.company = _company()
        self.profile = CompanyProfile.get(company=self.company)
        self.plan_pro = PlanLicence.objects.get(code='pro')
        self.admin_instance = CompanyProfileAdmin(CompanyProfile, django_admin.site)

    def _fake_request(self):
        return SimpleNamespace(user=None)

    def test_changement_de_plan_journalise_et_declenche_webhook(self):
        with mock.patch('apps.publicapi.delivery.dispatch_event') as dispatch:
            self.profile.plan = self.plan_pro
            self.admin_instance.save_model(
                self._fake_request(), self.profile, form=None, change=True)

        self.assertTrue(dispatch.called)
        args, _kwargs = dispatch.call_args
        self.assertEqual(args[0], self.company.id)
        self.assertEqual(args[1], 'plan.changed')
        self.assertEqual(args[2]['nouveau_plan'], 'pro')
        self.assertIsNone(args[2]['ancien_plan'])

        ligne = SettingsAuditLog.objects.filter(
            company=self.company, section='licence', field='plan').first()
        self.assertIsNotNone(ligne)
        self.assertEqual(ligne.new_value, 'Pro')

    def test_sans_changement_de_plan_aucun_webhook(self):
        with mock.patch('apps.publicapi.delivery.dispatch_event') as dispatch:
            self.admin_instance.save_model(
                self._fake_request(), self.profile, form=None, change=True)
        self.assertFalse(dispatch.called)

    def test_creation_initiale_aucun_webhook(self):
        """`change=False` (création) : jamais de comparaison ancien/nouveau."""
        autre_company = _company('NTADM41Co2')
        nouveau_profile = CompanyProfile(company=autre_company, nom='X', plan=self.plan_pro)
        with mock.patch('apps.publicapi.delivery.dispatch_event') as dispatch:
            self.admin_instance.save_model(
                self._fake_request(), nouveau_profile, form=None, change=False)
        self.assertFalse(dispatch.called)
