"""testkit — shared, dependency-light test scaffolding for TAQINOR OS.

Importable from any Django app's test modules:

    from testkit.factories import CompanyFactory, DevisFactory, another_tenant
    from testkit.base import TenantAPITestCase

Never imported by production code — dev/test only (see
``requirements-dev.txt``). Keep this package free of app-specific business
logic; it only builds consistent object graphs and common test bases.
"""
