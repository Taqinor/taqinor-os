"""ARC14 — registre data-driven des modules customfieldables.

Couvre : (1) non-régression des 8 clés natives historiques (elles résolvent
toujours vers le bon modèle et leurs données existantes restent lisibles) ;
(2) l'API du registre lui-même (register/is_registered/get_model) ; (3) les 2
pilotes ``contrats.contrat`` et ``flotte.vehicule`` — un champ personnalisé
créé, écrit puis lu via l'API existante de ``apps.customfields``, scopé
société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.customfields import registry
from apps.customfields.models import CustomFieldDef
from apps.customfields.serializers import _module_model
from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestNativeModulesNonRegression(TestCase):
    """Les 8 clés natives historiques (Module.LEAD..EMPLOYE) résolvent
    toujours vers le même modèle après le passage au registre — le
    comportement de ``_module_model`` est inchangé pour les appelants
    existants."""

    def test_all_eight_native_keys_registered(self):
        for key in CustomFieldDef.Module.values:
            self.assertTrue(
                registry.is_registered(key),
                f'Clé native « {key} » absente du registre.')

    def test_native_keys_resolve_to_expected_models(self):
        from apps.crm.models import Client, Lead
        from apps.ged.models import Document
        from apps.installations.models import Installation
        from apps.rh.models import DossierEmploye
        from apps.sav.models import Ticket
        from apps.stock.models import Fournisseur, Produit
        from apps.ventes.models import Devis

        expected = {
            'lead': Lead,
            'client': Client,
            'produit': Produit,
            'devis': Devis,
            'installation': Installation,
            'ticket': Ticket,
            'document': Document,
            'fournisseur': Fournisseur,
            'employe': DossierEmploye,
        }
        for key, model in expected.items():
            self.assertIs(_module_model(key), model,
                          f'Module « {key} » ne résout plus vers {model}.')

    def test_existing_lead_custom_data_still_readable(self):
        """Une définition + donnée custom_data posée sur un module natif
        (lead) reste lisible/validée à l'identique après ARC14."""
        from apps.crm.models import Lead
        from apps.customfields.serializers import validate_custom_data

        company = make_company('arc14-native', 'ARC14 Native Co')
        CustomFieldDef.objects.create(
            company=company, module='lead', code='budget',
            libelle='Budget', type='number', obligatoire=False)
        lead = Lead.objects.create(
            company=company, nom='Lead existant',
            custom_data={'budget': 42000})
        lead.refresh_from_db()
        self.assertEqual(lead.custom_data.get('budget'), 42000)
        # Re-validation via le même chemin que l'API (non-régression du
        # comportement de validation, pas seulement de la lecture brute).
        clean = validate_custom_data('lead', company, {'budget': 42000})
        self.assertEqual(clean.get('budget'), 42000)


class TestRegistryApi(TestCase):
    """Comportement de base du registre lui-même."""

    def test_unknown_module_returns_none(self):
        self.assertIsNone(registry.get_model('module_inexistant_xyz'))
        self.assertFalse(registry.is_registered('module_inexistant_xyz'))

    def test_register_is_idempotent_for_same_target(self):
        registry.register('_arc14_test_key', 'crm', 'Lead')
        registry.register('_arc14_test_key', 'crm', 'Lead')  # no-op, no raise
        self.assertTrue(registry.is_registered('_arc14_test_key'))

    def test_register_conflicting_target_raises(self):
        registry.register('_arc14_conflict_key', 'crm', 'Lead')
        with self.assertRaises(ValueError):
            registry.register('_arc14_conflict_key', 'crm', 'Client')

    def test_pilots_registered_by_app_ready(self):
        """contrats et flotte sont enregistrés au démarrage Django — donc déjà
        présents ici (ARC31 : désormais via le chargeur central
        ``CustomfieldsConfig.ready()`` qui lit leurs manifestes ``platform.py``,
        plus depuis un ``registry.register()`` explicite dans leur propre
        ``AppConfig.ready()`` — même résultat, source différente)."""
        from apps.contrats.models import Contrat
        from apps.flotte.models import Vehicule
        self.assertTrue(registry.is_registered('contrat'))
        self.assertTrue(registry.is_registered('vehicule'))
        self.assertIs(registry.get_model('contrat'), Contrat)
        self.assertIs(registry.get_model('vehicule'), Vehicule)


