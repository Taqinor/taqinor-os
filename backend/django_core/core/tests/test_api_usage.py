"""Tests FG398 — plans de tarif API & analytics d'usage.

Couvre :
  * enregistrer_usage incrémente atomiquement le compteur du jour ;
  * quota_depasse respecte le quota journalier (0 = illimité) ;
  * analytics agrège par clé + total ;
  * l'endpoint plan impose company (singleton) + écriture admin ;
  * isolation société sur les compteurs.

NB : la clé d'API (app satellite ``publicapi``) est résolue via
``apps.get_model`` — ``core`` ne l'IMPORTE jamais (contrat de fondation).
"""
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import api_usage
from core.models import ApiUsageRecord
from core.views import ApiUsagePlanViewSet

User = get_user_model()


def _make_api_key(company, label='k'):
    ApiKey = django_apps.get_model('publicapi', 'ApiKey')
    instance, _ = ApiKey.issue(company=company, label=label, scopes=[])
    return instance


class ApiUsageServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')

    def test_enregistrer_usage_increments(self):
        key = _make_api_key(self.company)
        api_usage.enregistrer_usage(key)
        api_usage.enregistrer_usage(key, erreur=True)
        rec = ApiUsageRecord.objects.get(api_key=key)
        self.assertEqual(rec.nb_requetes, 2)
        self.assertEqual(rec.nb_erreurs, 1)
        self.assertEqual(rec.company, self.company)

    def test_quota_depasse_daily(self):
        key = _make_api_key(self.company)
        plan = api_usage.plan_pour_societe(self.company)
        plan.quota_par_jour = 1
        plan.quota_par_mois = 0
        plan.save()
        self.assertFalse(api_usage.quota_depasse(key))
        api_usage.enregistrer_usage(key)
        self.assertTrue(api_usage.quota_depasse(key))

    def test_quota_unlimited_when_zero(self):
        key = _make_api_key(self.company)
        plan = api_usage.plan_pour_societe(self.company)
        plan.quota_par_jour = 0
        plan.quota_par_mois = 0
        plan.save()
        api_usage.enregistrer_usage(key)
        self.assertFalse(api_usage.quota_depasse(key))

    def test_analytics_aggregates(self):
        key = _make_api_key(self.company, 'pro')
        api_usage.enregistrer_usage(key)
        api_usage.enregistrer_usage(key)
        data = api_usage.analytics(self.company)
        self.assertEqual(data['total_requetes'], 2)
        self.assertEqual(len(data['par_cle']), 1)
        self.assertEqual(data['par_cle'][0]['label'], 'pro')

    def test_records_isolated_by_company(self):
        key_other = _make_api_key(self.other)
        api_usage.enregistrer_usage(key_other)
        data = api_usage.analytics(self.company)
        self.assertEqual(data['total_requetes'], 0)


class ApiUsagePlanViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.admin = User.objects.create_user(
            username='au_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='au_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_get_plan_creates_default(self):
        req = self.factory.get('/api-usage/plan/')
        force_authenticate(req, user=self.user)
        resp = ApiUsagePlanViewSet.as_view({'get': 'plan'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['code'], 'gratuit')

    def test_put_plan_requires_admin(self):
        req = self.factory.put('/api-usage/plan/', {'quota_par_jour': 5},
                               format='json')
        force_authenticate(req, user=self.user)
        resp = ApiUsagePlanViewSet.as_view({'put': 'plan'})(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_plan_updates_singleton(self):
        req = self.factory.put('/api-usage/plan/', {'quota_par_jour': 5},
                               format='json')
        force_authenticate(req, user=self.admin)
        resp = ApiUsagePlanViewSet.as_view({'put': 'plan'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['quota_par_jour'], 5)
        plan = api_usage.plan_pour_societe(self.company)
        self.assertEqual(plan.quota_par_jour, 5)

    def test_patch_plan_refuse_palier_responsable(self):
        """APFS41 (C-APFS-040, D-APFS-1) — le plan de quotas est réservé au
        palier administrateur : le palier « responsable » reçoit 403, plan
        inchangé ; Directeur et Administrateur 200."""
        from django.core.management import call_command
        Role = django_apps.get_model('roles', 'Role')  # core n'importe aucune app
        call_command('init_roles', verbosity=0)
        roles = {r.nom: r for r in Role.objects.filter(company=self.company)}
        avant = api_usage.plan_pour_societe(self.company)

        def patch(nom):
            user = User.objects.create_user(
                username=f'apfs41_{nom.replace(" ", "_").lower()}', password='x',
                company=self.company, role=roles[nom])
            req = self.factory.patch('/api-usage/plan/', {
                'quota_par_jour': 0, 'actif': False}, format='json')
            force_authenticate(req, user=user)
            return ApiUsagePlanViewSet.as_view({'patch': 'plan'})(req)
        for nom in ('Responsable', 'Admin RH', 'Admin Ventes', 'Technicien responsable',
                    'Commercial responsable', 'Commercial'):
            with self.subTest(role=nom):
                self.assertEqual(patch(nom).status_code, status.HTTP_403_FORBIDDEN)
                plan = api_usage.plan_pour_societe(self.company)
                self.assertEqual((plan.actif, plan.quota_par_jour), (avant.actif, avant.quota_par_jour))
        for nom in ('Directeur', 'Administrateur'):
            with self.subTest(role=nom):
                self.assertEqual(patch(nom).status_code, status.HTTP_200_OK)
