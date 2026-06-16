"""Tests du mécanisme de champs personnalisés (T11).

Couvre : CRUD des définitions + scoping société, validation des valeurs par
type, obligatoire, rejet hors-liste pour 'choice', masquage standard +
réinitialisation, et round-trip custom_fields sur lead/client/produit.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.customfields.models import (
    CustomFieldDefinition, HiddenStandardField,
)
from apps.customfields.services import validate_custom_fields, derive_field_key

User = get_user_model()


def make_company(slug, nom=None):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom or slug})
    return company


def admin_client(company, username):
    user = User.objects.create_user(
        username=username, password='x', role_legacy='admin', company=company)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def member_client(company, username):
    user = User.objects.create_user(
        username=username, password='x', role_legacy='responsable',
        company=company)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDefinitionCRUD(TestCase):
    def setUp(self):
        self.company = make_company('cf-co')
        self.admin = admin_client(self.company, 'cf_admin')

    def test_create_derives_field_key(self):
        r = self.admin.post('/api/django/customfields/definitions/', {
            'module': 'lead', 'label': 'Numéro de compteur ONEE',
            'field_type': 'text',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['field_key'], 'numero_de_compteur_onee')

    def test_field_key_not_taken_from_body(self):
        r = self.admin.post('/api/django/customfields/definitions/', {
            'module': 'lead', 'label': 'Mon champ', 'field_type': 'text',
            'field_key': 'INJECTED',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotEqual(r.data['field_key'], 'INJECTED')

    def test_choice_requires_options(self):
        r = self.admin.post('/api/django/customfields/definitions/', {
            'module': 'lead', 'label': 'Statut toit', 'field_type': 'choice',
            'choices': [],
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_company_is_forced_server_side(self):
        r = self.admin.post('/api/django/customfields/definitions/', {
            'module': 'client', 'label': 'X', 'field_type': 'text',
            'company': 999,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        d = CustomFieldDefinition.objects.get(id=r.data['id'])
        self.assertEqual(d.company_id, self.company.id)

    def test_non_admin_cannot_write(self):
        member = member_client(self.company, 'cf_member')
        r = member.post('/api/django/customfields/definitions/', {
            'module': 'lead', 'label': 'X', 'field_type': 'text',
        }, format='json')
        self.assertIn(r.status_code, (403, 401))

    def test_member_can_read_definitions(self):
        CustomFieldDefinition.objects.create(
            company=self.company, module='lead', field_key='a', label='A',
            field_type='text')
        member = member_client(self.company, 'cf_reader')
        r = member.get('/api/django/customfields/definitions/?module=lead')
        self.assertEqual(r.status_code, 200)


class TestDefinitionScoping(TestCase):
    def test_definitions_scoped_to_company(self):
        c1 = make_company('cf-a')
        c2 = make_company('cf-b')
        CustomFieldDefinition.objects.create(
            company=c1, module='lead', field_key='mine', label='Mine',
            field_type='text')
        CustomFieldDefinition.objects.create(
            company=c2, module='lead', field_key='theirs', label='Theirs',
            field_type='text')
        api = admin_client(c1, 'scope_admin')
        r = api.get('/api/django/customfields/definitions/')
        keys = [d['field_key'] for d in r.data.get('results', r.data)]
        self.assertIn('mine', keys)
        self.assertNotIn('theirs', keys)

    def test_schema_scoped_and_lists_hidden(self):
        c1 = make_company('cf-sch')
        CustomFieldDefinition.objects.create(
            company=c1, module='lead', field_key='extra', label='Extra',
            field_type='text')
        HiddenStandardField.objects.create(
            company=c1, module='lead', field_key='fbclid')
        api = admin_client(c1, 'sch_admin')
        r = api.get('/api/django/customfields/schema/lead/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            [d['field_key'] for d in r.data['definitions']], ['extra'])
        self.assertEqual(r.data['hidden_standard'], ['fbclid'])


class TestValueValidation(TestCase):
    def setUp(self):
        self.company = make_company('cf-val')

    def _def(self, field_type, **kw):
        return CustomFieldDefinition.objects.create(
            company=self.company, module='lead',
            field_key=kw.pop('field_key', field_type + '_f'),
            label=kw.pop('label', 'L'), field_type=field_type, **kw)

    def test_text(self):
        self._def('text', field_key='t')
        out = validate_custom_fields(self.company, 'lead', {'t': 'hello'})
        self.assertEqual(out['t'], 'hello')

    def test_number_valid_and_invalid(self):
        self._def('number', field_key='n')
        out = validate_custom_fields(self.company, 'lead', {'n': '12.5'})
        self.assertEqual(out['n'], 12.5)
        with self.assertRaises(ValueError):
            validate_custom_fields(self.company, 'lead', {'n': 'abc'})

    def test_boolean(self):
        self._def('boolean', field_key='b')
        out = validate_custom_fields(self.company, 'lead', {'b': 'oui'})
        self.assertIs(out['b'], True)
        out = validate_custom_fields(self.company, 'lead', {'b': False})
        self.assertIs(out['b'], False)

    def test_date_valid_and_invalid(self):
        self._def('date', field_key='d')
        out = validate_custom_fields(self.company, 'lead', {'d': '2026-06-16'})
        self.assertEqual(out['d'], '2026-06-16')
        with self.assertRaises(ValueError):
            validate_custom_fields(self.company, 'lead', {'d': '16/06/2026'})

    def test_choice_membership(self):
        self._def('choice', field_key='c', choices=['A', 'B'])
        out = validate_custom_fields(self.company, 'lead', {'c': 'A'})
        self.assertEqual(out['c'], 'A')
        with self.assertRaises(ValueError):
            validate_custom_fields(self.company, 'lead', {'c': 'Z'})

    def test_required_enforced(self):
        self._def('text', field_key='r', required=True)
        with self.assertRaises(ValueError):
            validate_custom_fields(self.company, 'lead', {})

    def test_unknown_keys_ignored(self):
        self._def('text', field_key='known')
        out = validate_custom_fields(
            self.company, 'lead', {'known': 'x', 'ghost': 'y'})
        self.assertNotIn('ghost', out)

    def test_partial_does_not_require_absent(self):
        self._def('text', field_key='req', required=True)
        # PATCH partiel : req absent ne lève pas, fusionne l'existant.
        out = validate_custom_fields(
            self.company, 'lead', {}, existing={'req': 'old'}, partial=True)
        self.assertEqual(out['req'], 'old')

    def test_derive_field_key_collision(self):
        CustomFieldDefinition.objects.create(
            company=self.company, module='lead', field_key='dup', label='L',
            field_type='text')
        key = derive_field_key('dup', self.company, 'lead')
        self.assertEqual(key, 'dup_2')


class TestHideRestore(TestCase):
    def setUp(self):
        self.company = make_company('cf-hide')
        self.admin = admin_client(self.company, 'hide_admin')

    def test_hide_standard_field(self):
        r = self.admin.post('/api/django/customfields/hidden-fields/', {
            'module': 'lead', 'field_key': 'fbclid',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(HiddenStandardField.objects.filter(
            company=self.company, module='lead', field_key='fbclid').exists())

    def test_restore_defaults_unhides_and_archives(self):
        HiddenStandardField.objects.create(
            company=self.company, module='lead', field_key='fbclid')
        d = CustomFieldDefinition.objects.create(
            company=self.company, module='lead', field_key='x', label='X',
            field_type='text', active=True)
        r = self.admin.post('/api/django/customfields/restore/lead/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(HiddenStandardField.objects.filter(
            company=self.company, module='lead').exists())
        d.refresh_from_db()
        self.assertFalse(d.active)  # archivé, pas supprimé
        self.assertTrue(CustomFieldDefinition.objects.filter(id=d.id).exists())

    def test_reorder(self):
        a = CustomFieldDefinition.objects.create(
            company=self.company, module='lead', field_key='a', label='A',
            field_type='text', order=0)
        b = CustomFieldDefinition.objects.create(
            company=self.company, module='lead', field_key='b', label='B',
            field_type='text', order=1)
        r = self.admin.post('/api/django/customfields/definitions/reorder/',
                            {'ids': [b.id, a.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(b.order, 0)
        self.assertEqual(a.order, 1)


class TestRoundTrip(TestCase):
    def setUp(self):
        self.company = make_company('cf-rt')
        self.admin = admin_client(self.company, 'rt_admin')

    def test_lead_round_trip(self):
        CustomFieldDefinition.objects.create(
            company=self.company, module='lead', field_key='compteur',
            label='Compteur', field_type='text')
        r = self.admin.post('/api/django/crm/leads/', {
            'nom': 'Lead CF', 'custom_fields': {'compteur': 'C-123'},
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        lead = Lead.objects.get(nom='Lead CF')
        self.assertEqual(lead.custom_fields['compteur'], 'C-123')
        self.assertEqual(r.data['custom_fields']['compteur'], 'C-123')

    def test_lead_rejects_bad_choice(self):
        CustomFieldDefinition.objects.create(
            company=self.company, module='lead', field_key='toit',
            label='Toit', field_type='choice', choices=['Plat', 'Incliné'])
        r = self.admin.post('/api/django/crm/leads/', {
            'nom': 'Lead Bad', 'custom_fields': {'toit': 'Rond'},
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_client_round_trip(self):
        CustomFieldDefinition.objects.create(
            company=self.company, module='client', field_key='fidelite',
            label='Fidélité', field_type='number')
        r = self.admin.post('/api/django/crm/clients/', {
            'nom': 'Client CF', 'email': 'cf@example.com',
            'custom_fields': {'fidelite': 5},
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        c = Client.objects.get(email='cf@example.com')
        self.assertEqual(c.custom_fields['fidelite'], 5)

    def test_produit_round_trip(self):
        CustomFieldDefinition.objects.create(
            company=self.company, module='produit', field_key='origine',
            label='Origine', field_type='text')
        # company est forcée côté serveur (perform_create) ; le sérialiseur
        # Produit l'exige toutefois dans le corps (quirk DRF FK pré-existant),
        # on l'envoie null — elle est de toute façon écrasée par la société.
        r = self.admin.post('/api/django/stock/produits/', {
            'nom': 'Panneau CF', 'sku': 'CF-PAN-1', 'prix_vente': '1000.00',
            'company': None, 'custom_fields': {'origine': 'Chine'},
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        p = Produit.objects.get(sku='CF-PAN-1')
        self.assertEqual(p.custom_fields['origine'], 'Chine')
