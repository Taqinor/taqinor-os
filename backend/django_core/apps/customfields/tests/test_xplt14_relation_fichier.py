"""XPLT14 — types RELATION/FICHIER + couverture fournisseur/employé."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.customfields.models import CustomFieldDef
from apps.customfields.serializers import validate_custom_data
from apps.rh.models import DossierEmploye
from apps.stock.models import Fournisseur, Produit
from authentication.models import Company

User = get_user_model()


class CF14Base(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cf14-co', defaults={'nom': 'CF14 Co'})[0]
        self.admin = User.objects.create_user(
            username='cf14_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestRelationFieldDefinition(CF14Base):
    def test_relation_requires_target_module(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'apporteur', 'libelle': 'Apporteur',
            'type': 'relation',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('relation_module', resp.data)

    def test_relation_unknown_target_module_rejected(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'apporteur', 'libelle': 'Apporteur',
            'type': 'relation', 'relation_module': 'bidule',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_relation_with_target_module_accepted(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'apporteur', 'libelle': 'Apporteur',
            'type': 'relation', 'relation_module': 'client',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['relation_module'], 'client')


class TestRelationValueValidation(CF14Base):
    def test_relation_resolves_id_and_denormalizes_label(self):
        from apps.crm.models import Client
        client = Client.objects.create(company=self.company, nom='Client X')
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='apporteur',
            libelle='Apporteur', type='relation', relation_module='client')
        clean = validate_custom_data(
            'lead', self.company, {'apporteur': client.id})
        self.assertEqual(clean['apporteur']['id'], client.id)
        self.assertEqual(clean['apporteur']['label'], 'Client X')

    def test_relation_accepts_already_resolved_dict(self):
        from apps.crm.models import Client
        client = Client.objects.create(company=self.company, nom='Client Y')
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='apporteur',
            libelle='Apporteur', type='relation', relation_module='client')
        clean = validate_custom_data(
            'lead', self.company,
            {'apporteur': {'id': client.id, 'label': 'stale label'}})
        # Le libellé est re-résolu (jamais fait confiance à l'entrée telle
        # quelle) — toujours dénormalisé depuis l'enregistrement réel.
        self.assertEqual(clean['apporteur']['label'], 'Client Y')

    def test_relation_unknown_id_rejected(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='apporteur',
            libelle='Apporteur', type='relation', relation_module='client')
        with self.assertRaises(ValidationError):
            validate_custom_data('lead', self.company, {'apporteur': 999999})

    def test_relation_cross_tenant_id_rejected(self):
        from apps.crm.models import Client
        other = Company.objects.create(slug='cf14-other', nom='Autre Co')
        other_client = Client.objects.create(company=other, nom='Client autre')
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='apporteur',
            libelle='Apporteur', type='relation', relation_module='client')
        with self.assertRaises(ValidationError):
            validate_custom_data(
                'lead', self.company, {'apporteur': other_client.id})


class TestFichierFieldValidation(CF14Base):
    def test_fichier_accepts_already_uploaded_dict(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='piece',
            libelle='Pièce jointe', type='fichier')
        stored = {'file_key': 'attachments/x.pdf', 'filename': 'x.pdf',
                  'size': 100, 'mime': 'application/pdf'}
        clean = validate_custom_data(
            'lead', self.company, {'piece': stored})
        self.assertEqual(clean['piece'], stored)

    def test_fichier_rejects_dict_without_file_key(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='piece',
            libelle='Pièce jointe', type='fichier')
        with self.assertRaises(ValidationError):
            validate_custom_data('lead', self.company, {'piece': {}})

    def test_fichier_uploads_raw_file_via_store_attachment(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='piece',
            libelle='Pièce jointe', type='fichier')
        stored = {'file_key': 'attachments/y.pdf', 'filename': 'y.pdf',
                  'size': 5, 'mime': 'application/pdf'}
        with patch('apps.records.storage.store_attachment',
                   return_value=(stored, None)) as mock_store:
            clean = validate_custom_data(
                'lead', self.company,
                {'piece': type('F', (), {'read': lambda self: b''})()})
        self.assertTrue(mock_store.called)
        self.assertEqual(clean['piece'], stored)

    def test_fichier_store_error_propagates_as_validation_error(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='piece',
            libelle='Pièce jointe', type='fichier')
        with patch('apps.records.storage.store_attachment',
                   return_value=(None, 'Format non supporté.')):
            with self.assertRaises(ValidationError):
                validate_custom_data(
                    'lead', self.company,
                    {'piece': type('F', (), {'read': lambda self: b''})()})


class TestFournisseurEmployeModuleCoverage(CF14Base):
    """Nouveaux modules acceptent des définitions ; custom_data se filtre en
    liste (isolation tenant testée via company-scoping standard)."""

    def test_fournisseur_module_choice_accepted(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'fournisseur', 'code': 'delai_livraison',
            'libelle': 'Délai de livraison (j)', 'type': 'number',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_fournisseur_custom_data_field_exists(self):
        field = Fournisseur._meta.get_field('custom_data')
        from django.db import models as db_models
        self.assertIsInstance(field, db_models.JSONField)
        self.assertTrue(field.null)

    def test_fournisseur_custom_data_validated_and_stored(self):
        CustomFieldDef.objects.create(
            company=self.company, module='fournisseur', code='note_qualite',
            libelle='Note qualité', type='number', obligatoire=True)
        clean = validate_custom_data(
            'fournisseur', self.company, {'note_qualite': 8})
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four X', custom_data=clean)
        self.assertEqual(fournisseur.custom_data['note_qualite'], 8.0)

    def test_employe_module_choice_accepted(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'employe', 'code': 'permis_conduire',
            'libelle': 'Permis de conduire', 'type': 'boolean',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_employe_custom_data_field_exists(self):
        field = DossierEmploye._meta.get_field('custom_data')
        from django.db import models as db_models
        self.assertIsInstance(field, db_models.JSONField)
        self.assertTrue(field.null)

    def test_relation_pointing_to_produit_module(self):
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='CF14-P1',
            prix_vente=100)
        CustomFieldDef.objects.create(
            company=self.company, module='fournisseur', code='produit_phare',
            libelle='Produit phare', type='relation', relation_module='produit')
        clean = validate_custom_data(
            'fournisseur', self.company, {'produit_phare': produit.id})
        self.assertEqual(clean['produit_phare']['label'], 'Panneau')
