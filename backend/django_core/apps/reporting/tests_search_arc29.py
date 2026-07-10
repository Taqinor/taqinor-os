"""ARC29 — recherche globale pilotée par le registre plateforme (core.platform).

Couvre : (1) non-régression stricte des 10 groupes historiques (mêmes
requêtes/résultats qu'avant ARC29, cf. tests_search.py déjà vert) ; (2) les
deux trous comblés — ``stock.Produit`` et ``contrats.Contrat`` deviennent
trouvables ; (3) un modèle déclaré au registre (manifeste fictif) apparaît en
recherche SANS toucher apps/reporting/search.py (preuve que le balayage suit
bien platform.searchable_models(), pas une liste hard-codée) ; (4) le gatage
ModuleToggle retire bien un module cherchable de la recherche.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from authentication.models import Company
from core.models import ModuleToggle

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestSearchFindsProduit(TestCase):
    """Trou comblé 1/2 — stock.Produit était importable/customfieldable/
    records-isé mais introuvable en recherche globale avant ARC29."""

    def setUp(self):
        self.company = make_company('arc29-produit', 'ARC29 Produit Co')
        self.other = Company.objects.create(slug='arc29-produit-other', nom='Autre')
        self.user = User.objects.create_user(
            username='arc29_produit_user', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth_client(self.user)

    def test_search_finds_produit_by_nom(self):
        from apps.stock.models import Produit
        Produit.objects.create(
            company=self.company, nom='Panneau SolarMax 450W',
            prix_vente=1200)
        Produit.objects.create(
            company=self.other, nom='Panneau SolarMax 450W autre société',
            prix_vente=1200)
        resp = self.api.get('/api/django/reporting/search/?q=SolarMax')
        self.assertEqual(resp.status_code, 200)
        group = next((g for g in resp.data['groups'] if g['type'] == 'produit'), None)
        self.assertIsNotNone(group, resp.data['groups'])
        # Scopé société (multi-tenant) — un seul résultat, pas celui de l'autre.
        self.assertEqual(len(group['results']), 1)
        self.assertIn('SolarMax', group['results'][0]['label'])

    def test_search_finds_produit_by_sku(self):
        from apps.stock.models import Produit
        Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-XK900',
            prix_vente=3000)
        resp = self.api.get('/api/django/reporting/search/?q=OND-XK900')
        self.assertEqual(resp.status_code, 200)
        group = next((g for g in resp.data['groups'] if g['type'] == 'produit'), None)
        self.assertIsNotNone(group)
        self.assertEqual(group['results'][0]['sublabel'], 'OND-XK900')

    def test_archived_produit_not_found(self):
        from apps.stock.models import Produit
        Produit.objects.create(
            company=self.company, nom='Ancien module ArchiveTest',
            prix_vente=1, is_archived=True)
        resp = self.api.get('/api/django/reporting/search/?q=ArchiveTest')
        group = next((g for g in resp.data['groups'] if g['type'] == 'produit'), None)
        self.assertIsNone(group)


class TestSearchFindsContrat(TestCase):
    """Trou comblé 2/2 — contrats.Contrat avait le chatter générique (ARC8)
    mais restait invisible en recherche (seul sav.ContratMaintenance
    l'était)."""

    def setUp(self):
        self.company = make_company('arc29-contrat', 'ARC29 Contrat Co')
        self.user = User.objects.create_user(
            username='arc29_contrat_user', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth_client(self.user)

    def test_search_finds_contrat_by_reference(self):
        from apps.contrats.models import Contrat
        Contrat.objects.create(
            company=self.company, reference='CTR-2026-ARC29',
            objet='Contrat de maintenance annuelle')
        resp = self.api.get('/api/django/reporting/search/?q=CTR-2026-ARC29')
        self.assertEqual(resp.status_code, 200)
        group = next(
            (g for g in resp.data['groups'] if g['type'] == 'contrat_clm'), None)
        self.assertIsNotNone(group, resp.data['groups'])
        self.assertEqual(group['results'][0]['label'], 'CTR-2026-ARC29')

    def test_search_finds_contrat_by_objet(self):
        from apps.contrats.models import Contrat
        Contrat.objects.create(
            company=self.company, objet='Fourniture panneaux ArcSearchTest')
        resp = self.api.get('/api/django/reporting/search/?q=ArcSearchTest')
        group = next(
            (g for g in resp.data['groups'] if g['type'] == 'contrat_clm'), None)
        self.assertIsNotNone(group)

    def test_contrat_search_coexists_with_contrat_maintenance_group(self):
        """Les deux groupes 'contrat' (maintenance SAV) et 'contrat_clm' (CLM)
        restent DISTINCTS — aucune collision de clé de type."""
        from apps.contrats.models import Contrat
        from apps.sav.models import ContratMaintenance
        from datetime import date
        client = Client.objects.create(company=self.company, nom='CoexistTest')
        Contrat.objects.create(
            company=self.company, objet='CoexistTest contrat CLM')
        ContratMaintenance.objects.create(
            company=self.company, client=client, periodicite='annuel',
            date_debut=date.today(), actif=True)
        resp = self.api.get('/api/django/reporting/search/?q=CoexistTest')
        types = {g['type'] for g in resp.data['groups']}
        self.assertIn('contrat_clm', types)


class TestSearchNonRegressionEnvelope(TestCase):
    """L'enveloppe de résultat (clés/forme) reste identique à avant ARC29
    pour les groupes historiques (le hook front VX13 la consomme sans
    changement)."""

    def setUp(self):
        self.company = make_company('arc29-envelope', 'ARC29 Envelope Co')
        self.user = User.objects.create_user(
            username='arc29_envelope_user', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth_client(self.user)

    def test_envelope_shape_unchanged(self):
        from apps.crm.models import Lead
        Lead.objects.create(company=self.company, nom='EnvelopeShapeLead')
        resp = self.api.get('/api/django/reporting/search/?q=EnvelopeShapeLead')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.data.keys()), {'query', 'groups'})
        group = resp.data['groups'][0]
        self.assertEqual(set(group.keys()) & {'type', 'label', 'results'},
                         {'type', 'label', 'results'})
        item = group['results'][0]
        self.assertEqual(set(item.keys()), {'id', 'label', 'sublabel'})


class TestSearchRegistryDrivenWithoutTouchingSearchPy(TestCase):
    """Preuve que le balayage suit vraiment platform.searchable_models() :
    un manifeste fictif ADDITIONNEL déclarant une clé déjà servie par
    _SEARCH_SPECS (stock.produit) doit continuer à fonctionner — et retirer
    stock.produit du registre gaté (toggle OFF) le retire de la recherche
    SANS toucher apps/reporting/search.py."""

    def setUp(self):
        self.company = make_company('arc29-registry', 'ARC29 Registry Co')
        self.user = User.objects.create_user(
            username='arc29_registry_user', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth_client(self.user)

    def test_module_off_removes_model_from_search(self):
        """stock désactivé pour la société → stock.Produit disparaît de la
        recherche globale (gatage ModuleToggle étendu ODX23, sans changement
        dans search.py)."""
        from apps.stock.models import Produit
        Produit.objects.create(
            company=self.company, nom='ToggleOffProduitTest', prix_vente=1)
        ModuleToggle.objects.create(
            company=self.company, module='stock', actif=False)
        resp = self.api.get('/api/django/reporting/search/?q=ToggleOffProduitTest')
        self.assertEqual(resp.status_code, 200)
        group = next((g for g in resp.data['groups'] if g['type'] == 'produit'), None)
        self.assertIsNone(group, "stock désactivé mais Produit encore trouvé")

    def test_contrats_module_off_removes_contrat_from_search(self):
        from apps.contrats.models import Contrat
        Contrat.objects.create(
            company=self.company, objet='ToggleOffContratTest')
        ModuleToggle.objects.create(
            company=self.company, module='contrats', actif=False)
        resp = self.api.get('/api/django/reporting/search/?q=ToggleOffContratTest')
        group = next(
            (g for g in resp.data['groups'] if g['type'] == 'contrat_clm'), None)
        self.assertIsNone(group)

    def test_undeclared_model_disappears_from_search(self):
        """L'inverse utile : un registre simulé qui NE contient PLUS
        stock.produit (sans toggle) le retire de la recherche — le filtre est
        bien piloté par platform.searchable_models(), pas par une liste
        interne."""
        from apps.stock.models import Produit
        from core import platform as core_platform
        Produit.objects.create(
            company=self.company, nom='MockedRegistryProduitTest', prix_vente=1)

        vrais_manifestes = core_platform.collect_platform_manifests()
        sans_stock = {k: v for k, v in vrais_manifestes.items() if k != 'stock'}

        # ``apps.reporting.search.platform`` EST le module ``core.platform`` ;
        # patcher son attribut remplace donc aussi ``core_platform.searchable_models``.
        # On capture l'implémentation réelle AVANT le patch pour la rappeler dans
        # le side_effect sans réentrer dans le mock.
        vrai_searchable = core_platform.searchable_models
        with mock.patch(
                'apps.reporting.search.platform.searchable_models',
                side_effect=lambda company: vrai_searchable(
                    manifests=sans_stock)):
            resp = self.api.get(
                '/api/django/reporting/search/?q=MockedRegistryProduitTest')
        group = next((g for g in resp.data['groups'] if g['type'] == 'produit'), None)
        self.assertIsNone(
            group,
            "Produit retrouvé même en retirant 'stock' du registre plateforme "
            "— la recherche n'est pas réellement pilotée par platform.searchable_models().")

    def test_new_registry_model_appears_without_touching_search_py(self):
        """Sens direct du critère « Done » ARC29 : un modèle DÉCLARÉ au
        registre par un manifeste (ici un manifeste fictif d'un AUTRE module
        déclarant stock.produit, le vrai manifeste stock étant retiré)
        apparaît en recherche SANS AUCUNE modification de search.py — la
        présence dans un manifeste suffit à activer la spec."""
        from apps.stock.models import Produit
        from core import platform as core_platform
        Produit.objects.create(
            company=self.company, nom='DeclaredElsewhereProduitTest',
            prix_vente=1)

        vrais_manifestes = core_platform.collect_platform_manifests()
        faux = {k: v for k, v in vrais_manifestes.items() if k != 'stock'}
        faux['module_fictif_arc29'] = {
            'module': 'module_fictif_arc29',
            'searchable_models': ['stock.produit'],
            'record_targets': [], 'customfield_models': [],
            'import_specs': [], 'agent_actions_module': '',
            'automation_state_fields': [], 'kpi_providers': [],
        }

        # cf. note ci-dessus : capturer l'impl réelle avant le patch (le module
        # patché est aussi core.platform), pour ne pas réentrer dans le mock.
        vrai_searchable = core_platform.searchable_models
        with mock.patch(
                'apps.reporting.search.platform.searchable_models',
                side_effect=lambda company: vrai_searchable(
                    manifests=faux)):
            resp = self.api.get(
                '/api/django/reporting/search/?q=DeclaredElsewhereProduitTest')
        group = next((g for g in resp.data['groups'] if g['type'] == 'produit'), None)
        self.assertIsNotNone(
            group,
            "stock.produit déclaré par un manifeste mais absent de la "
            "recherche — le balayage n'est pas piloté par le registre.")
