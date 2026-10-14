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

    def test_url_conforme_au_motif_publie_acceptee(self):
        # CI #997 api-fuzz — ``format: uri`` laissait publier un hôte de 7
        # étiquettes de 63 signes (> 253) que ``URLValidator`` refuse (400 sur
        # un corps « conforme »). La requête publie désormais le motif
        # ``MOTIF_URL_HTTP`` : tout ce qu'il admet est accepté, et l'hôte hors
        # limite en est exclu.
        import re

        from core.champs_stricts import MOTIF_URL_HTTP

        etiquette = 'a' * 63
        trop_long = 'https://' + '.'.join([etiquette] * 7)
        self.assertIsNone(re.match(MOTIF_URL_HTTP, trop_long))
        for champ in ('sso_url', 'metadata_url'):
            r = self._admin().post(
                self.BASE, self._payload(**{champ: trop_long, 'actif': False}),
                format='json')
            self.assertEqual(r.status_code, 400, (champ, r.content))
            self.assertIn(champ, r.json())
        for url in ('', 'http://a.bc', 'https://abcdefghij.klmnopqrst',
                    'https://abcdefghij.klmnopqrst/a/b.c-d_e~',
                    'https://idp.example/' + 'a' * 400):
            self.assertTrue(re.match(MOTIF_URL_HTTP, url), url)
            for champ in ('sso_url', 'metadata_url'):
                r = self._admin().post(
                    self.BASE,
                    self._payload(**{champ: url, 'actif': False}),
                    format='json')
                self.assertEqual(r.status_code, 201, (champ, url, r.content))

    def test_schema_url_requete_motif_reponse_libre(self):
        # Le motif n'est publié que côté REQUÊTE : une URL déjà enregistrée,
        # hors motif, reste conforme à la réponse.
        from drf_spectacular.openapi import AutoSchema

        from apps.identity.serializers import IdentityProviderSerializer
        from core.champs_stricts import MOTIF_URL_HTTP

        champs = IdentityProviderSerializer().fields
        for nom in ('sso_url', 'metadata_url'):
            requete = AutoSchema()._map_serializer_field(champs[nom], 'request')
            self.assertEqual(requete['pattern'], MOTIF_URL_HTTP)
            self.assertEqual(requete['maxLength'], 500)
            reponse = AutoSchema()._map_serializer_field(champs[nom], 'response')
            self.assertNotIn('pattern', str(reponse))

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
