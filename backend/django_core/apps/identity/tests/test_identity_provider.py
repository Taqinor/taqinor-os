"""NTSEC1 — Tests du modèle ``IdentityProvider`` + CRUD admin SSO.

Garanties : scope société forcé côté serveur, CRUD réservé au Directeur, un
seul IdP actif par (société, protocole), et — sans IdP actif — aucun impact
sur le login (le modèle est inerte).
"""
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase

from apps.identity.models import IdentityProvider


class IdentityProviderCrudTests(TenantAPITestCase):
    BASE = '/api/django/identity/providers/'

    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def _payload(self, **over):
        data = {
            'protocol': 'saml',
            'nom': 'Okta',
            'actif': True,
            'entity_id': 'https://idp.example/entity',
            'sso_url': 'https://idp.example/sso',
            'attribute_map': {'email': 'mail', 'nom': 'sn'},
        }
        data.update(over)
        return data

    def test_admin_can_register_and_activate_idp(self):
        r = self._admin().post(self.BASE, self._payload(), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        idp = IdentityProvider.objects.get()
        self.assertEqual(idp.company_id, self.company.id)
        self.assertTrue(idp.actif)
        self.assertEqual(idp.protocol, 'saml')

    def test_company_forced_server_side(self):
        # Un corps qui tente d'injecter une autre société est ignoré : la
        # société de l'appelant prime toujours.
        r = self._admin().post(
            self.BASE,
            self._payload(company=self.other_company.id),
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            IdentityProvider.objects.get().company_id, self.company.id)

    def test_non_admin_forbidden(self):
        r = self.client_as().post(self.BASE, self._payload(), format='json')
        self.assertEqual(r.status_code, 403)

    def test_second_active_same_protocol_rejected(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='A', actif=True)
        r = self._admin().post(self.BASE, self._payload(nom='B'), format='json')
        self.assertEqual(r.status_code, 400)

    def test_second_active_other_protocol_allowed(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='A', actif=True)
        r = self._admin().post(
            self.BASE, self._payload(protocol='oidc', nom='B'), format='json')
        self.assertEqual(r.status_code, 201, r.content)

    def test_inactive_second_provider_allowed(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='A', actif=True)
        r = self._admin().post(
            self.BASE, self._payload(nom='B', actif=False), format='json')
        self.assertEqual(r.status_code, 201, r.content)

    def test_list_is_company_scoped(self):
        IdentityProvider.objects.create(
            company=self.other_company, protocol='saml', nom='X', actif=True)
        r = self._admin().get(self.BASE)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['results']), 0)
