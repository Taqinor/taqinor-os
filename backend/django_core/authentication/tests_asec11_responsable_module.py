"""ASEC11 — ``IsResponsableOrAdmin`` dépend du MODULE de la vue.

Pour un rôle fin non administrateur : écriture = un code d'écriture du module
de la vue ; lecture = au moins un code de ce module. Commercial terrain et
Admin RH ne passent plus CRM / Ventes (factures) ; Commercial responsable
inchangé sur CRM. La MATRICE DORÉE rôle système × module ci-dessous est
littérale : elle ne change que par un geste volontaire et doit égaler le
registre des droits.
"""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import get_resolver
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.roles.permissions_registre import PERMISSION_MODULE
from authentication.models import Company
from authentication.permissions import IsResponsableOrAdmin, module_de_la_vue

User = get_user_model()

MODULES = ('crm', 'ventes', 'stock', 'installations', 'sav', 'reporting',
           'calepinage', 'ged')

# W = lecture + écriture ; R = lecture seule ; - = refusé.
MATRICE_DOREE = {
    'Directeur':              'WWWWWWWW',
    'Administrateur':         'WWWWWWWW',
    'Commercial responsable': 'WWW-WWWW',
    'Commercial':             'WWR-RRWW',
    'Commercial terrain':     '--------',
    'Technicien responsable': '--WWWW-W',
    'Technicien':             '--WWWR-W',
    'Viewer':                 '--------',
    'Responsable':            'WWWWWRWW',
    'Utilisateur':            '--------',
    'Admin RH':               '-----R-W',
    'Admin Ventes':           'WWW--WWW',
}

# Apps de FONDATION / satellites sans codes propres au registre : leurs vues
# gardées par IsResponsableOrAdmin suivent la règle historique. Liste FIGÉE,
# qui ne peut que décroître : une nouvelle app non résolue fait échouer le test.
APPS_SANS_MODULE_FIGEES = frozenset({
    'authentication', 'core', 'dataimport', 'documents', 'monitoring',
    'offlinesync', 'outillage', 'portail', 'records', 'roles', 'semantic',
    'uxviews',
})


def _iter_vues(motifs):
    for motif in motifs:
        if hasattr(motif, 'url_patterns'):
            yield from _iter_vues(motif.url_patterns)
            continue
        cls = getattr(getattr(motif, 'callback', None), 'cls', None)
        if cls is not None:
            yield cls


class ResponsableParModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ASEC11', slug='asec11-co')
        call_command('init_roles', verbosity=0)
        cls.roles = {r.nom: r for r in Role.objects.filter(company=cls.company)}

    def _user(self, nom_role):
        return User.objects.create_user(
            username=f'asec11_{nom_role.replace(" ", "_").lower()}',
            password='x', company=self.company, role=self.roles[nom_role])

    def _api(self, nom_role):
        api = APIClient()
        api.force_authenticate(self._user(nom_role))
        return api

    def test_commercial_terrain_refuse_crm(self):
        # ClientViewSet : create/update gardés par IsResponsableOrAdmin.
        api = self._api('Commercial terrain')
        self.assertEqual(
            api.post('/api/django/crm/clients/', {'nom': 'X'}, format='json')
            .status_code, 403)

    def test_admin_rh_refuse_facturation(self):
        # FactureViewSet : create (et abandon de solde, paiements…) gardés par
        # IsResponsableOrAdmin ; le refus précède toute validation du corps.
        api = self._api('Admin RH')
        self.assertEqual(
            api.post('/api/django/ventes/factures/', {}, format='json')
            .status_code, 403)

    def test_commercial_resp_crm_ok(self):
        api = self._api('Commercial responsable')
        resp = api.post('/api/django/crm/clients/', {'nom': 'Client ASEC11'},
                        format='json')
        self.assertNotEqual(resp.status_code, 403,
                            getattr(resp, 'data', None))

    def test_matrice_role_module_egale_registre(self):
        perm = IsResponsableOrAdmin()
        for nom_role, ligne in MATRICE_DOREE.items():
            user = self._user(nom_role)
            for module, attendu in zip(MODULES, ligne):
                vue = SimpleNamespace(permission_module=module)
                lecture = perm.has_permission(
                    SimpleNamespace(user=user, method='GET'), vue)
                ecriture = perm.has_permission(
                    SimpleNamespace(user=user, method='POST'), vue)
                obtenu = 'W' if ecriture else ('R' if lecture else '-')
                with self.subTest(role=nom_role, module=module):
                    self.assertEqual(obtenu, attendu)
                    self.assertFalse(ecriture and not lecture)

    def test_vues_sans_module_figees(self):
        modules_registre = set(PERMISSION_MODULE.values())
        non_resolues = set()
        for cls in _iter_vues(get_resolver().url_patterns):
            perms = list(getattr(cls, 'permission_classes', []) or [])
            if not any(p is IsResponsableOrAdmin for p in perms):
                continue
            vue = cls.__new__(cls)
            if module_de_la_vue(vue) in modules_registre:
                continue
            parties = cls.__module__.split('.')
            non_resolues.add(parties[1] if parties[0] == 'apps' else parties[0])
        nouvelles = non_resolues - APPS_SANS_MODULE_FIGEES
        self.assertEqual(
            nouvelles, set(),
            'Vue IsResponsableOrAdmin sans module résolu : poser '
            '`permission_module` ou un code au registre.')
