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

    def test_attribute_map_objet_non_nul(self):
        # CI #997 fuzz : ``null`` n'était pas un objet mais le schéma ``{}``
        # l'annonçait valide -> la requête « conforme » répondait 400.
        for valeur in (None, [], 'x', 5):
            with self.subTest(attribute_map=valeur):
                r = self._admin().post(
                    self.BASE, self._payload(attribute_map=valeur),
                    format='json')
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn('attribute_map', r.json())
        r = self._admin().post(
            self.BASE, self._payload(attribute_map={}), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        from apps.identity.serializers import IdentityProviderSerializer
        from drf_spectacular.drainage import get_override
        publie = get_override(
            IdentityProviderSerializer().fields['attribute_map'], 'field')
        self.assertEqual(publie['type'], 'object')
        self.assertNotIn('nullable', publie)

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
        # CI #997 (3) — corps conforme au schéma, ÉTAT contraire : 409.
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('actif', r.json())
        self.assertEqual(IdentityProvider.objects.count(), 1)

    def test_booleens_et_textes_stricts(self):
        # CI #997 (3) — ``enforce_sso: 0`` (schéma : booléen) répondait 201 :
        # un entier n'est ni un booléen ni un texte, 400 nommant le champ.
        for champ, valeur in (('enforce_sso', 0), ('actif', 1),
                              ('auto_provision', 'true'), ('nom', 0),
                              ('entity_id', False)):
            r = self._admin().post(
                self.BASE, self._payload(**{champ: valeur}), format='json')
            self.assertEqual(r.status_code, 400, (champ, r.content))
            self.assertIn(champ, r.json())
        self.assertEqual(IdentityProvider.objects.count(), 0)
        r = self._admin().post(
            self.BASE, self._payload(enforce_sso=True, actif=False),
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['enforce_sso'])

    URLS_SOUPLES = (
        '', 'https://0.com', 'http://a.bc',
        'https://login.microsoftonline.com/x?a=1&b=2',
        'https://idp.example:8443/sso#frag',
        # Hôte à étiquettes de 63 signes, 253 signes en tout : accepté.
        'https://' + '.'.join(['a' * 63] * 3) + '.' + 'b' * 45,
        'https://' + 'a' * 245)
    URLS_REFUSEES = (
        'https://' + 'a' * 246,                        # 254 signes
        'https://' + '.'.join(['a' * 63] * 7),         # l'URL du constat CI
        'ftp://x', 'https://a b', 'http://', ' https://a.bc',
        'https://a\nb', 'HTTPS://a.bc')

    def test_url_acceptee_si_et_seulement_si_le_schema_la_publie(self):
        # CI #997 api-fuzz — le schéma de requête et le serveur partagent UN
        # prédicat (``UrlHttpSouple`` / ``MOTIF_URL_HTTP_SOUPLE``, 253 signes) :
        # ce que le motif admet est accepté (hôte à longues étiquettes, port,
        # requête), ce qu'il exclut est refusé 400 — sur les deux champs.
        import re

        from core.champs_stricts import (
            MOTIF_URL_HTTP_SOUPLE, URL_HTTP_SOUPLE_MAX)

        for url in self.URLS_SOUPLES:
            self.assertTrue(re.fullmatch(MOTIF_URL_HTTP_SOUPLE, url), url)
            self.assertLessEqual(len(url), URL_HTTP_SOUPLE_MAX, url)
        for url in self.URLS_REFUSEES:
            self.assertFalse(
                re.fullmatch(MOTIF_URL_HTTP_SOUPLE, url)
                and len(url) <= URL_HTTP_SOUPLE_MAX, url)
        for champ in ('sso_url', 'metadata_url'):
            for url in self.URLS_SOUPLES:
                r = self._admin().post(
                    self.BASE, self._payload(**{champ: url, 'actif': False}),
                    format='json')
                self.assertEqual(r.status_code, 201, (champ, url, r.content))
            for url in self.URLS_REFUSEES:
                r = self._admin().post(
                    self.BASE, self._payload(**{champ: url, 'actif': False}),
                    format='json')
                self.assertEqual(r.status_code, 400, (champ, url, r.content))
                self.assertIn(champ, r.json())

    def test_schema_url_requete_motif_reponse_libre(self):
        # Le motif n'est publié que côté REQUÊTE : une URL déjà enregistrée,
        # hors motif, reste conforme à la réponse.
        from drf_spectacular.openapi import AutoSchema

        from apps.identity.serializers import IdentityProviderSerializer
        from core.champs_stricts import (
            MOTIF_URL_HTTP_SOUPLE, URL_HTTP_SOUPLE_MAX)

        champs = IdentityProviderSerializer().fields
        for nom in ('sso_url', 'metadata_url'):
            requete = AutoSchema()._map_serializer_field(champs[nom], 'request')
            self.assertEqual(requete['pattern'], MOTIF_URL_HTTP_SOUPLE)
            self.assertEqual(requete['maxLength'], URL_HTTP_SOUPLE_MAX)
            reponse = AutoSchema()._map_serializer_field(champs[nom], 'response')
            self.assertNotIn('pattern', reponse)

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
