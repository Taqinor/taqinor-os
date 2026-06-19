"""L808/L814/L815/L816/L818 — câblage validate_custom_data (produit/client),
protection du renommage de code, validation date/choice, et audit.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.customfields.models import CustomFieldDef
from apps.customfields.serializers import validate_custom_data
from apps.parametres.models import SettingsAuditLog
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


class CFWiringBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cfw-co', defaults={'nom': 'CFW Co'})[0]
        self.admin = User.objects.create_user(
            username='cfw_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestProduitClientWiring(CFWiringBase):
    """L808 — produit et client persistent leur custom_data via le même chemin
    de validation que Lead."""

    def test_produit_required_field_enforced_and_stored(self):
        CustomFieldDef.objects.create(
            company=self.company, module='produit', code='puissance',
            libelle='Puissance', type='number', obligatoire=True)
        # Manquant → 400 (sku + company fournis pour satisfaire l'unicité
        # (company, sku) ; seul le champ perso obligatoire manque).
        r1 = self.api.post(
            '/api/django/stock/produits/',
            {'nom': 'Panneau', 'prix_vente': '100', 'sku': 'CF-PAN-1',
             'company': self.company.id},
            format='json')
        self.assertEqual(r1.status_code, 400, r1.data)
        # Fourni → créé et stocké
        r2 = self.api.post(
            '/api/django/stock/produits/',
            {'nom': 'Panneau', 'prix_vente': '100', 'sku': 'CF-PAN-2',
             'company': self.company.id, 'custom_data': {'puissance': 550}},
            format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        prod = Produit.objects.get(id=r2.data['id'])
        self.assertEqual(prod.custom_data.get('puissance'), 550)

    def test_client_required_field_enforced_and_stored(self):
        CustomFieldDef.objects.create(
            company=self.company, module='client', code='secteur',
            libelle='Secteur', type='text', obligatoire=True)
        # email fourni (l'unicité (company, email) le rend obligatoire) ; seul
        # le champ perso obligatoire « secteur » manque → 400.
        r1 = self.api.post(
            '/api/django/crm/clients/',
            {'nom': 'Sans secteur', 'email': 'cf-secteur-1@example.invalid'},
            format='json')
        self.assertEqual(r1.status_code, 400, r1.data)
        r2 = self.api.post(
            '/api/django/crm/clients/',
            {'nom': 'Avec secteur', 'email': 'cf-secteur-2@example.invalid',
             'custom_data': {'secteur': 'Agricole'}},
            format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        client = Client.objects.get(id=r2.data['id'])
        self.assertEqual(client.custom_data.get('secteur'), 'Agricole')


class TestDateValidation(CFWiringBase):
    """L815 — le type 'date' rejette une valeur non-ISO."""

    def test_invalid_date_rejected(self):
        d = CustomFieldDef.objects.create(
            company=self.company, module='client', code='date_visite',
            libelle='Date de visite', type='date')
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_custom_data('client', self.company,
                                 {'date_visite': '31/12/2026'})
        # ISO accepté et normalisé
        clean = validate_custom_data('client', self.company,
                                     {'date_visite': '2026-12-31'})
        self.assertEqual(clean['date_visite'], '2026-12-31')
        self.assertEqual(d.type, 'date')


class TestChoiceOptionsRequired(CFWiringBase):
    """L816 — un champ choice sans options est refusé à la définition."""

    def test_choice_without_options_rejected(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'canal', 'libelle': 'Canal',
            'type': 'choice', 'options': [],
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('options', resp.data)

    def test_choice_with_options_accepted(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'canal', 'libelle': 'Canal',
            'type': 'choice', 'options': ['Facebook', 'Google'],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestCodeRenameProtection(CFWiringBase):
    """L814 — renommer code est bloqué dès qu'un enregistrement porte data."""

    def test_rename_blocked_when_data_exists(self):
        d = CustomFieldDef.objects.create(
            company=self.company, module='client', code='secteur',
            libelle='Secteur', type='text')
        Client.objects.create(company=self.company, nom='X',
                              custom_data={'secteur': 'Agricole'})
        resp = self.api.patch(
            f'/api/django/custom-fields/definitions/{d.id}/',
            {'code': 'secteur_v2'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('code', resp.data)

    def test_rename_allowed_when_no_data(self):
        d = CustomFieldDef.objects.create(
            company=self.company, module='client', code='secteur',
            libelle='Secteur', type='text')
        resp = self.api.patch(
            f'/api/django/custom-fields/definitions/{d.id}/',
            {'code': 'secteur_v2'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_libelle_edit_always_allowed(self):
        d = CustomFieldDef.objects.create(
            company=self.company, module='client', code='secteur',
            libelle='Secteur', type='text')
        Client.objects.create(company=self.company, nom='X',
                              custom_data={'secteur': 'Agricole'})
        resp = self.api.patch(
            f'/api/django/custom-fields/definitions/{d.id}/',
            {'libelle': 'Secteur d’activité'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class TestAuditLog(CFWiringBase):
    """L818 — create/delete d'une définition écrit une ligne d'audit."""

    def test_create_and_delete_logged(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'origine', 'libelle': 'Origine',
            'type': 'text',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(SettingsAuditLog.objects.filter(
            company=self.company, section='champs',
            field='lead.origine').exists())
        def_id = resp.data['id']
        self.api.delete(f'/api/django/custom-fields/definitions/{def_id}/')
        logs = SettingsAuditLog.objects.filter(
            company=self.company, section='champs', field='lead.origine')
        self.assertEqual(logs.count(), 2)


class TestReorder(CFWiringBase):
    """L813 — l'action reorder pose `ordre` selon la position."""

    def test_reorder_sets_ordre(self):
        a = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='a', libelle='A',
            type='text', ordre=0)
        b = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='b', libelle='B',
            type='text', ordre=1)
        resp = self.api.post(
            '/api/django/custom-fields/definitions/reorder/',
            {'ids': [b.id, a.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(b.ordre, 0)
        self.assertEqual(a.ordre, 1)
