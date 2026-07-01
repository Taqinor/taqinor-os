"""Tests FG393 — éditeur de modèles imprimables/brandés + rendu sûr.

Couvre :
  * moteur ``core.templating`` : substitution littérale, nested, inconnu vide,
    mode strict, détection des variables ;
  * pas d'exécution de code (un placeholder « malicieux » reste littéral) ;
  * endpoint : écriture admin-only, lecture ouverte, company imposée,
    preview rend avec contexte, isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import templating
from core.models import BrandedTemplate
from core.views import BrandedTemplateViewSet

User = get_user_model()


class TemplatingEngineTests(SimpleTestCase):
    def test_literal_substitution(self):
        out = templating.rendre('Bonjour {{ nom }}', {'nom': 'Reda'})
        self.assertEqual(out, 'Bonjour Reda')

    def test_nested_lookup(self):
        out = templating.rendre('{{ client.ville }}',
                                {'client': {'ville': 'Casa'}})
        self.assertEqual(out, 'Casa')

    def test_unknown_blank_or_strict(self):
        self.assertEqual(templating.rendre('x={{ y }}', {}), 'x=')
        self.assertEqual(
            templating.rendre('x={{ y }}', {}, strict=True), 'x={{ y }}')

    def test_no_code_execution(self):
        # Un placeholder non conforme n'est pas un appel : laissé tel quel.
        out = templating.rendre("{{ __import__('os') }}", {})
        self.assertEqual(out, "{{ __import__('os') }}")

    def test_variables_detected(self):
        vs = templating.variables_utilisees('{{ a }} {{ b }} {{ a }}')
        self.assertEqual(vs, ['a', 'b'])


class BrandedTemplateViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.admin = User.objects.create_user(
            username='tpl_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='tpl_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_create_requires_admin_tier(self):
        body = {'kind': 'email', 'code': 'relance', 'nom': 'Relance',
                'corps': 'Bonjour {{ nom }}'}
        req = self.factory.post('/branded-templates/', body, format='json')
        force_authenticate(req, user=self.user)
        resp = BrandedTemplateViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_imposes_company_and_exposes_variables(self):
        body = {'kind': 'email', 'code': 'relance', 'nom': 'Relance',
                'corps': 'Bonjour {{ nom }}'}
        req = self.factory.post('/branded-templates/', body, format='json')
        force_authenticate(req, user=self.admin)
        resp = BrandedTemplateViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        tpl = BrandedTemplate.objects.get(pk=resp.data['id'])
        self.assertEqual(tpl.company, self.company)
        self.assertIn('nom', resp.data['variables'])

    def test_preview_renders_with_context(self):
        tpl = BrandedTemplate.objects.create(
            company=self.company, kind='email', code='r', nom='R',
            sujet='Devis {{ ref }}', corps='Bonjour {{ nom }}')
        req = self.factory.post(
            f'/branded-templates/{tpl.pk}/preview/',
            {'context': {'ref': 'D-1', 'nom': 'Reda'}}, format='json')
        force_authenticate(req, user=self.admin)
        resp = BrandedTemplateViewSet.as_view({'post': 'preview'})(req, pk=tpl.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['sujet'], 'Devis D-1')
        self.assertEqual(resp.data['corps'], 'Bonjour Reda')

    def test_list_company_isolation(self):
        BrandedTemplate.objects.create(
            company=self.other, kind='email', code='x', nom='Secret')
        req = self.factory.get('/branded-templates/')
        force_authenticate(req, user=self.user)
        resp = BrandedTemplateViewSet.as_view({'get': 'list'})(req)
        noms = {row['nom'] for row in resp.data}
        self.assertNotIn('Secret', noms)
