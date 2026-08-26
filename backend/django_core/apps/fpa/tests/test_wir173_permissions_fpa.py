"""WIR173 — les 14 viewsets FP&A sont GARDÉS (fpa_saisir/valider/…).

Constat corrigé : aucun des 14 viewsets FP&A ne portait la moindre garde de
permission — cycles budgétaires, export XLSX de synthèse, scénarios what-if et
projection de masse salariale étaient ouverts à TOUT utilisateur authentifié de
la société (le défaut projet ``IsAuthenticated``).

Ce que ce module PROUVE :

* un rôle SANS aucun code FP&A → **403 partout** (les 14 routes, lecture ET
  écriture) ;
* un Directeur (hérite d'``ALL_PERMISSIONS``) → **200** en lecture ;
* les quatre actions de gouvernance d'un cycle (``ouvrir-saisie``, ``clore``,
  ``dupliquer``, ``export``) exigent ``fpa_administrer`` — ``fpa_saisir`` seul
  reçoit 403 ;
* les 4 codes sont bien ENREGISTRÉS au catalogue de rôles ;
* le repli LÉGACY (compte sans rôle fin, palier Responsable/Administrateur)
  garde son accès historique ;
* le périmètre par département (NTFPA26) est INCHANGÉ — cf.
  ``test_ntfpa26_permission_perimetre`` qui reste vert avec un rôle
  ``fpa_saisir``.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.fpa.models import CycleBudgetaire
from apps.fpa.permissions import (
    FPA_ADMINISTRER, FPA_CONSULTER_TOUT, FPA_SAISIR, FPA_VALIDER,
)
from apps.roles.models import (
    ALL_PERMISSIONS, COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS, Role,
)

User = get_user_model()

BASE = '/api/django/fpa/'

# Les 14 surfaces FP&A, dans l'ordre de ``apps/fpa/urls.py``.
ROUTES_LISTE = (
    f'{BASE}departements/',
    f'{BASE}cycles-budgetaires/',
    f'{BASE}lignes-budget-departement/',
    f'{BASE}soumissions-budget/',
    f'{BASE}previsions-glissantes/',
    f'{BASE}lignes-prevision-glissante/',
    f'{BASE}hypotheses-recrutement/',
    f'{BASE}scenarios/',
    f'{BASE}lignes-scenario/',
    f'{BASE}variance/',
    f'{BASE}consolidation/',
    f'{BASE}commentaires-variance/',
    f'{BASE}mapping-categories/',
    f'{BASE}drivers/revenu-pipeline/',
)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _FpaPermissionsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='WIR173 Co', slug='wir173-co')
        cls.cycle = CycleBudgetaire.objects.create(
            company=cls.company, nom='Budget 2030',
            date_debut=date(2030, 1, 1), date_fin=date(2030, 12, 31),
            statut=CycleBudgetaire.Statut.BROUILLON)

    def _user(self, suffix, perms=None, role_legacy=None):
        role = None
        if perms is not None:
            role = Role.objects.create(
                company=self.company, nom=f'wir173-{suffix}',
                permissions=list(perms))
        kwargs = {}
        if role_legacy is not None:
            kwargs['role_legacy'] = role_legacy
        return User.objects.create_user(
            username=f'wir173-{suffix}', password='x', role=role,
            company=self.company, **kwargs)


class FpaGardeGlobaleTests(_FpaPermissionsBase):
    """LE BUG : un rôle sans code FP&A ouvrait tout le module."""

    def test_role_sans_code_fpa_403_partout(self):
        user = self._user('commercial', perms=COMMERCIAL_PERMISSIONS)
        # Garde-fou : ce rôle porte bien des écritures ailleurs — il passait
        # donc l'ancien défaut « authentifié suffit ».
        self.assertTrue(user.is_responsable)
        client = _auth(user)
        for path in ROUTES_LISTE:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 403)

    def test_role_sans_code_fpa_403_en_ecriture(self):
        client = _auth(self._user('commercial-w', perms=COMMERCIAL_PERMISSIONS))
        for path in (f'{BASE}departements/', f'{BASE}cycles-budgetaires/',
                     f'{BASE}lignes-budget-departement/', f'{BASE}scenarios/'):
            with self.subTest(path=path):
                self.assertEqual(
                    client.post(path, {}, format='json').status_code, 403)

    def test_directeur_lit_partout(self):
        client = _auth(self._user('directeur', perms=DIRECTEUR_PERMISSIONS))
        for path in ROUTES_LISTE:
            with self.subTest(path=path):
                resp = client.get(path)
                # Certaines routes de calcul exigent des paramètres (400) —
                # jamais 403 pour un Directeur.
                self.assertIn(resp.status_code, (200, 400), path)

    def test_fpa_consulter_tout_lit_mais_n_ecrit_pas(self):
        """``fpa_consulter_tout`` est une LECTURE élargie, jamais une écriture."""
        client = _auth(self._user('lecteur', perms=[FPA_CONSULTER_TOUT]))
        self.assertEqual(
            client.get(f'{BASE}cycles-budgetaires/').status_code, 200)
        self.assertEqual(
            client.post(f'{BASE}cycles-budgetaires/', {},
                        format='json').status_code, 403)

    def test_fpa_saisir_lit_et_ecrit(self):
        client = _auth(self._user('saisie', perms=[FPA_SAISIR]))
        self.assertEqual(
            client.get(f'{BASE}lignes-budget-departement/').status_code, 200)
        # Jamais 403 : 400 de validation métier accepté sur ce POST minimal.
        self.assertNotEqual(
            client.post(f'{BASE}lignes-budget-departement/', {},
                        format='json').status_code, 403)

    def test_compte_legacy_garde_son_acces_historique(self):
        client = _auth(self._user(
            'legacy', perms=None, role_legacy=CustomUser.ROLE_RESPONSABLE))
        self.assertEqual(
            client.get(f'{BASE}cycles-budgetaires/').status_code, 200)

    def test_anonyme_refuse(self):
        self.assertIn(
            APIClient().get(f'{BASE}cycles-budgetaires/').status_code,
            (401, 403))


class FpaActionsGouvernanceTests(_FpaPermissionsBase):
    """Les 4 actions de cycle exigent ``fpa_administrer``, pas moins."""

    def _actions(self):
        cid = self.cycle.pk
        return (
            ('post', f'{BASE}cycles-budgetaires/{cid}/ouvrir-saisie/'),
            ('post', f'{BASE}cycles-budgetaires/{cid}/clore/'),
            ('post', f'{BASE}cycles-budgetaires/{cid}/dupliquer/'),
            ('get', f'{BASE}cycles-budgetaires/{cid}/export/'),
        )

    def test_fpa_saisir_seul_refuse_la_gouvernance(self):
        client = _auth(self._user('gouv-saisie', perms=[FPA_SAISIR]))
        for methode, path in self._actions():
            with self.subTest(path=path):
                resp = getattr(client, methode)(path, {}, format='json') \
                    if methode == 'post' else client.get(path)
                self.assertEqual(resp.status_code, 403, path)

    def test_fpa_valider_seul_refuse_la_gouvernance(self):
        client = _auth(self._user('gouv-valider', perms=[FPA_VALIDER]))
        for methode, path in self._actions():
            with self.subTest(path=path):
                resp = getattr(client, methode)(path, {}, format='json') \
                    if methode == 'post' else client.get(path)
                self.assertEqual(resp.status_code, 403, path)

    def test_fpa_administrer_passe_la_gouvernance(self):
        client = _auth(self._user('gouv-admin', perms=[FPA_ADMINISTRER]))
        for methode, path in self._actions():
            with self.subTest(path=path):
                resp = getattr(client, methode)(path, {}, format='json') \
                    if methode == 'post' else client.get(path)
                # Jamais 403 : selon l'état du cycle, 200/201/400 sont des
                # réponses MÉTIER légitimes.
                self.assertNotEqual(resp.status_code, 403, path)


class FpaCatalogueTests(TestCase):
    """Les 4 codes sont enregistrés et distribués à la direction seule."""

    CODES = (FPA_SAISIR, FPA_VALIDER, FPA_CONSULTER_TOUT, FPA_ADMINISTRER)

    def test_codes_au_catalogue(self):
        for code in self.CODES:
            with self.subTest(code=code):
                self.assertIn(code, ALL_PERMISSIONS)

    def test_directeur_les_porte(self):
        for code in self.CODES:
            with self.subTest(code=code):
                self.assertIn(code, DIRECTEUR_PERMISSIONS)

    def test_commercial_ne_les_porte_pas(self):
        for code in self.CODES:
            with self.subTest(code=code):
                self.assertNotIn(code, COMMERCIAL_PERMISSIONS)