class TestContratPilot(TestCase):
    """Pilote 1/2 — un champ personnalisé sur ``contrats.Contrat`` créé,
    écrit et lu via l'API existante de ``apps.customfields``."""

    def setUp(self):
        self.company = make_company('arc14-contrat', 'ARC14 Contrat Co')
        # role_legacy='admin' (pas 'responsable') : le test crée AUSSI la
        # CustomFieldDef via l'API, gardée par IsAdminRole (repli legacy
        # is_admin_role exige role_legacy == ROLE_ADMIN) — 'responsable' n'y
        # suffit pas, alors que 'admin' satisfait aussi le repli legacy
        # contrat_gerer (is_responsable est vrai pour ADMIN et RESPONSABLE).
        self.admin = User.objects.create_user(
            username='arc14-contrat-admin', password='x',
            company=self.company, role_legacy='admin')
        self.api = auth(self.admin)

    def test_definition_created_for_contrat_module(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'contrat', 'code': 'dossier_juridique',
            'libelle': 'Dossier juridique', 'type': 'text',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(CustomFieldDef.objects.filter(
            company=self.company, module='contrat',
            code='dossier_juridique').exists())

    def test_custom_field_written_and_read_via_contrat_api(self):
        CustomFieldDef.objects.create(
            company=self.company, module='contrat', code='dossier_juridique',
            libelle='Dossier juridique', type='text', obligatoire=True)
        # Manquant → 400 (champ personnalisé obligatoire non fourni).
        missing = self.api.post('/api/django/contrats/contrats/', {
            'objet': 'Contrat sans dossier',
        }, format='json')
        self.assertEqual(missing.status_code, 400, missing.data)
        # Fourni → créé et persisté.
        created = self.api.post('/api/django/contrats/contrats/', {
            'objet': 'Contrat avec dossier',
            'custom_data': {'dossier_juridique': 'DJ-2026-001'},
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        from apps.contrats.models import Contrat
        contrat = Contrat.objects.get(id=created.data['id'])
        self.assertEqual(
            contrat.custom_data.get('dossier_juridique'), 'DJ-2026-001')
        # Relu via l'API (GET).
        got = self.api.get(f'/api/django/contrats/contrats/{contrat.id}/')
        self.assertEqual(got.status_code, 200, got.data)
        self.assertEqual(
            got.data['custom_data'].get('dossier_juridique'), 'DJ-2026-001')

    def test_custom_field_is_company_scoped(self):
        """Une définition posée sur la société A n'affecte pas la société B
        (pas de fuite cross-tenant du registre)."""
        other_company = make_company('arc14-contrat-b', 'ARC14 Contrat B')
        other_admin = User.objects.create_user(
            username='arc14-contrat-admin-b', password='x',
            company=other_company, role_legacy='responsable')
        other_api = auth(other_admin)

        CustomFieldDef.objects.create(
            company=self.company, module='contrat', code='dossier_juridique',
            libelle='Dossier juridique', type='text', obligatoire=True)
        # La société B n'a pas cette définition obligatoire → création libre.
        resp = other_api.post('/api/django/contrats/contrats/', {
            'objet': 'Contrat société B sans dossier',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestVehiculePilot(TestCase):
    """Pilote 2/2 — un champ personnalisé sur ``flotte.Vehicule`` créé,
    écrit et lu via l'API existante de ``apps.customfields``."""

    def setUp(self):
        self.company = make_company('arc14-vehicule', 'ARC14 Vehicule Co')
        self.admin = User.objects.create_user(
            username='arc14-vehicule-admin', password='x',
            company=self.company, role_legacy='admin')
        self.api = auth(self.admin)

    def test_definition_created_for_vehicule_module(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'vehicule', 'code': 'numero_flotte_interne',
            'libelle': 'N° flotte interne', 'type': 'text',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(CustomFieldDef.objects.filter(
            company=self.company, module='vehicule',
            code='numero_flotte_interne').exists())

    def test_custom_field_written_and_read_via_vehicule_api(self):
        CustomFieldDef.objects.create(
            company=self.company, module='vehicule',
            code='numero_flotte_interne', libelle='N° flotte interne',
            type='text', obligatoire=True)
        missing = self.api.post('/api/django/flotte/vehicules/', {
            'immatriculation': '1111-A-11', 'marque': 'Renault',
            'modele': 'Kangoo', 'energie': 'diesel',
        }, format='json')
        self.assertEqual(missing.status_code, 400, missing.data)
        created = self.api.post('/api/django/flotte/vehicules/', {
            'immatriculation': '2222-B-22', 'marque': 'Renault',
            'modele': 'Kangoo', 'energie': 'diesel',
            'custom_data': {'numero_flotte_interne': 'FL-042'},
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        from apps.flotte.models import Vehicule
        vehicule = Vehicule.objects.get(id=created.data['id'])
        self.assertEqual(
            vehicule.custom_data.get('numero_flotte_interne'), 'FL-042')
        got = self.api.get(f'/api/django/flotte/vehicules/{vehicule.id}/')
        self.assertEqual(got.status_code, 200, got.data)
        self.assertEqual(
            got.data['custom_data'].get('numero_flotte_interne'), 'FL-042')

    def test_custom_field_is_company_scoped(self):
        other_company = make_company('arc14-vehicule-b', 'ARC14 Vehicule B')
        other_admin = User.objects.create_user(
            username='arc14-vehicule-admin-b', password='x',
            company=other_company, role_legacy='admin')
        other_api = auth(other_admin)

        CustomFieldDef.objects.create(
            company=self.company, module='vehicule',
            code='numero_flotte_interne', libelle='N° flotte interne',
            type='text', obligatoire=True)
        resp = other_api.post('/api/django/flotte/vehicules/', {
            'immatriculation': '3333-C-33', 'marque': 'Renault',
            'modele': 'Kangoo', 'energie': 'diesel',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
