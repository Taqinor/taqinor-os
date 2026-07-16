"""ENG30 — Audit multi-tenant du moteur publicitaire.

Vérifie que TOUS les modèles ENG portent une FK ``company`` (via
``core.TenantModel``) vers ``authentication.Company`` et que tous les ViewSets
inscriptibles sont scopés société (``CompanyScopedModelViewSet``). Un modèle ou
un viewset non scopé ajouté par mégarde fait échouer ce test — jamais de pooling
de données entre clients (voir ``docs/adsengine-tenant-onboarding.md``).
"""
import inspect

from django.apps import apps as django_apps
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine.models import AdCampaignMirror, EngineAction


class ModelTenancyAuditTests(SimpleTestCase):
    def _models(self):
        return list(django_apps.get_app_config('adsengine').get_models())

    def test_every_model_inherits_tenant_model(self):
        from core.models import TenantModel
        models = self._models()
        self.assertTrue(models)  # l'app a bien des modèles
        for model in models:
            self.assertTrue(
                issubclass(model, TenantModel),
                f'{model.__name__} doit hériter de core.TenantModel')

    def test_every_model_has_company_fk_to_company(self):
        for model in self._models():
            field = model._meta.get_field('company')
            self.assertTrue(field.is_relation, model.__name__)
            self.assertEqual(
                field.related_model, Company,
                f'{model.__name__}.company doit pointer authentication.Company')


class ViewSetTenancyAuditTests(SimpleTestCase):
    def test_every_writable_viewset_is_company_scoped(self):
        from rest_framework.viewsets import ModelViewSet

        from core.viewsets import CompanyScopedModelViewSet
        from apps.adsengine import views

        checked = 0
        for name, obj in inspect.getmembers(views, inspect.isclass):
            if obj.__module__ != views.__name__:
                continue
            if issubclass(obj, ModelViewSet) and obj is not ModelViewSet:
                self.assertTrue(
                    issubclass(obj, CompanyScopedModelViewSet),
                    f'{name} doit hériter de CompanyScopedModelViewSet')
                checked += 1
        self.assertGreater(checked, 0)


class FunctionalIsolationTests(TestCase):
    def test_query_scoped_by_company_never_leaks(self):
        a = Company.objects.create(nom='A', slug='a-tn')
        b = Company.objects.create(nom='B', slug='b-tn')
        AdCampaignMirror.objects.create(
            company=a, meta_id='ca', name='CA', status='PAUSED')
        AdCampaignMirror.objects.create(
            company=b, meta_id='cb', name='CB', status='PAUSED')
        EngineAction.objects.create(
            company=a, kind=EngineAction.Kind.CREATE_CAMPAIGN,
            reason_fr='x', payload={})
        # Un scope par société ne voit jamais les données de l'autre.
        self.assertEqual(
            AdCampaignMirror.objects.filter(company=a).count(), 1)
        self.assertEqual(
            EngineAction.objects.filter(company=b).count(), 0)
