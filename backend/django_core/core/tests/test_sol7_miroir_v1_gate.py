"""SOL7 — le miroir `api/v1/` est gardé comme `api/django/` (bug produit vivant).

`erp_agentique/urls.py` monte la MÊME liste `_APP_URLS` sous les deux préfixes
(YAPIC7) : mêmes ViewSets, mêmes données. `DisabledModuleMiddleware` ne matchait
que `api/django/` — un tenant ayant désactivé un module recevait bien un 404 sur
`/api/django/pos/…` mais était SERVI NORMALEMENT sur `/api/v1/pos/…`. Le gating
n'était donc pas un gating : c'était une porte fermée à côté d'une porte ouverte.

Ces tests épinglent la PARITÉ des deux préfixes, dans les deux sens : ce qui est
bloqué l'est des deux côtés, ce qui est exempté l'est des deux côtés.
"""
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from authentication.models import Company
from core import permissions
from core.models import ModuleToggle

User = get_user_model()

# Segments testés en parité — un module métier « installable », un alias de
# préfixe, et l'ensemble des exemptions.
SEGMENTS_METIER = ('pos', 'flotte', 'stock', 'douane', 'transport', 'scm')


class PariteDesDeuxPrefixesTests(SimpleTestCase):
    """Le helper de mapping doit répondre IDENTIQUEMENT aux deux préfixes."""

    def test_module_metier_reconnu_sous_v1(self):
        for segment in SEGMENTS_METIER:
            self.assertEqual(
                permissions._module_key_for_path(f'/api/v1/{segment}/x/'),
                segment, segment)

    def test_parite_stricte_avec_api_django(self):
        for segment in SEGMENTS_METIER + tuple(permissions.EXEMPT_PREFIXES):
            legacy = permissions._module_key_for_path(
                f'/api/django/{segment}/x/')
            miroir = permissions._module_key_for_path(f'/api/v1/{segment}/x/')
            self.assertEqual(
                legacy, miroir,
                f'segment « {segment} » : api/django → {legacy!r} mais '
                f'api/v1 → {miroir!r}')

    def test_alias_de_prefixe_applique_aussi_sous_v1(self):
        for chemin, cle in permissions.PREFIX_TO_MODULE.items():
            self.assertEqual(
                permissions._module_key_for_path(f'/api/v1/{chemin}/x/'), cle)

    def test_exemptions_valent_pour_les_deux_prefixes(self):
        for segment in permissions.EXEMPT_PREFIXES:
            self.assertIsNone(
                permissions._module_key_for_path(f'/api/v1/{segment}/x/'),
                segment)

    def test_api_publique_par_cle_hors_perimetre(self):
        """`api/public/…` n'est ni `api/django/` ni `api/v1/` : jamais matché."""
        for chemin in ('/api/public/v1/openapi.json',
                       '/api/public/produits/',
                       '/api/schema/', '/static/x.css', '/'):
            self.assertIsNone(
                permissions._module_key_for_path(chemin), chemin)

    def test_prefixe_voisin_non_matche(self):
        """`api/v10/`/`api/v1x/` ne doivent PAS être pris pour `api/v1/`."""
        for chemin in ('/api/v10/pos/x/', '/api/v1x/pos/x/', '/api/v1'):
            self.assertIsNone(
                permissions._module_key_for_path(chemin), chemin)


class MiroirV1BloqueTests(TestCase):
    """Bout en bout : le 404 tombe aussi sur le miroir, et seulement là où il faut."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME SOL7')
        cls.autre = Company.objects.create(nom='Autre SOL7')
        cls.user = User.objects.create_user(
            username='sol7_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.autre_user = User.objects.create_user(
            username='sol7_autre', password='x', role_legacy='normal',
            company=cls.autre)

    def _mw(self):
        sentinel = HttpResponse('ok')
        return permissions.DisabledModuleMiddleware(lambda req: sentinel), sentinel

    def _req(self, path, user):
        req = RequestFactory().get(path)
        req.user = user
        return req

    def test_module_desactive_bloque_sur_le_miroir_v1(self):
        ModuleToggle.objects.create(
            company=self.company, module='pos', actif=False)
        mw, sentinel = self._mw()
        legacy = mw(self._req('/api/django/pos/tickets/', self.user))
        miroir = mw(self._req('/api/v1/pos/tickets/', self.user))
        self.assertEqual(legacy.status_code, 404)
        self.assertEqual(
            miroir.status_code, 404,
            'le miroir /api/v1/ sert encore un module désactivé (SOL7)')
        self.assertIsNot(miroir, sentinel)

    def test_module_actif_passe_sur_le_miroir(self):
        mw, sentinel = self._mw()
        self.assertIs(mw(self._req('/api/v1/pos/tickets/', self.user)), sentinel)

    def test_isolation_multi_tenant_sur_le_miroir(self):
        ModuleToggle.objects.create(
            company=self.company, module='pos', actif=False)
        mw, sentinel = self._mw()
        self.assertEqual(
            mw(self._req('/api/v1/pos/x/', self.user)).status_code, 404)
        self.assertIs(
            mw(self._req('/api/v1/pos/x/', self.autre_user)), sentinel)

    def test_exemption_fondation_sur_le_miroir(self):
        ModuleToggle.objects.create(
            company=self.company, module='reporting', actif=False)
        mw, sentinel = self._mw()
        self.assertIs(
            mw(self._req('/api/v1/reporting/kpis/', self.user)), sentinel)

    def test_routes_publiques_tokenisees_jamais_bloquees(self):
        """Audit SOL7 — un lien PDF client ne dépend d'aucun ModuleToggle."""
        ModuleToggle.objects.create(
            company=self.company, module='ventes', actif=False)
        mw, sentinel = self._mw()
        for chemin in ('/api/django/public/devis/abc/',
                       '/api/django/public/sav/xyz/',
                       '/api/public/produits/'):
            self.assertIs(
                mw(self._req(chemin, self.user)), sentinel, chemin)
