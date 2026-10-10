"""YAPIC5 — schéma OpenAPI 3 auto-généré (drf-spectacular).

Prouve :
  * le générateur produit un schéma OpenAPI 3 valide SANS lever d'exception ;
  * les apps « core » citées par le Done de YAPIC5 (crm, ventes, stock, rh,
    compta) ont chacune AU MOINS une opération dans le schéma ;
  * les 3 vues (schema/docs/redoc) sont montées et exigent une session
    authentifiée (SERVE_PERMISSIONS = IsAuthenticated).

NB : le contrôle CI « zéro avertissement » (fail-on-warn) est YAPIC6, pas
cette tâche — un warning drf-spectacular sur un serializer isolé ne fait pas
échouer ce test.
"""
from django.test import TestCase
from django.urls import reverse
from drf_spectacular.generators import SchemaGenerator

from core.parked import est_parquee


class OpenAPISchemaGenerationTests(TestCase):
    """Génération du schéma en mémoire, sans passer par le client HTTP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        generator = SchemaGenerator()
        cls.schema = generator.get_schema(request=None, public=True)

    def test_schema_generates_without_exception(self):
        self.assertIsNotNone(self.schema)
        self.assertIn('openapi', self.schema)
        self.assertIn('paths', self.schema)
        self.assertGreater(len(self.schema['paths']), 0)

    def test_core_apps_have_at_least_one_operation(self):
        """ERR-QAH-TESTS-RACINE (28/09/2026) — `rh` et `compta` sont
        parquées par l'édition MVP solaire courante (`core.parked.
        APPS_PARQUEES`) : ni l'une ni l'autre n'est incluse dans
        `erp_agentique/urls.py`, donc le schéma ne porte plus AUCUN chemin
        `/api/django/rh` ou `/api/django/compta` — pas une régression, l'état
        attendu d'une app sortie (coquille de migrations, zéro url). La liste
        d'origine (crm/ventes/stock/rh/compta) est filtrée sur le registre
        UNIQUE des apps parquées (`core.parked.est_parquee`) plutôt que
        rétrécie à la main, pour que ce test se corrige tout seul si
        rh/compta reviennent un jour."""
        paths = self.schema['paths']
        core_app_prefixes = (
            '/api/django/crm',
            '/api/django/ventes',
            '/api/django/stock',
            '/api/django/rh',
            '/api/django/compta',
        )
        for prefix in core_app_prefixes:
            app_label = prefix.rsplit('/', 1)[-1]
            if est_parquee(app_label):
                continue
            matched = [p for p in paths if p.startswith(prefix)]
            self.assertTrue(
                matched,
                f"aucune opération de schéma trouvée pour le préfixe {prefix}",
            )

    def test_authenticators_are_described_in_the_schema(self):
        """YAPIC6 — les deux authenticators maison ont leur extension.

        Sans `OpenApiAuthenticationExtension`, drf-spectacular émettait
        « could not resolve authenticator » sur CHAQUE vue (1 244
        avertissements uniques, ~66 % du bruit) et le document ne portait
        AUCUN `securitySchemes` : ni Swagger ni un client généré ne savaient
        s'authentifier. Cf. authentication/cookie_auth.py et
        apps/publicapi/auth.py.
        """
        schemes = self.schema.get('components', {}).get('securitySchemes', {})
        self.assertIn('cookieJWT', schemes)
        self.assertIn('publicApiKey', schemes)
        self.assertEqual(schemes['cookieJWT']['in'], 'cookie')
        self.assertEqual(schemes['cookieJWT']['name'], 'access_token')
        self.assertEqual(schemes['publicApiKey']['in'], 'header')

    def test_bearer_jwt_declare_en_alternative_du_cookie(self):
        """ENF2 (C4) — le Bearer accepté par `CookieJWTAuthentication` est
        un schéma déclaré, en OU avec le cookie (jamais un ET)."""
        schemes = self.schema['components']['securitySchemes']
        self.assertEqual(schemes['bearerJWT']['type'], 'http')
        self.assertEqual(schemes['bearerJWT']['scheme'], 'bearer')
        op = self.schema['paths']['/api/django/stock/marques/']['get']
        self.assertIn({'cookieJWT': []}, op['security'])
        self.assertIn({'bearerJWT': []}, op['security'])

    def test_enveloppe_erreur_declaree_sur_chaque_operation(self):
        """ENF2 (C2) — documenté == réel : 400/404/429/500 partout,
        401/403 si authentifiée, 409 sur une écriture."""
        self.assertIn('ErreurApi', self.schema['components']['schemas'])
        ref = '#/components/schemas/ErreurApi'
        liste = self.schema['paths']['/api/django/stock/marques/']
        for code in ('400', '401', '403', '404', '429', '500'):
            reponse = liste['get']['responses'][code]
            self.assertEqual(
                reponse['content']['application/json']['schema']['$ref'], ref)
        self.assertNotIn('409', liste['get']['responses'])
        self.assertIn('409', liste['post']['responses'])
        for chemin, item in self.schema['paths'].items():
            for methode, op in item.items():
                if not isinstance(op, dict) or 'responses' not in op:
                    continue
                for code in ('400', '404', '429', '500'):
                    self.assertIn(code, op['responses'], f'{methode} {chemin}')

    def test_lien_public_a_jeton_sans_authentification_ni_401(self):
        """ENF2 (C5) — une route publique à jeton n'exige ni ne déclare
        aucun justificatif : pas de 401 documenté."""
        op = self.schema['paths']['/api/django/public/sav/ticket/{token}/']['get']
        self.assertFalse(any(op.get('security') or []))
        self.assertNotIn('401', op['responses'])


class OpenAPIDocsEndpointsTests(TestCase):
    """Les 3 endpoints (schema/docs/redoc) existent et exigent une session."""

    # NB : selon l'authenticator qui déclenche le refus (aucun n'expose
    # `authenticate_header`), DRF répond 401 OU 403 pour un appel anonyme —
    # cf. apps/publicapi/tests.py:88, même tolérance.
    def test_schema_endpoint_requires_authentication(self):
        response = self.client.get(reverse('schema'))
        self.assertIn(response.status_code, (401, 403))

    def test_swagger_ui_requires_authentication(self):
        response = self.client.get(reverse('swagger-ui'))
        self.assertIn(response.status_code, (401, 403))

    def test_redoc_requires_authentication(self):
        response = self.client.get(reverse('redoc'))
        self.assertIn(response.status_code, (401, 403))
