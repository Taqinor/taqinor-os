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
        paths = self.schema['paths']
        core_app_prefixes = (
            '/api/django/crm',
            '/api/django/ventes',
            '/api/django/stock',
            '/api/django/rh',
            '/api/django/compta',
        )
        for prefix in core_app_prefixes:
            matched = [p for p in paths if p.startswith(prefix)]
            self.assertTrue(
                matched,
                f"aucune opération de schéma trouvée pour le préfixe {prefix}",
            )


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
