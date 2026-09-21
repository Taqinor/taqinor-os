"""Tests API + sélecteur des liens contrat (``ContratLien``).

Couvre : société posée côté serveur (jamais du corps), garde-fou même-société
sur le ``contrat`` (un lien vers le contrat d'une AUTRE société est refusé 400),
isolation de la liste entre sociétés, filtres ``?contrat=``/``?type_cible=``,
404 cross-tenant, l'action ``contrats/{id}/liens/`` enrichie, et le sélecteur
``liens_enrichis`` — qui DÉGRADE proprement (libellé stocké, ``source='stored'``)
quand l'app cible n'expose pas de sélecteur (cas ``maintenance`` → sav sans
selectors.py) ou quand la cible est introuvable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors
from apps.contrats.models import Contrat, ContratLien

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ContratLienApiTests(TestCase):
    BASE = '/api/django/contrats/contrat-liens/'

    def setUp(self):
        self.co_a = make_company('contrat-liens-a', 'A')
        self.co_b = make_company('contrat-liens-b', 'B')
        self.user_a = make_user(self.co_a, 'contrat-liens-a')
        self.user_b = make_user(self.co_b, 'contrat-liens-b')
        self.contrat_a = Contrat.objects.create(
            company=self.co_a, objet='Contrat A')
        self.contrat_b = Contrat.objects.create(
            company=self.co_b, objet='Contrat B')

    def _payload(self, contrat, **over):
        data = {
            'contrat': contrat.id,
            'type_cible': 'maintenance',
            'cible_id': 42,
            'libelle': 'Maintenance #42',
        }
        data.update(over)
        return data

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.contrat_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ContratLien.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.contrat, self.contrat_a)
        self.assertEqual(obj.type_cible, 'maintenance')

    def test_create_ignores_company_in_body(self):
        api = auth(self.user_a)
        payload = self._payload(self.contrat_a, company=self.co_b.id)
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ContratLien.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_create_rejects_cross_tenant_contrat(self):
        # user A tries to link to company B's contract -> validation error.
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.contrat_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('contrat', resp.data)
        self.assertFalse(ContratLien.objects.filter(cible_id=42).exists())

    def test_list_isolation(self):
        ContratLien.objects.create(
            company=self.co_a, contrat=self.contrat_a,
            type_cible='devis', cible_id=7, libelle='D7')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_contrat_and_type(self):
        ContratLien.objects.create(
            company=self.co_a, contrat=self.contrat_a,
            type_cible='devis', cible_id=7, libelle='D7')
        ContratLien.objects.create(
            company=self.co_a, contrat=self.contrat_a,
            type_cible='lead', cible_id=8, libelle='L8')
        resp = auth(self.user_a).get(
            self.BASE + '?contrat=%d&type_cible=lead' % self.contrat_a.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['cible_id'], 8)

    def test_cross_tenant_detail_404(self):
        lien = ContratLien.objects.create(
            company=self.co_a, contrat=self.contrat_a,
            type_cible='devis', cible_id=5, libelle='D5')
        resp = auth(self.user_b).get(f'{self.BASE}{lien.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_contrat_liens_action_enriched(self):
        # The contrats/{id}/liens/ action returns enriched rows with a source.
        ContratLien.objects.create(
            company=self.co_a, contrat=self.contrat_a,
            type_cible='maintenance', cible_id=99, libelle='Maintenance stockée')
        url = f'/api/django/contrats/contrats/{self.contrat_a.id}/liens/'
        resp = auth(self.user_a).get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['type_cible'], 'maintenance')
        self.assertEqual(data[0]['libelle'], 'Maintenance stockée')
        self.assertEqual(data[0]['source'], 'stored')

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'contrat-liens-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class ContratLienSelectorTests(TestCase):
    """Le sélecteur d'enrichissement dégrade proprement sans app cible."""

    def setUp(self):
        self.co = make_company('contrat-liens-sel', 'S')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Contrat S')

    def test_enrichment_degrades_to_stored_label(self):
        # A 'maintenance' link: sav exposes no selectors.py -> stored label
        # kept, no import of another app's models, no crash.
        ContratLien.objects.create(
            company=self.co, contrat=self.contrat,
            type_cible='maintenance', cible_id=99, libelle='Maintenance stockée')
        result = selectors.liens_enrichis(self.contrat)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['type_cible'], 'maintenance')
        self.assertEqual(row['cible_id'], 99)
        self.assertEqual(row['libelle'], 'Maintenance stockée')
        self.assertEqual(row['source'], 'stored')

    def test_enrichment_devis_missing_target_degrades(self):
        # A 'devis' link whose target devis does not exist: ventes selector is
        # called but returns None -> degrade to stored label, never crash.
        ContratLien.objects.create(
            company=self.co, contrat=self.contrat,
            type_cible='devis', cible_id=123456, libelle='Devis stocké')
        result = selectors.liens_enrichis(self.contrat)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['type_cible'], 'devis')
        self.assertEqual(row['libelle'], 'Devis stocké')
        self.assertEqual(row['source'], 'stored')

    def test_enrichment_lead_and_installation_missing_target_degrade(self):
        # 'lead' (crm) and 'installation' (installations) selectors exist but
        # the targets are absent -> degrade to stored label, never crash.
        ContratLien.objects.create(
            company=self.co, contrat=self.contrat,
            type_cible='lead', cible_id=222222, libelle='Lead stocké')
        ContratLien.objects.create(
            company=self.co, contrat=self.contrat,
            type_cible='installation', cible_id=333333,
            libelle='Chantier stocké')
        result = selectors.liens_enrichis(self.contrat)
        by_type = {r['type_cible']: r for r in result}
        self.assertEqual(by_type['lead']['libelle'], 'Lead stocké')
        self.assertEqual(by_type['lead']['source'], 'stored')
        self.assertEqual(by_type['installation']['libelle'], 'Chantier stocké')
        self.assertEqual(by_type['installation']['source'], 'stored')

    def test_liens_for_contrat_is_company_scoped(self):
        ContratLien.objects.create(
            company=self.co, contrat=self.contrat,
            type_cible='installation', cible_id=5, libelle='Chantier 5')
        qs = selectors.liens_for_contrat(self.contrat)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().cible_id, 5)
