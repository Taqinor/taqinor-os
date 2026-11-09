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
from authentication.permissions import (
    APPS_SANS_MODULE, IsResponsableOrAdmin, module_de_la_vue)

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
    # ASEC50 (roles 0009) : « Responsable » reçoit ``reporting_export`` pour
    # garder l'export de rapport qu'il faisait déjà ; c'est l'unique code
    # d'écriture du module reporting, d'où W (rapports sauvegardés, config du
    # tableau de bord, alertes KPI : « restent administrateur/responsable »,
    # décision fondateur ASEC11) — comme Commercial/Technicien responsable.
    'Responsable':            'WWWWWWWW',
    'Utilisateur':            '--------',
    'Admin RH':               '-----R-W',
    'Admin Ventes':           'WWW--WWW',
}

# AARG52 — la liste des apps de fondation vit dans ``authentication.permissions``
# (``APPS_SANS_MODULE``, seule liste). Une app non résolue HORS liste a ses
# écritures fermées aux rôles fins ; ``portail`` l'est jusqu'à AARG8 (modules
# posés sur ses vues). Toute autre app non résolue fait échouer le test.
FERMEES_EN_ECRITURE_ATTENDUES = frozenset({'portail'})


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

    def _facture(self, auteur):
        from decimal import Decimal
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        cli = Client.objects.create(company=self.company, nom='Lecture',
                                    prenom='ASEC11',
                                    email='lecture-asec11@test.invalid')
        return Facture.objects.create(
            company=self.company, reference='ASEC11-LECT-1', client=cli,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
            created_by=auteur)

    def test_lecture_factures_refusee_sans_ventes_voir(self):
        # ERR-ASEC11-LECTURE-FACTURES (D-ASEC11-LECTURE-FACTURES) — liste ET
        # fiche : 403 pour Commercial terrain et Admin RH (aucun code ventes).
        facture = self._facture(None)
        for nom_role in ('Commercial terrain', 'Admin RH'):
            api = self._api(nom_role)
            with self.subTest(role=nom_role):
                self.assertEqual(
                    api.get('/api/django/ventes/factures/').status_code, 403)
                self.assertEqual(
                    api.get(f'/api/django/ventes/factures/{facture.id}/')
                    .status_code, 403)

    def test_lecture_factures_ok_avec_ventes_voir(self):
        user = self._user('Commercial')
        facture = self._facture(user)
        api = APIClient()
        api.force_authenticate(user)
        self.assertEqual(
            api.get('/api/django/ventes/factures/').status_code, 200)
        self.assertEqual(
            api.get(f'/api/django/ventes/factures/{facture.id}/').status_code,
            200)
        directeur = self._api('Directeur')
        self.assertEqual(
            directeur.get('/api/django/ventes/factures/').status_code, 200)

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
        nouvelles = non_resolues - APPS_SANS_MODULE - FERMEES_EN_ECRITURE_ATTENDUES
        self.assertEqual(
            nouvelles, set(),
            'Vue IsResponsableOrAdmin sans module résolu : poser '
            '`permission_module` ou un code au registre.')

    def test_vues_facturation_relevent_du_module_ventes(self):
        """ODX18 — les vues déménagées sous ``apps.facturation`` gardent la
        garde du module ``ventes`` (sinon « module non résolu » : écritures
        refusées à tout rôle fin, Commercial à ``ventes_creer`` compris)."""
        vue = type('VueFacture', (),
                   {'__module__': 'apps.facturation.views.facture'})()
        self.assertEqual(module_de_la_vue(vue), 'ventes')

    def test_ecriture_sans_module_hors_fondation_refusee(self):
        """AARG52 — vue sans module d'une app hors ``APPS_SANS_MODULE``
        (portail) : écriture refusée à un rôle fin non administrateur
        (Technicien, rôle « RH seul »), lecture inchangée ; app de fondation
        listée et administrateur : inchangés."""
        perm = IsResponsableOrAdmin()
        rh_seul = User.objects.create_user(
            username='aarg52_rh', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='RH seul',
                                     permissions=['rh_voir', 'rh_gerer']))
        portail = type('VuePortail', (), {'__module__': 'apps.portail.views'})()
        fondation = type('VueCore', (), {'__module__': 'apps.core.views'})()
        self.assertNotIn('portail', APPS_SANS_MODULE)
        for user in (rh_seul, self._user('Technicien')):
            with self.subTest(user=user.username):
                self.assertIsNone(module_de_la_vue(portail))
                self.assertFalse(perm.has_permission(
                    SimpleNamespace(user=user, method='POST'), portail))
                self.assertTrue(perm.has_permission(
                    SimpleNamespace(user=user, method='GET'), portail))
                self.assertTrue(perm.has_permission(
                    SimpleNamespace(user=user, method='POST'), fondation))
        admin = self._user('Administrateur')
        self.assertTrue(perm.has_permission(
            SimpleNamespace(user=admin, method='POST'), portail))

    def test_monitoring_hors_liste_de_fondation(self):
        """AMON92 — ``monitoring`` n'est plus une app de fondation : une vue
        sans module de l'app refuse l'écriture au rôle « RH seul » et au
        Technicien (lecture admise) ; l'Administrateur reste admis."""
        perm = IsResponsableOrAdmin()
        rh_seul = User.objects.create_user(
            username='amon92_rh', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='RH seul 92',
                                     permissions=['rh_voir', 'rh_gerer']))
        vue = type('VueMonitoring', (), {
            '__module__': 'apps.monitoring.views'})()
        self.assertNotIn('monitoring', APPS_SANS_MODULE)
        for user in (rh_seul, self._user('Technicien')):
            with self.subTest(user=user.username):
                self.assertFalse(perm.has_permission(
                    SimpleNamespace(user=user, method='POST'), vue))
                self.assertTrue(perm.has_permission(
                    SimpleNamespace(user=user, method='GET'), vue))
        self.assertTrue(perm.has_permission(SimpleNamespace(
            user=self._user('Administrateur'), method='POST'), vue))
