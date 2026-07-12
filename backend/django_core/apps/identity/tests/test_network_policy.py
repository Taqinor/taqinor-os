"""NTSEC11 — Tests de l'allowlist IP/CIDR par société.

Couvre le middleware (off/monitor/enforce, allow/deny, applies_to, chemins
publics) et le CRUD scopé société réservé au Directeur.
"""
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from authentication.models import CustomUser
from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory, UserFactory

from apps.identity.middleware import NetworkPolicyMiddleware
from apps.identity.models import IpAllowRule, NetworkPolicy


def _ok(_request):
    return HttpResponse('ok', status=200)


class NetworkPolicyMiddlewareTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_ADMIN)
        self.mw = NetworkPolicyMiddleware(_ok)

    def _req(self, ip='9.9.9.9', user=None, path='/api/django/crm/leads/'):
        req = self.rf.get(path, REMOTE_ADDR=ip)
        req.user = user or self.user
        return req

    def _policy(self, mode, applies_to='all', allow='10.0.0.0/8'):
        pol = NetworkPolicy.objects.create(
            company=self.company, mode=mode, applies_to=applies_to)
        if allow:
            IpAllowRule.objects.create(
                company=self.company, policy=pol, cidr=allow)
        return pol

    def test_no_policy_never_blocks(self):
        resp = self.mw(self._req(ip='203.0.113.5'))
        self.assertEqual(resp.status_code, 200)

    def test_off_mode_never_blocks(self):
        self._policy(NetworkPolicy.Mode.OFF)
        resp = self.mw(self._req(ip='203.0.113.5'))
        self.assertEqual(resp.status_code, 200)

    def test_enforce_blocks_ip_outside_range(self):
        self._policy(NetworkPolicy.Mode.ENFORCE)
        resp = self.mw(self._req(ip='203.0.113.5'))
        self.assertEqual(resp.status_code, 403)
        self.assertIn(b'non autoris', resp.content)

    def test_enforce_allows_ip_inside_range(self):
        self._policy(NetworkPolicy.Mode.ENFORCE)
        resp = self.mw(self._req(ip='10.1.2.3'))
        self.assertEqual(resp.status_code, 200)

    def test_monitor_logs_but_never_blocks(self):
        from apps.audit.models import AuditLog
        self._policy(NetworkPolicy.Mode.MONITOR)
        before = AuditLog.objects.filter(
            action=AuditLog.Action.SECURITY_ALERT).count()
        resp = self.mw(self._req(ip='203.0.113.5'))
        self.assertEqual(resp.status_code, 200)
        after = AuditLog.objects.filter(
            action=AuditLog.Action.SECURITY_ALERT).count()
        self.assertEqual(after, before + 1)

    def test_public_paths_never_blocked(self):
        self._policy(NetworkPolicy.Mode.ENFORCE)
        for path in ('/api/public/leads/', '/api/django/public/sav/x/',
                     '/api/django/ventes/devis/1/proposal/'):
            resp = self.mw(self._req(ip='203.0.113.5', path=path))
            self.assertEqual(resp.status_code, 200, path)

    def test_applies_to_admins_ignores_non_admin(self):
        self._policy(NetworkPolicy.Mode.ENFORCE, applies_to='admins')
        # utilisateur normal hors plage : la politique ne le concerne pas.
        resp = self.mw(self._req(ip='203.0.113.5', user=self.user))
        self.assertEqual(resp.status_code, 200)
        # administrateur hors plage : bloqué.
        resp = self.mw(self._req(ip='203.0.113.5', user=self.admin))
        self.assertEqual(resp.status_code, 403)

    def test_forwarded_for_first_hop_used(self):
        self._policy(NetworkPolicy.Mode.ENFORCE)
        req = self.rf.get('/api/django/crm/leads/', REMOTE_ADDR='172.16.0.1')
        req.META['HTTP_X_FORWARDED_FOR'] = '10.5.5.5, 172.16.0.1'
        req.user = self.user
        resp = self.mw(req)
        self.assertEqual(resp.status_code, 200)

    def test_other_company_policy_does_not_apply(self):
        # Politique enforce sur MA société ; un user d'une autre société n'est
        # pas concerné par ma politique (résolution par sa propre société).
        self._policy(NetworkPolicy.Mode.ENFORCE)
        other = UserFactory(company=CompanyFactory())
        resp = self.mw(self._req(ip='203.0.113.5', user=other))
        self.assertEqual(resp.status_code, 200)


class NetworkPolicyCrudTests(TenantAPITestCase):
    BASE = '/api/django/identity/network-policies/'
    RULES = '/api/django/identity/ip-allow-rules/'

    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def test_admin_can_create_policy(self):
        r = self._admin().post(self.BASE, {'mode': 'enforce'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(NetworkPolicy.objects.count(), 1)

    def test_non_admin_forbidden(self):
        r = self.client_as().post(self.BASE, {'mode': 'enforce'},
                                  format='json')
        self.assertEqual(r.status_code, 403)

    def test_second_policy_rejected(self):
        NetworkPolicy.objects.create(
            company=self.company, mode=NetworkPolicy.Mode.OFF)
        r = self._admin().post(self.BASE, {'mode': 'monitor'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_policy_list_is_company_scoped(self):
        NetworkPolicy.objects.create(
            company=self.other_company, mode=NetworkPolicy.Mode.ENFORCE)
        r = self._admin().get(self.BASE)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 0)

    def test_rule_rejected_for_foreign_policy(self):
        foreign = NetworkPolicy.objects.create(
            company=self.other_company, mode=NetworkPolicy.Mode.OFF)
        r = self._admin().post(
            self.RULES,
            {'policy': foreign.id, 'cidr': '10.0.0.0/8'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_invalid_cidr_rejected(self):
        pol = NetworkPolicy.objects.create(
            company=self.company, mode=NetworkPolicy.Mode.OFF)
        r = self._admin().post(
            self.RULES,
            {'policy': pol.id, 'cidr': 'not-a-cidr'}, format='json')
        self.assertEqual(r.status_code, 400)
