"""NTSEC20 — Séparation des tâches (SoD) : violations + blocage + seed.

Garanties : un utilisateur cumulant deux permissions en conflit apparaît dans
le rapport SoD ; une règle critique bloque l'attribution du rôle ; le seed
standard est fourni ; tout est scopé société.
"""
from apps.roles.models import ALL_PERMISSIONS, Role
from apps.roles.services import apply_role_to_user
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase
from testkit.factories import UserFactory

from apps.accessreview.models import SodRule
from apps.accessreview.sod import (
    STANDARD_SOD_RULES, seed_standard_sod_rules, sod_violations,
    would_cumulate_critical,
)


class SodTests(TenantAPITestCase):
    def _rule(self, a, b, sev='warning', company=None):
        return SodRule.objects.create(
            company=company or self.company,
            permission_a=a, permission_b=b, severite=sev)

    def test_violation_detected(self):
        self._rule('facture.saisir', 'paiement.valider')
        role = Role.objects.create(
            company=self.company, nom='Cumul',
            permissions=['facture.saisir', 'paiement.valider'])
        UserFactory(company=self.company, username='cumul', role=role)
        v = sod_violations(self.company)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]['username'], 'cumul')

    def test_no_violation_when_only_one_permission(self):
        self._rule('facture.saisir', 'paiement.valider')
        role = Role.objects.create(
            company=self.company, nom='Solo',
            permissions=['facture.saisir'])
        UserFactory(company=self.company, username='solo', role=role)
        self.assertEqual(sod_violations(self.company), [])

    def test_critical_rule_blocks_role_assignment(self):
        self._rule('facture.saisir', 'paiement.valider', sev='critique')
        role = Role.objects.create(
            company=self.company, nom='Dangereux',
            permissions=['facture.saisir', 'paiement.valider'])
        user = UserFactory(company=self.company, username='blockme')
        self.assertTrue(would_cumulate_critical(user, role))
        # apply_role_to_user doit refuser (retourne False, rôle inchangé).
        self.assertFalse(apply_role_to_user(user, role.id))
        user.refresh_from_db()
        self.assertIsNone(user.role_id)

    def test_warning_rule_does_not_block(self):
        self._rule('achat.commander', 'achat.receptionner', sev='warning')
        role = Role.objects.create(
            company=self.company, nom='Achat',
            permissions=['achat.commander', 'achat.receptionner'])
        user = UserFactory(company=self.company, username='ok')
        self.assertTrue(apply_role_to_user(user, role.id))
        user.refresh_from_db()
        self.assertEqual(user.role_id, role.id)

    def test_seed_standard_idempotent(self):
        n1 = seed_standard_sod_rules(self.company)
        n2 = seed_standard_sod_rules(self.company)
        self.assertGreater(n1, 0)
        self.assertEqual(n2, 0)

    def test_report_scoped_to_company(self):
        # Règle + cumul dans une AUTRE société : jamais dans notre rapport.
        self._rule('a', 'b', company=self.other_company)
        role = Role.objects.create(
            company=self.other_company, nom='X', permissions=['a', 'b'])
        UserFactory(company=self.other_company, username='foreign', role=role)
        self.assertEqual(sod_violations(self.company), [])

    def test_violations_endpoint(self):
        self._rule('facture.saisir', 'paiement.valider')
        role = Role.objects.create(
            company=self.company, nom='Cumul',
            permissions=['facture.saisir', 'paiement.valider'])
        UserFactory(company=self.company, username='cumul', role=role)
        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(
            '/api/django/accessreview/sod-rules/violations/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()['results']), 1)


class SodStandardRealCodesTests(TenantAPITestCase):
    """WIR11 — le jeu SoD standard utilise de VRAIS codes underscore, si bien
    qu'un cumul réellement incompatible est cette fois détecté ET bloqué (les
    anciens codes pointés ne matchaient jamais : SoD silencieusement inerte)."""

    def test_seed_standard_only_real_permission_codes(self):
        catalogue = set(ALL_PERMISSIONS)
        for perm_a, perm_b, _sev, _lib in STANDARD_SOD_RULES:
            self.assertIn(perm_a, catalogue, perm_a)
            self.assertIn(perm_b, catalogue, perm_b)

    def test_seed_standard_flags_real_cumul(self):
        seed_standard_sod_rules(self.company)
        role = Role.objects.create(
            company=self.company, nom='Compta cumul',
            permissions=['compta_saisir', 'compta_valider'])
        UserFactory(company=self.company, username='compta-cumul', role=role)
        v = sod_violations(self.company)
        self.assertTrue(any(
            x['permission_a'] == 'compta_saisir'
            and x['permission_b'] == 'compta_valider' for x in v), v)

    def test_seed_standard_critical_blocks_role_assignment(self):
        seed_standard_sod_rules(self.company)
        role = Role.objects.create(
            company=self.company, nom='Compta dangereux',
            permissions=['compta_saisir', 'compta_valider'])
        user = UserFactory(company=self.company, username='compta-block')
        self.assertTrue(would_cumulate_critical(user, role))
        self.assertFalse(apply_role_to_user(user, role.id))
        user.refresh_from_db()
        self.assertIsNone(user.role_id)


class SodRuleWriteValidationTests(TenantAPITestCase):
    """WIR11 — écrire une SodRule sur un code de permission inexistant renvoie
    400 (FR) : une règle inerte ne peut plus être créée par inadvertance."""

    URL = '/api/django/accessreview/sod-rules/'

    def test_create_rule_unknown_code_rejected(self):
        client = self.client_as(role=CustomUser.ROLE_ADMIN)
        r = client.post(self.URL, {
            'permission_a': 'facture.saisir',  # code POINTÉ inexistant
            'permission_b': 'compta_valider',
            'severite': 'critique',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('permission_a', r.json())
        self.assertEqual(
            SodRule.objects.filter(company=self.company).count(), 0)

    def test_create_rule_unknown_second_code_rejected(self):
        client = self.client_as(role=CustomUser.ROLE_ADMIN)
        r = client.post(self.URL, {
            'permission_a': 'compta_saisir',
            'permission_b': 'paiement.valider',  # inexistant
            'severite': 'warning',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('permission_b', r.json())

    def test_create_rule_known_codes_ok(self):
        client = self.client_as(role=CustomUser.ROLE_ADMIN)
        r = client.post(self.URL, {
            'permission_a': 'compta_saisir',
            'permission_b': 'compta_valider',
            'severite': 'critique',
            'libelle': 'Test',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            SodRule.objects.filter(company=self.company).count(), 1)
