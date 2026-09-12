"""VTA1 — l'app « visites » existe, est déclarée et est CÂBLÉE.

Ce module ne teste pas du métier : il teste le CÂBLAGE, c'est-à-dire les points
que le scaffolder ``startapp_erp`` imprime et qu'on oublie un par un (patron
repris de ``apps/veille_ao/tests/test_smoke.py``) :

  1. le manifeste de module est bien collecté (clé unique, libellé FR,
     catégorie, dépendances) ;
  2. le 2ᵉ segment d'URL est IDENTIQUE à la clé de manifeste — sans quoi le
     gatage 404 des modules désactivés viserait le mauvais module (ou
     exigerait une entrée ``core/permissions.PREFIX_TO_MODULE``) ;
  3. ``/api/django/visites/`` répond réellement ;
  4. un module désactivé par ``ModuleToggle`` rend bien 404, pour CETTE
     société seulement.

Plus la garde de conception du groupe VTA : ``apps.visites`` n'est NI
``apps.crm`` (d'où elle sort) NI ``apps.installations`` (le post-vente).
"""
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import resolve
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core import permissions
from core.models import ModuleToggle

User = get_user_model()

SEGMENT_URL = 'visites'
CLE_MODULE = 'visites'


class ManifesteModuleTests(TestCase):
    """1. Le manifeste est déclaré et collecté génériquement."""

    def test_app_chargee(self):
        config = django_apps.get_app_config('visites')
        self.assertEqual(config.name, 'apps.visites')

    def test_manifeste_declare(self):
        manifeste = django_apps.get_app_config('visites').module_manifest
        self.assertEqual(manifeste['key'], CLE_MODULE)
        self.assertEqual(manifeste['label'], 'Visites terrain')
        self.assertEqual(manifeste['categorie'], 'Commercial')
        # La visite documente un LEAD : dépendance de graphe, jamais un import
        # Python (la FK reste une référence string 'crm.Lead').
        self.assertEqual(manifeste['depends'], ['crm'])

    def test_manifeste_dans_le_registre(self):
        from core.modules import collect_manifests

        manifestes = collect_manifests()
        self.assertIn(CLE_MODULE, manifestes)
        self.assertEqual(manifestes[CLE_MODULE]['app_label'], 'visites')

    def test_graphe_de_modules_reste_valide(self):
        """``depends: ['crm']`` doit pointer vers un module qui EXISTE (et le
        graphe complet rester sans cycle)."""
        from core.modules import collect_manifests, valider_graphe

        manifestes = collect_manifests()
        self.assertIn('crm', manifestes)
        valider_graphe(manifestes)

    def test_visites_n_est_ni_crm_ni_installations(self):
        """Garde de conception VTA : trois apps DISTINCTES.

        ``apps.crm`` est l'app d'où la visite SORT ; ``apps.installations`` est
        le post-vente (possédé par le contrat PLAN_SERVICE) — la visite
        technique est de la pré-vente, rattachée au ``Lead``.
        """
        nom = django_apps.get_app_config('visites').name
        self.assertNotEqual(nom, django_apps.get_app_config('crm').name)
        self.assertNotEqual(
            nom, django_apps.get_app_config('installations').name)

    def test_manifeste_plateforme_collecte(self):
        """ARC28 — le manifeste plateforme est vu par le collecteur générique."""
        from core.platform import collect_platform_manifests

        manifestes = collect_platform_manifests()
        self.assertIn(CLE_MODULE, manifestes)


class CablageUrlTests(TestCase):
    """2. + 3. Le segment colle à la clé, et la route répond."""

    def test_segment_url_identique_a_la_cle_de_manifeste(self):
        manifeste = django_apps.get_app_config('visites').module_manifest
        self.assertEqual(SEGMENT_URL, manifeste['key'])

    def test_prefixe_url_mappe_sur_le_module(self):
        """Sans cette égalité, un module désactivé ne serait PAS bloqué."""
        self.assertEqual(
            permissions._module_key_for_path(
                f'/api/django/{SEGMENT_URL}/visites/'),
            CLE_MODULE)

    def test_racine_du_module_est_routee(self):
        match = resolve(f'/api/django/{SEGMENT_URL}/')
        self.assertIsNotNone(match)

    def test_racine_repond_a_un_utilisateur_authentifie(self):
        company = Company.objects.create(nom='ACME VTA')
        user = User.objects.create_user(
            username='vta_smoke', password='x', role_legacy='normal',
            company=company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        reponse = api.get(f'/api/django/{SEGMENT_URL}/')
        self.assertLess(reponse.status_code, 400, reponse.status_code)

    def test_racine_refusee_a_un_anonyme(self):
        anonyme = APIClient()
        self.assertIn(
            anonyme.get(f'/api/django/{SEGMENT_URL}/').status_code,
            (401, 403))


class ModuleDesactiveTests(TestCase):
    """4. ``ModuleToggle`` OFF → 404, pour cette société seulement."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME VTA toggle')
        cls.autre = Company.objects.create(nom='Autre société VTA')
        cls.user = User.objects.create_user(
            username='vta_toggle', password='x', role_legacy='normal',
            company=cls.company)
        cls.autre_user = User.objects.create_user(
            username='vta_toggle_autre', password='x', role_legacy='normal',
            company=cls.autre)

    def _middleware(self):
        sentinelle = HttpResponse('ok')
        middleware = permissions.DisabledModuleMiddleware(
            lambda requete: sentinelle)
        return middleware, sentinelle

    def _requete(self, user):
        requete = RequestFactory().get(f'/api/django/{SEGMENT_URL}/visites/')
        requete.user = user
        return requete

    def test_module_desactive_rend_404(self):
        ModuleToggle.objects.create(
            company=self.company, module=CLE_MODULE, actif=False)
        middleware, sentinelle = self._middleware()
        reponse = middleware(self._requete(self.user))
        self.assertEqual(reponse.status_code, 404)
        self.assertIsNot(reponse, sentinelle)

    def test_module_actif_par_defaut_passe(self):
        middleware, sentinelle = self._middleware()
        reponse = middleware(self._requete(self.user))
        self.assertIs(reponse, sentinelle)

    def test_desactivation_isolee_par_societe(self):
        ModuleToggle.objects.create(
            company=self.company, module=CLE_MODULE, actif=False)
        middleware, sentinelle = self._middleware()
        reponse = middleware(self._requete(self.autre_user))
        self.assertIs(reponse, sentinelle)
